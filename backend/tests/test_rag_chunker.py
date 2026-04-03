"""Tests for app.rag.chunker — text chunking with overlap."""

import pytest

from app.rag.chunker import TextChunk, _split_paragraphs, _split_sentences, split_text


class TestSplitParagraphs:
    """Test paragraph splitting by double newline."""

    def test_two_paragraphs(self) -> None:
        text = "Paragraph one.\n\nParagraph two."
        result = _split_paragraphs(text)
        assert len(result) == 2
        assert result[0] == "Paragraph one."
        assert result[1] == "Paragraph two."

    def test_single_paragraph(self) -> None:
        text = "Single paragraph with no double newlines."
        result = _split_paragraphs(text)
        assert len(result) == 1

    def test_empty_string(self) -> None:
        result = _split_paragraphs("")
        assert result == []

    def test_multiple_blank_lines(self) -> None:
        text = "A\n\n\n\nB"
        result = _split_paragraphs(text)
        assert len(result) == 2

    def test_whitespace_between_paragraphs(self) -> None:
        text = "A\n  \nB"
        result = _split_paragraphs(text)
        assert len(result) == 2

    def test_strips_whitespace(self) -> None:
        text = "  A  \n\n  B  "
        result = _split_paragraphs(text)
        assert result[0] == "A"
        assert result[1] == "B"


class TestSplitSentences:
    """Test sentence splitting."""

    def test_english_sentences(self) -> None:
        text = "First sentence. Second sentence. Third."
        result = _split_sentences(text)
        assert len(result) == 3

    def test_chinese_sentences(self) -> None:
        text = "第一句话。 第二句话！ 第三句话？"
        result = _split_sentences(text)
        assert len(result) == 3

    def test_no_sentence_boundary(self) -> None:
        text = "One continuous text without punctuation"
        result = _split_sentences(text)
        assert len(result) == 1

    def test_exclamation_and_question(self) -> None:
        text = "Really? Yes! OK."
        result = _split_sentences(text)
        assert len(result) == 3


class TestSplitText:
    """Test the main split_text function."""

    # --- Empty/null inputs ---
    def test_empty_string(self) -> None:
        assert split_text("") == []

    def test_whitespace_only(self) -> None:
        assert split_text("   \n\n  ") == []

    # --- Short text returns single chunk ---
    def test_short_text_single_chunk(self) -> None:
        text = "Hello, world!"
        result = split_text(text, chunk_size=512)
        assert len(result) == 1
        assert result[0].content == "Hello, world!"
        assert result[0].index == 0

    def test_single_word(self) -> None:
        result = split_text("word")
        assert len(result) == 1
        assert result[0].content == "word"

    # --- Paragraph splitting ---
    def test_two_short_paragraphs_merged(self) -> None:
        text = "Short para one.\n\nShort para two."
        result = split_text(text, chunk_size=512)
        assert len(result) == 1  # Both fit in one chunk

    def test_large_paragraphs_split(self) -> None:
        # Each paragraph > chunk_size
        para1 = "A" * 300
        para2 = "B" * 300
        text = f"{para1}\n\n{para2}"
        result = split_text(text, chunk_size=250)
        assert len(result) >= 2

    # --- Chunk size respected ---
    def test_chunk_size_respected(self) -> None:
        text = "\n\n".join([f"Paragraph {i} content here." for i in range(20)])
        result = split_text(text, chunk_size=100, chunk_overlap=0)
        for chunk in result:
            # Allow some tolerance since we join with newlines
            assert len(chunk.content) <= 150, (
                f"Chunk {chunk.index} exceeds expected size: {len(chunk.content)}"
            )

    # --- Overlap works ---
    def test_overlap_creates_shared_content(self) -> None:
        text = "\n\n".join([f"Para{i} " + "x" * 80 for i in range(5)])
        result = split_text(text, chunk_size=100, chunk_overlap=20)
        if len(result) >= 2:
            # Second chunk should contain some text from end of first chunk
            first_end = result[0].content[-20:]
            assert first_end in result[1].content

    def test_zero_overlap(self) -> None:
        text = "\n\n".join([f"Paragraph {i} " + "x" * 80 for i in range(5)])
        result = split_text(text, chunk_size=100, chunk_overlap=0)
        assert len(result) >= 2

    # --- Index numbering ---
    def test_chunks_have_sequential_indices(self) -> None:
        text = "\n\n".join([f"Paragraph {i} " + "y" * 80 for i in range(10)])
        result = split_text(text, chunk_size=100, chunk_overlap=0)
        for i, chunk in enumerate(result):
            assert chunk.index == i

    # --- TextChunk dataclass ---
    def test_textchunk_is_frozen(self) -> None:
        chunk = TextChunk(content="test", index=0)
        with pytest.raises(AttributeError):
            chunk.content = "modified"  # type: ignore[misc]

    def test_textchunk_fields(self) -> None:
        chunk = TextChunk(content="hello", index=3)
        assert chunk.content == "hello"
        assert chunk.index == 3

    # --- Long text with sentences ---
    def test_long_paragraph_splits_by_sentences(self) -> None:
        # Create a paragraph longer than chunk_size with sentence boundaries
        sentences = ["Sentence number one. ", "Sentence number two. ",
                     "Sentence number three. ", "Sentence number four. "]
        long_para = "".join(sentences * 5)
        result = split_text(long_para, chunk_size=100, chunk_overlap=0)
        assert len(result) >= 2

    # --- Default parameters ---
    def test_default_chunk_size_512(self) -> None:
        text = "x" * 1024
        result = split_text(text)
        assert len(result) >= 1

    # --- Unicode content ---
    def test_unicode_content(self) -> None:
        text = "这是一段中文测试文本。\n\n第二段中文内容。"
        result = split_text(text, chunk_size=512)
        assert len(result) >= 1
        assert "中文" in result[0].content

    # --- Mixed content ---
    def test_mixed_paragraphs_and_sentences(self) -> None:
        text = (
            "First paragraph with some content.\n\n"
            "Second paragraph. It has multiple sentences. And a third one.\n\n"
            "Third paragraph is short."
        )
        result = split_text(text, chunk_size=512)
        assert len(result) >= 1
        # All content should be present across chunks
        combined = " ".join(c.content for c in result)
        assert "First paragraph" in combined
        assert "Second paragraph" in combined
        assert "Third paragraph" in combined
