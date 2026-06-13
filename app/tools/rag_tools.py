"""
rag_tools.py — Ingestión async de documentos en Flamehaven FileSearch RAG.

REGLA UNIVERSAL: Nada puede ser subido al RAG sin estar en formato MD
en /compose/documentos_listos/{store}/

Los 3 casos de ingesta:
  CASO 1: source es .md Y está en documentos_listos/{store}/
          → upload directo a Flamehaven (sin conversión, sin copia)

  CASO 2: source NO es .md (cualquier path local o URL)
          → descargar si es URL
          → convertir con markitdown
          → guardar en documentos_listos/{store}/{stem}.md
          → upload a Flamehaven

  CASO 3: source es .md PERO no está en documentos_listos/{store}/
          → copiar a documentos_listos/{store}/{name}
          → upload a Flamehaven

Stores / colecciones:
  Cada store tiene su subcarpeta: documentos_listos/{store}/ y documentos_nuevos/{store}/
  Si el store no existe en Flamehaven, se crea automáticamente al subir.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

# Raíz de los volúmenes compartidos con Flamehaven
DOCUMENTOS_LISTOS_ROOT = Path("/compose/documentos_listos")
DOCUMENTOS_NUEVOS_ROOT = Path("/compose/documentos_nuevos")


def _now_ts() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# Dataclass del job
# ---------------------------------------------------------------------------

@dataclass
class RagIngestJob:
    id: str
    source: str           # URL o path local (original, antes de conversión)
    original_name: str    # nombre original del documento
    store: str            # colección destino en Flamehaven
    caso: int = 0         # 1, 2 o 3 según la lógica de detección
    overwrite: bool = False  # True: borrar duplicado y reingestar / False: rechazar si ya existe
    status: str = "queued"   # queued / running / uploading / skipped_duplicate / completed / failed
    created_at: float = field(default_factory=_now_ts)
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    md_path: str | None = None          # path final del .md en documentos_listos
    rag_response: dict | None = None    # respuesta JSON del upload a Flamehaven
    duplicate_info: dict | None = None  # si se detectó duplicado, info del doc previo

    def as_dict(self) -> dict:
        return {
            "job_id": self.id,
            "status": self.status,
            "caso": self.caso,
            "overwrite": self.overwrite,
            "source": self.source,
            "original_name": self.original_name,
            "store": self.store,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "md_path": self.md_path,
            "rag_response": self.rag_response,
            "duplicate_info": self.duplicate_info,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Job store (singleton en memoria)
# ---------------------------------------------------------------------------

class RagIngestJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, RagIngestJob] = {}
        self._lock = threading.Lock()

    def create(self, job: RagIngestJob) -> None:
        with self._lock:
            self._jobs[job.id] = job

    def get(self, job_id: str) -> RagIngestJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_recent(self, limit: int = 20) -> list[dict]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
            return [j.as_dict() for j in jobs[:limit]]


JOB_STORE = RagIngestJobStore()


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _listos_dir(store: str) -> Path:
    """Devuelve documentos_listos/{store}/ y la crea si no existe."""
    p = DOCUMENTOS_LISTOS_ROOT / store
    p.mkdir(parents=True, exist_ok=True)
    return p


def _detectar_caso(source: str, store: str) -> tuple[int, Path | None]:
    """
    Detecta el caso de ingesta.
    Devuelve (caso, Path_local_o_None_si_URL).
    """
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        return 2, None  # URL → siempre convertir

    p = Path(source)
    is_md = p.suffix.lower() == ".md"
    listos_dir = DOCUMENTOS_LISTOS_ROOT / store

    if is_md:
        try:
            p.resolve().relative_to(listos_dir.resolve())
            return 1, p  # CASO 1: MD ya en documentos_listos
        except ValueError:
            return 3, p  # CASO 3: MD fuera de documentos_listos
    else:
        return 2, p  # CASO 2: no es MD


def _list_store_docs(store: str, api_key: str, base_url: str) -> list[dict]:
    """Devuelve lista de docs del store (title, uri, metadata). Vacía si el store no existe."""
    import httpx
    url = base_url.rstrip("/") + f"/api/stores/{store}/docs"
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers={"Authorization": f"Bearer {api_key}"})
    if resp.status_code == 404:
        return []
    if resp.status_code != 200:
        raise RuntimeError(f"Flamehaven list_docs HTTP {resp.status_code}: {resp.text[:200]}")
    return resp.json().get("docs", [])


def _find_duplicate(title: str, store: str, api_key: str, base_url: str) -> dict | None:
    """
    Busca un doc con el mismo título (filename) en el store.
    Comparación por nombre normalizado (minúsculas, sin espacios extremos).
    Devuelve el dict del doc si existe, None si no.
    """
    needle = title.strip().lower()
    for doc in _list_store_docs(store, api_key, base_url):
        if doc.get("title", "").strip().lower() == needle:
            return doc
    return None


def _delete_doc_from_flamehaven(title: str, store: str, api_key: str, base_url: str) -> dict:
    """Borra un doc por título usando DELETE /api/delete-doc?store={store}&title={title}."""
    import httpx
    url = base_url.rstrip("/") + "/api/delete-doc"
    with httpx.Client(timeout=30.0) as client:
        resp = client.delete(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            params={"store": store, "title": title},
        )
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"Flamehaven delete_doc HTTP {resp.status_code}: {resp.text[:200]}")
    return resp.json() if resp.content else {"status": "success"}


def _upload_to_flamehaven(
    md_path: Path,
    store: str,
    api_key: str,
    base_url: str,
    overwrite: bool = False,
) -> dict:
    """
    Sube un .md a Flamehaven respetando la regla de no-duplicados.

    - Si no existe doc con el mismo nombre → sube normalmente.
    - Si existe Y overwrite=True  → borra el anterior y sube el nuevo.
    - Si existe Y overwrite=False → lanza DuplicateDocError (no sube).
    """
    import httpx

    title = md_path.name
    existing = _find_duplicate(title, store, api_key, base_url)

    if existing:
        if not overwrite:
            raise DuplicateDocError(
                f"Ya existe un documento con el nombre '{title}' en el store '{store}'. "
                f"Usá overwrite=true para reemplazarlo.",
                existing,
            )
        # overwrite=True: eliminar el doc anterior antes de reingestar
        _delete_doc_from_flamehaven(title, store, api_key, base_url)

    upload_url = base_url.rstrip("/") + "/api/upload/single"
    with open(md_path, "rb") as fh:
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(
                upload_url,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (title, fh, "text/markdown")},
                data={"store": store},
            )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Flamehaven upload falló HTTP {resp.status_code}: {resp.text[:300]}"
        )
    result = resp.json()
    if existing:
        result["overwritten"] = True
        result["previous_uri"] = existing.get("uri", "")
    return result


class DuplicateDocError(Exception):
    """Se lanza cuando existe un doc con el mismo nombre y overwrite=False."""
    def __init__(self, message: str, existing_doc: dict):
        super().__init__(message)
        self.existing_doc = existing_doc


# ---------------------------------------------------------------------------
# Worker principal
# ---------------------------------------------------------------------------

def _run_ingest_job(job: RagIngestJob, api_key: str, base_url: str) -> None:
    """
    Ejecuta la ingesta según el caso detectado.
    Regla universal: el MD siempre termina en documentos_listos/{store}/
    antes del upload a Flamehaven.
    """
    try:
        job.status = "running"
        job.started_at = _now_ts()

        listos_dir = _listos_dir(job.store)
        caso, local_path = _detectar_caso(job.source, job.store)
        job.caso = caso

        parsed = urlparse(job.source)
        is_url = parsed.scheme in ("http", "https")

        if caso == 1:
            # MD ya en documentos_listos — upload directo sin tocar el archivo
            md_path = local_path
            job.md_path = str(md_path)

        elif caso == 2:
            # No es MD (o es URL): descargar si URL, convertir, guardar en listos
            with tempfile.TemporaryDirectory() as tmpdir:
                if is_url:
                    import httpx
                    dl_name = Path(parsed.path).name or "documento"
                    dl_path = Path(tmpdir) / dl_name
                    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                        r = client.get(job.source)
                        r.raise_for_status()
                        dl_path.write_bytes(r.content)
                    source_path = dl_path
                else:
                    source_path = local_path
                    if not source_path.exists():
                        raise FileNotFoundError(f"Archivo no encontrado: {job.source}")

                from markitdown import MarkItDown
                result = MarkItDown().convert(str(source_path))
                md_content = result.text_content or ""

                header = (
                    f"<!-- source: {job.source} -->\n"
                    f"<!-- original_name: {job.original_name} -->\n\n"
                )
                stem = Path(job.original_name).stem or source_path.stem
                md_path = listos_dir / f"{stem}.md"
                md_path.write_text(header + md_content, encoding="utf-8")
                job.md_path = str(md_path)

        elif caso == 3:
            # Es MD pero fuera de documentos_listos — copiar a listos
            if not local_path.exists():
                raise FileNotFoundError(f"Archivo no encontrado: {job.source}")
            md_path = listos_dir / local_path.name
            shutil.copy2(local_path, md_path)
            job.md_path = str(md_path)

        # Upload a Flamehaven siempre desde documentos_listos/{store}/
        job.status = "uploading"
        try:
            job.rag_response = _upload_to_flamehaven(
                Path(job.md_path), job.store, api_key, base_url, overwrite=job.overwrite
            )
        except DuplicateDocError as dup:
            job.status = "skipped_duplicate"
            job.duplicate_info = dup.existing_doc
            job.error = str(dup)
            job.finished_at = _now_ts()
            return
        job.status = "completed"
        job.finished_at = _now_ts()

    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.finished_at = _now_ts()


# ---------------------------------------------------------------------------
# Funciones públicas (tools MCP)
# ---------------------------------------------------------------------------

def start_rag_ingest(config, args: dict) -> dict:
    """
    Inicia ingestión async de un documento en Flamehaven RAG.
    Respeta la regla: nada va al RAG sin ser MD en documentos_listos/{store}/.

    Detecta automáticamente el caso:
      CASO 1: source ya es .md en documentos_listos/{store}/ → upload directo
      CASO 2: source no es .md (o es URL) → convertir → guardar en listos → upload
      CASO 3: source es .md pero fuera de listos → copiar a listos → upload

    Args:
      source        (req) — URL o path local al documento
      store         (opt) — colección destino (default: config.rag.default_store)
      original_name (opt) — nombre descriptivo para el índice
    """
    source = args.get("source", "").strip()
    if not source:
        return {"error": "Parámetro 'source' requerido."}

    store = args.get("store", "").strip() or config.rag.default_store

    original_name = args.get("original_name", "").strip()
    if not original_name:
        parsed = urlparse(source)
        original_name = Path(parsed.path).name or Path(source).name or "document"

    api_key = os.environ.get(config.rag.api_key_env, "")
    if not api_key:
        return {"error": f"Variable de entorno '{config.rag.api_key_env}' no configurada."}

    overwrite = bool(args.get("overwrite", False))

    # Detección anticipada del caso para informar al caller
    caso, _ = _detectar_caso(source, store)

    job = RagIngestJob(
        id=f"rag_{uuid4().hex[:12]}",
        source=source,
        original_name=original_name,
        store=store,
        caso=caso,
        overwrite=overwrite,
    )
    JOB_STORE.create(job)

    t = threading.Thread(
        target=_run_ingest_job,
        args=(job, api_key, config.rag.base_url),
        daemon=True,
    )
    t.start()

    caso_desc = {
        1: "MD en documentos_listos → upload directo",
        2: "No es MD → convertir → guardar en documentos_listos → upload",
        3: "MD fuera de documentos_listos → copiar → upload",
    }

    return {
        "job_id": job.id,
        "status": job.status,
        "caso": caso,
        "caso_descripcion": caso_desc.get(caso, ""),
        "overwrite": overwrite,
        "source": job.source,
        "original_name": job.original_name,
        "store": job.store,
        "md_destino": str(DOCUMENTOS_LISTOS_ROOT / store),
        "message": "Ingestión iniciada en background. Usa get_rag_ingest_job para consultar estado.",
    }


def get_rag_ingest_job(config, args: dict) -> dict:
    """Consulta estado de un job de ingestión RAG."""
    job_id = args.get("job_id", "").strip()
    if not job_id:
        return {"error": "Parámetro 'job_id' requerido."}
    job = JOB_STORE.get(job_id)
    if not job:
        return {"error": f"Job '{job_id}' no encontrado."}
    return job.as_dict()


def list_rag_ingest_jobs(config, args: dict) -> dict:
    """Lista jobs recientes de ingestión RAG."""
    limit = int(args.get("limit", 20))
    return {"jobs": JOB_STORE.list_recent(limit=limit)}


# ---------------------------------------------------------------------------
# Tool: scan_documentos_nuevos
# ---------------------------------------------------------------------------

def scan_documentos_nuevos(config, args: dict) -> dict:
    """
    Escanea documentos_nuevos/{store}/ y lanza un job de ingesta por cada archivo.
    Aplica los 3 casos automáticamente. Los archivos procesados se mueven a
    documentos_nuevos/{store}/procesados/ para evitar reprocesarlos.

    Args:
      store   (opt) — store a escanear (default: config.rag.default_store).
                      Pasar "all" para escanear todos los stores.
      dry_run (opt) — si true, solo lista archivos sin ingestar.
            include_procesados (opt) — si true, también incluye
                                            documentos_nuevos/{store}/procesados/.
    max_files (opt) — limita la cantidad de archivos procesados/listados
                por llamada para evitar timeouts.
    """
    api_key = os.environ.get(config.rag.api_key_env, "")
    if not api_key:
        return {"error": f"Variable de entorno '{config.rag.api_key_env}' no configurada."}

    store_param = args.get("store", "").strip() or config.rag.default_store
    dry_run = bool(args.get("dry_run", False))
    overwrite = bool(args.get("overwrite", False))
    include_procesados = bool(args.get("include_procesados", False))
    max_files_raw = args.get("max_files")
    max_files = None
    if max_files_raw is not None:
        try:
            parsed_max = int(max_files_raw)
            if parsed_max > 0:
                max_files = parsed_max
        except (TypeError, ValueError):
            max_files = None
    base_url = config.rag.base_url

    if store_param == "all":
        stores = [p.name for p in DOCUMENTOS_NUEVOS_ROOT.iterdir() if p.is_dir() and p.name != "procesados"]
    else:
        stores = [store_param]

    launched_jobs = []
    preview = []

    for store in stores:
        nuevos_dir = DOCUMENTOS_NUEVOS_ROOT / store
        if not nuevos_dir.exists():
            continue
        procesados_dir = nuevos_dir / "procesados"
        procesados_dir.mkdir(exist_ok=True)

        files_to_scan: list[tuple[Path, str]] = []
        for filepath in sorted(nuevos_dir.iterdir()):
            if filepath.is_file():
                files_to_scan.append((filepath, "nuevos"))

        if include_procesados:
            for filepath in sorted(procesados_dir.iterdir()):
                if filepath.is_file():
                    files_to_scan.append((filepath, "procesados"))

        if max_files is not None:
            files_to_scan = files_to_scan[:max_files]

        for filepath, origen in files_to_scan:
            caso, _ = _detectar_caso(str(filepath), store)

            if dry_run:
                preview.append({"file": filepath.name, "store": store, "caso": caso, "origen": origen})
                continue

            original_name = filepath.stem
            if origen == "procesados":
                # Ya está en procesados, no mover.
                dest = filepath
            else:
                # Mover a procesados ANTES del thread para evitar reprocesar
                dest = procesados_dir / filepath.name
                shutil.move(str(filepath), dest)

            job = RagIngestJob(
                id=f"rag_{uuid4().hex[:12]}",
                source=str(dest),
                original_name=original_name,
                store=store,
                caso=caso,
                overwrite=overwrite,
            )
            JOB_STORE.create(job)

            t = threading.Thread(
                target=_run_ingest_job,
                args=(job, api_key, base_url),
                daemon=True,
            )
            t.start()
            launched_jobs.append({
                "job_id": job.id,
                "file": filepath.name,
                "store": store,
                "caso": caso,
                "origen": origen,
            })

    if dry_run:
        return {
            "dry_run": True,
            "include_procesados": include_procesados,
            "max_files": max_files,
            "stores_escaneados": stores,
            "archivos_encontrados": len(preview),
            "archivos": preview,
        }

    return {
        "include_procesados": include_procesados,
        "max_files": max_files,
        "stores_escaneados": stores,
        "jobs_lanzados": len(launched_jobs),
        "jobs": launched_jobs,
        "message": "Usa get_rag_ingest_job o list_rag_ingest_jobs para seguir el progreso.",
    }
