from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from app.config.models import AppConfig
from app.utils.security import resolve_allowed_path


def _now_ts() -> float:
    return time.time()


def _translate_text(source_lang: str, target_lang: str, text: str) -> str:
    from deep_translator import GoogleTranslator

    translator = GoogleTranslator(source=source_lang, target=target_lang)
    return translator.translate(text)


def _split_markdown_into_chunks(content: str, max_chars: int) -> list[str]:
    paragraphs = content.split("\n\n")
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= max_chars:
            current = paragraph
            continue

        start = 0
        while start < len(paragraph):
            end = min(start + max_chars, len(paragraph))
            chunks.append(paragraph[start:end])
            start = end

    if current:
        chunks.append(current)

    return chunks


@dataclass
class TranslationJob:
    id: str
    input_path: str
    output_path: str
    source_lang: str
    target_lang: str
    status: str = "queued"
    created_at: float = field(default_factory=_now_ts)
    started_at: float | None = None
    finished_at: float | None = None
    total_chunks: int = 0
    translated_chunks: int = 0
    error: str | None = None
    overwrite: bool = False

    def as_dict(self) -> dict:
        return {
            "job_id": self.id,
            "status": self.status,
            "input_path": self.input_path,
            "output_path": self.output_path,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_chunks": self.total_chunks,
            "translated_chunks": self.translated_chunks,
            "progress_pct": 0 if self.total_chunks == 0 else round((self.translated_chunks / self.total_chunks) * 100, 2),
            "error": self.error,
        }


class TranslationJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, TranslationJob] = {}
        self._lock = threading.Lock()

    def create(self, job: TranslationJob) -> None:
        with self._lock:
            self._jobs[job.id] = job

    def get(self, job_id: str) -> TranslationJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_recent(self, limit: int = 20) -> list[dict]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)
            return [job.as_dict() for job in jobs[:limit]]


JOB_STORE = TranslationJobStore()


def _run_translation_job(job: TranslationJob, chunk_size: int, retries: int) -> None:
    try:
        job.status = "running"
        job.started_at = _now_ts()

        input_path = Path(job.input_path)
        output_path = Path(job.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists() and not job.overwrite:
            raise ValueError(f"El archivo de salida ya existe: {output_path}")

        content = input_path.read_text(encoding="utf-8", errors="replace")
        chunks = _split_markdown_into_chunks(content, max_chars=chunk_size)
        job.total_chunks = len(chunks)

        temp_path = output_path.with_suffix(f"{output_path.suffix}.part")
        with temp_path.open("w", encoding="utf-8") as stream:
            for idx, chunk in enumerate(chunks, start=1):
                translated_chunk: str | None = None
                attempt = 0
                last_error = ""
                while attempt <= retries and translated_chunk is None:
                    try:
                        translated_chunk = _translate_text(job.source_lang, job.target_lang, chunk)
                    except Exception as exc:
                        last_error = str(exc)
                        attempt += 1
                        if attempt <= retries:
                            time.sleep(min(2 * attempt, 6))
                if translated_chunk is None:
                    raise RuntimeError(f"Falló la traducción del chunk {idx}/{job.total_chunks}: {last_error}")

                if idx > 1:
                    stream.write("\n\n")
                stream.write(translated_chunk)
                stream.flush()
                job.translated_chunks = idx

        temp_path.replace(output_path)
        job.status = "completed"
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
    finally:
        job.finished_at = _now_ts()


def start_markdown_translation(config: AppConfig, arguments: dict) -> dict:
    input_path_raw = arguments.get("input_path")
    if not input_path_raw:
        raise ValueError("Se requiere 'input_path'")

    source_lang = str(arguments.get("source_lang", "auto"))
    target_lang = str(arguments.get("target_lang", "es"))
    chunk_size = int(arguments.get("chunk_size", 2800))
    retries = int(arguments.get("retries", 2))
    overwrite = bool(arguments.get("overwrite", False))

    if chunk_size < 300:
        raise ValueError("'chunk_size' debe ser >= 300")
    if retries < 0:
        raise ValueError("'retries' no puede ser negativo")

    input_path = resolve_allowed_path(config, input_path_raw)
    if not input_path.exists() or not input_path.is_file():
        raise ValueError(f"Archivo de entrada no encontrado: {input_path_raw}")

    output_path_raw = arguments.get("output_path")
    if output_path_raw:
        output_path = resolve_allowed_path(config, str(output_path_raw))
    else:
        output_path = input_path.with_name(f"{input_path.stem}-{target_lang}{input_path.suffix}")

    job = TranslationJob(
        id=uuid4().hex,
        input_path=str(input_path),
        output_path=str(output_path),
        source_lang=source_lang,
        target_lang=target_lang,
        overwrite=overwrite,
    )
    JOB_STORE.create(job)

    worker = threading.Thread(
        target=_run_translation_job,
        args=(job, chunk_size, retries),
        daemon=True,
        name=f"translation-job-{job.id[:8]}",
    )
    worker.start()

    return {
        "message": "Traducción iniciada en segundo plano",
        **job.as_dict(),
    }


def get_translation_job(_config: AppConfig, arguments: dict) -> dict:
    job_id = arguments.get("job_id")
    if not job_id:
        raise ValueError("Se requiere 'job_id'")

    job = JOB_STORE.get(str(job_id))
    if job is None:
        raise ValueError(f"No existe job_id: {job_id}")
    return job.as_dict()


def list_translation_jobs(_config: AppConfig, arguments: dict) -> dict:
    limit = int(arguments.get("limit", 20))
    if limit < 1:
        raise ValueError("'limit' debe ser >= 1")
    if limit > 100:
        limit = 100
    return {
        "jobs": JOB_STORE.list_recent(limit=limit),
        "count": min(limit, len(JOB_STORE.list_recent(limit=limit))),
    }
