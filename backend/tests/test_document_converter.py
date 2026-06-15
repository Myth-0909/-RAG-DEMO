from pathlib import Path

from app.services.document_converter import (
    ConversionResult,
    convert_document_to_markdown,
    validate_markdown_conversion,
)


def test_convert_document_to_markdown_uses_docling_when_available(monkeypatch, tmp_path):
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"%PDF")

    def fake_docling_convert(file_path: str, file_type: str):
        assert file_path == str(source)
        assert file_type == "pdf"
        return ConversionResult(
            markdown="# Title\n\n| A | B |\n| --- | --- |\n| 1 | 2 |",
            converter="docling",
            quality={"is_usable": True},
        )

    monkeypatch.setattr(
        "app.services.document_converter._convert_with_docling",
        fake_docling_convert,
    )

    result = convert_document_to_markdown(str(source), "pdf")

    assert result.converter == "docling"
    assert result.markdown.startswith("# Title")
    assert result.quality["is_usable"] is True


def test_convert_document_to_markdown_falls_back_to_legacy_extractor(monkeypatch, tmp_path):
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"%PDF")

    def fake_docling_convert(file_path: str, file_type: str):
        raise RuntimeError("docling unavailable")

    def fake_legacy_extract(file_path: str, file_type: str):
        return "legacy text"

    monkeypatch.setattr(
        "app.services.document_converter._convert_with_docling",
        fake_docling_convert,
    )
    monkeypatch.setattr(
        "app.services.document_converter._extract_with_legacy_pipeline",
        fake_legacy_extract,
    )

    result = convert_document_to_markdown(str(source), "pdf")

    assert result.converter == "legacy"
    assert result.markdown == "legacy text"
    assert result.warnings == ["docling unavailable"]


def test_validate_markdown_conversion_flags_empty_content():
    quality = validate_markdown_conversion("", source_size=1024)

    assert quality["is_usable"] is False
    assert "转换结果为空" in quality["issues"]
