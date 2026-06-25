from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any

try:
    from faster_whisper import WhisperModel
except ImportError:  # pragma: no cover - depende del entorno
    WhisperModel = None

log = logging.getLogger("conti.transcription")


class TranscriptionService:
    def __init__(self) -> None:
        self._model: WhisperModel | None = None
        self._model_lock = Lock()
        self._model_size = os.getenv("WHISPER_MODEL_SIZE", "tiny")
        self._device = os.getenv("WHISPER_DEVICE", "cpu")
        self._compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

    def _get_model(self) -> WhisperModel:
        if WhisperModel is None:
            raise RuntimeError("faster_whisper no está instalado en este entorno")
        if self._model is not None:
            return self._model

        with self._model_lock:
            if self._model is None:
                log.info(
                    "Cargando modelo Whisper local",
                    extra={
                        "model_size": self._model_size,
                        "device": self._device,
                        "compute_type": self._compute_type,
                    },
                )
                self._model = WhisperModel(
                    self._model_size,
                    device=self._device,
                    compute_type=self._compute_type,
                )
        return self._model

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        *,
        filename: str | None = None,
        language: str = "es",
    ) -> dict[str, Any]:
        if not audio_bytes:
            raise ValueError("El archivo de audio está vacío")

        suffix = Path(filename or "audio.webm").suffix or ".webm"
        temp_path: str | None = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name

            model = self._get_model()
            segments, info = model.transcribe(
                temp_path,
                language=language or "es",
                vad_filter=True,
                beam_size=1,
                condition_on_previous_text=False,
            )

            transcript = " ".join(segment.text.strip() for segment in segments if segment.text).strip()
            detected_language = getattr(info, "language", language or "es")
            duration = float(getattr(info, "duration", 0.0) or 0.0)

            return {
                "transcript": transcript,
                "language": detected_language,
                "duration": duration,
                "engine": "faster-whisper",
                "model": self._model_size,
            }
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    log.warning("No se pudo borrar el temporal de audio", extra={"path": temp_path})


_transcription_service: TranscriptionService | None = None


def get_transcription_service() -> TranscriptionService:
    global _transcription_service
    if _transcription_service is None:
        _transcription_service = TranscriptionService()
    return _transcription_service