import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    markdown: str
    converter: str
    quality: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)


def validate_markdown_conversion(markdown: str, source_size: int = 0) -> Dict[str, Any]:
    text = markdown or ""
    stripped = text.strip()
    issues = []

    if not stripped:
        issues.append("转换结果为空")

    replacement_count = text.count("\ufffd")
    replacement_ratio = replacement_count / max(len(text), 1)
    if replacement_ratio > 0.01:
        issues.append("疑似存在较多乱码字符")

    table_count = text.count("\n|")
    heading_count = sum(1 for line in text.splitlines() if line.startswith("#"))

    if source_size > 4096 and len(stripped) < 80:
        issues.append("转换结果字符数异常偏少")

    score = 1.0
    if not stripped:
        score = 0.0
    else:
        score -= min(replacement_ratio * 10, 0.4)
        if len(stripped) < 80 and source_size > 4096:
            score -= 0.3
        if issues:
            score -= 0.2
    score = max(0.0, round(score, 2))

    return {
        "is_usable": bool(stripped) and score >= 0.5,
        "score": score,
        "chars": len(text),
        "headings": heading_count,
        "tables": table_count,
        "issues": issues,
    }


def convert_document_to_markdown(file_path: str, file_type: str) -> ConversionResult:
    source_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    warnings = []

    if file_type in ("txt", "md"):
        markdown = _read_plain_text(file_path)
        return ConversionResult(
            markdown=markdown,
            converter="plain_text",
            quality=validate_markdown_conversion(markdown, source_size),
        )

    try:
        result = _convert_with_docling(file_path, file_type)
        quality = validate_markdown_conversion(result.markdown, source_size)
        if quality["is_usable"]:
            result.quality = quality
            return result
        warnings.extend(result.warnings)
        warnings.extend(quality.get("issues", []))
        logger.warning("Docling conversion quality check failed for %s: %s", file_path, warnings)
    except Exception as exc:
        warnings.append(str(exc))
        logger.warning("Docling conversion failed for %s: %s", file_path, exc)

    markdown = _extract_with_legacy_pipeline(file_path, file_type)
    quality = validate_markdown_conversion(markdown, source_size)
    return ConversionResult(
        markdown=markdown,
        converter="legacy",
        quality=quality,
        warnings=warnings,
    )


def _convert_with_docling(file_path: str, file_type: str) -> ConversionResult:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise RuntimeError("docling 未安装，已回退到旧版解析流程") from exc

    converter = DocumentConverter()
    converted = converter.convert(file_path)
    markdown = converted.document.export_to_markdown()
    return ConversionResult(
        markdown=markdown,
        converter="docling",
        quality={},
    )


def _extract_with_legacy_pipeline(file_path: str, file_type: str) -> str:
    from app.services.document import extract_text

    return extract_text(file_path, file_type)


def _read_plain_text(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
