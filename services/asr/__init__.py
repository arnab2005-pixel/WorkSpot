"""
ASR (Speech-to-Text) module for PM-AJAY Voice Assistant using faster-whisper.
"""

from .whisper_worker import TranscriptionResult, WhisperASRWorker

__all__ = ["TranscriptionResult", "WhisperASRWorker"]
