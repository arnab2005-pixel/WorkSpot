"""
Sentence-boundary chunker for incremental TTS synthesis.

Splits Hindi/Indic strings at punctuation boundaries: ।, ?, !, ,
ensuring the neural vocoder runs incrementally for minimum First-Packet-Time.
"""

import re
from collections.abc import Generator


class TextChunker:
    """
    Incremental sentence-boundary chunker for Devanagari and Hindi text.
    """

    # Primary sentence delimiters including Hindi danda (।)
    DELIMITERS_PATTERN = re.compile(r"([।\?\!\,\;\n]+)")

    def __init__(self, min_chunk_chars: int = 15, max_chunk_chars: int = 120):
        self.min_chunk_chars = min_chunk_chars
        self.max_chunk_chars = max_chunk_chars

    def split_into_chunks(self, text: str) -> list[str]:
        """
        Split text into synthesis chunks.

        Merges very short fragments (< min_chunk_chars) to avoid unnatural acoustic pauses.
        """
        if not text:
            return []

        tokens = self.DELIMITERS_PATTERN.split(text)
        raw_chunks: list[str] = []
        current = ""

        for token in tokens:
            if not token:
                continue
            if self.DELIMITERS_PATTERN.match(token):
                current += token
                raw_chunks.append(current.strip())
                current = ""
            else:
                current += token

        if current.strip():
            raw_chunks.append(current.strip())

        # Merge undersized chunks
        merged_chunks: list[str] = []
        accum = ""

        for c in raw_chunks:
            if not c:
                continue
            if len(accum) + len(c) < self.min_chunk_chars:
                accum = (accum + " " + c).strip()
            elif len(accum) + len(c) > self.max_chunk_chars and accum:
                merged_chunks.append(accum)
                accum = c
            else:
                accum = (accum + " " + c).strip()
                merged_chunks.append(accum)
                accum = ""

        if accum:
            if merged_chunks:
                merged_chunks[-1] = (merged_chunks[-1] + " " + accum).strip()
            else:
                merged_chunks.append(accum)

        return [m for m in merged_chunks if m.strip()]

    def stream_chunks(self, text: str) -> Generator[str, None, None]:
        """Generator streaming chunks lazily."""
        yield from self.split_into_chunks(text)
