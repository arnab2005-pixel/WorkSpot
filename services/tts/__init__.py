"""
Text-to-Speech (TTS) module for PM-AJAY Voice Assistant.
"""

from .chunker import TextChunker
from .indic_tts_worker import IndicTTSWorker

__all__ = ["TextChunker", "IndicTTSWorker"]
