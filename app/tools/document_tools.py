from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4


DOCUMENTOS_LISTOS_ROOT = Path("/compose/documentos_listos")


def _now_ts() -> float:
    return time.time()


@dataclass
class MdConversionJob:
    id: str
    source: str
    store: str
    output_path: str          # ruta final en documentos_listos/{store}/
    also_translate: bool
    target_lang: str
    status: str = "queued"
    created_at: float = field(default_factory=_now_ts)
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    md_path: str | None = None
    translation_job_id: str | None = None
    output_path_ignored: str | None = None  # informa si se ignoró un output_path externo

    def as_dict(self) -> dict:
        return {
            "job_id": self.id,
            "status": self.status,
            "source": self.source,
            "store": self.store,
            "output_path": self.output_path,
            "output_path_ignored": self.output_path_ignored,
            "also_translate": self.also_translate,
            "target_lang": self.target_lang,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "md_path": self.md_path,
            "translation_job_id": self.translation_job_id,
            "error": self.error,
        }


class MdConversionJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, MdConversionJob] = {}
        self._lock = threading.Lock()

    def create(self, job: MdConversionJob) -> None:
        with self._lock:
            self._jobs[job.id] = job

    def get(self, job_id: str) -> MdConversionJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_recent(self, limit: int = 20) -> list[dict]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
            return [j.as_dict() for j in jobs[:limit]]


JOB_STORE = MdConversionJobStore()


def _run_conversion_job(job: MdConversionJob) -> None:
    try:
        job.status = "running"
        job.started_at = _now_ts()

        from markitdown import MarkItDown

        output_path = Path(job.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        mid = MarkItDown()
        result = mid.convert(job.source)
        md_content = result.text_content

        output_path.write_text(md_content, encoding="utf-8")
        job.md_path = str(output_path)

        if job.also_translate:
            from app.tools.translation_tools import TranslationJob, JOB_STORE as TRANS_STORE, _run_translation_job

            trans_job = TranslationJob(
                id=uuid4().hex,
                input_path=str(output_path),
                output_path=str(output_path.with_name(f"{output_path.stem}-{job.target_lang}{output_path.suffix}")),
                source_lang="auto",
                target_lang=job.target_lang,
                overwrite=True,
            )
            TRANS_STORE.create(trans_job)
            job.translation_job_id = trans_job.id

            trans_thread = threading.Thread(
                target=_run_translation_job,
                args=(trans_job, 2800, 2),
                daemon=True,
                name=f"trans-job-{trans_job.id[:8]}",
            )
            trans_thread.start()
            job.status = "completed_translating"
        else:
            job.status = "completed"

    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
    finally:
        job.finished_at = _now_ts()


def _resolve_output_path(source: str, output_path_raw: str | None, store: str) -> tuple[Path, str | None]:
    """
    Calcula la ruta de salida SIEMPRE en documentos_listos/{store}/.
    Si se recibió output_path_raw, lo ignora y lo devuelve como segundo valor
    para que el caller pueda informarlo en la respuesta.
    """
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        name = Path(parsed.path).stem or "document"
    else:
        name = Path(source).stem or "document"
    target_dir = DOCUMENTOS_LISTOS_ROOT / store
    target_dir.mkdir(parents=True, exist_ok=True)
    final_path = target_dir / f"{name}.md"
    ignored = output_path_raw if output_path_raw else None
    return final_path, ignored


def start_pdf_to_markdown(_config, arguments: dict) -> dict:
    source = arguments.get("source")
    if not source:
        raise ValueError("Se requiere 'source' (URL o ruta local al PDF/documento)")

    output_path_raw = arguments.get("output_path")
    store = str(arguments.get("store") or _config.rag.default_store)
    also_translate = bool(arguments.get("also_translate", False))
    target_lang = str(arguments.get("target_lang", "en"))

    output_path, ignored = _resolve_output_path(source, output_path_raw, store)

    job = MdConversionJob(
        id=uuid4().hex,
        source=source,
        store=store,
        output_path=str(output_path),
        also_translate=also_translate,
        target_lang=target_lang,
        output_path_ignored=ignored,
    )
    JOB_STORE.create(job)

    worker = threading.Thread(
        target=_run_conversion_job,
        args=(job,),
        daemon=True,
        name=f"md-conv-job-{job.id[:8]}",
    )
    worker.start()

    result = {
        "message": "Conversión iniciada en segundo plano",
        **job.as_dict(),
    }
    if ignored:
        result["aviso"] = (
            f"output_path '{ignored}' ignorado. "
            f"El MD siempre se deposita en /compose/documentos_listos/{store}/."
        )
    return result


def get_md_conversion_job(_config, arguments: dict) -> dict:
    job_id = arguments.get("job_id")
    if not job_id:
        raise ValueError("Se requiere 'job_id'")
    job = JOB_STORE.get(str(job_id))
    if job is None:
        raise ValueError(f"No existe job_id: {job_id}")
    return job.as_dict()


def list_md_conversion_jobs(_config, arguments: dict) -> dict:
    limit = int(arguments.get("limit", 20))
    if limit < 1:
        raise ValueError("'limit' debe ser >= 1")
    if limit > 100:
        limit = 100
    jobs = JOB_STORE.list_recent(limit=limit)
    return {"jobs": jobs, "count": len(jobs)}
