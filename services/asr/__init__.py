"""
ASR (Speech-to-Text) module for PM-AJAY Voice Assistant using faster-whisper.
"""

from .whisper_worker import WhisperASRWorker, TranscriptionResult

__all__ = ["WhisperASRWorker", "TranscriptionResult"]