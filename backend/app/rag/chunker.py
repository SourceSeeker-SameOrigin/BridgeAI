import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    """A chunk of text with its index position."""
    content: str
    index: int


def split_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[TextChunk]:
    """Split text into chunks with overlap.

    Strategy:
      1. Split by paragraphs (double newline)
      2. If a paragraph exceeds chunk_size, split by sentences
      3. Merge small paragraphs until reaching chunk_size
      4. Apply overlap between consecutive chunks
    """
    if not text or not text.strip():
        return []

    # Detect QA format: lines with "问题 | 答案" or "xxx | xxx" pattern (e.g., Excel exports)
    lines = text.strip().split("\n")
    qa_lines = [l for l in lines if "|" in l and len(l.strip()) > 10]
    if len(qa_lines) > len(lines) * 0.5:
        # QA format detected — each line is a separate chunk for precise matching
        chunks: list[TextChunk] = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith("##"):  # skip headers
                continue
            # Skip header row (first row with column names)
            if i == 0 and "|" in line and len(line) < 30:
                continue
            chunks.append(TextChunk(content=line, index=len(chunks)))
        return chunks if chunks else []  # fallback to normal splitting if no chunks

    paragraphs = _split_paragraphs(text)
    # Further split paragraphs that exceed chunk_size into sentences
    segments: list[str] = []
    for para in paragraphs:
        if len(para) <= chunk_size:
            segments.append(para)
        else:
            sentences = _split_sentences(para)
            segments.extend(sentences)

    # Merge segments into chunks respecting chunk_size
    chunks: list[TextChunk] = []
    current_parts: list[str] = []
    current_len = 0
    chunk_index = 0

    for segment in segments:
        segment_len = len(segment)
        # If adding this segment would exceed chunk_size, flush current buffer
        if current_parts and current_len + segment_len + 1 > chunk_size:
            chunk_text = "\n".join(current_parts).strip()
            if chunk_text:
                chunks.append(TextChunk(content=chunk_text, index=chunk_index))
                chunk_index += 1

            # Apply overlap: keep trailing text from current chunk
            overlap_text = chunk_text[-chunk_overlap:] if chunk_overlap > 0 else ""
            current_parts = [overlap_text] if overlap_text else []
            current_len = len(overlap_text)

        current_parts.append(segment)
        current_len += segment_len + 1  # +1 for join separator

    # Flush remaining
    if current_parts:
        chunk_text = "\n".join(current_parts).strip()
        if chunk_text:
            chunks.append(TextChunk(content=chunk_text, index=chunk_index))

    return chunks


def _split_paragraphs(text: str) -> list[str]:
    """Split text by double newlines (paragraph boundaries)."""
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using common delimiters."""
    # Split on sentence-ending punctuation followed by whitespace
    sentences = re.split(r"(?<=[.!?。！？])\s+", text)
    return [s.strip() for s in sentences if s.strip()]
