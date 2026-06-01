"""
Intelligent content analyzer for automatic cleaning and chunking strategy selection.

Analyzes document content characteristics and recommends the optimal chunking strategy:
- parent_child: Structured documents with clear sections/headings
- semantic: Narrative/dense text with topic flow
- recursive: Short or simple documents
- hybrid: Mixed content with both structured and narrative sections
"""

import re
from typing import Dict, Any, Tuple, List
from dataclasses import dataclass


@dataclass
class ContentProfile:
    """Profile of analyzed document content."""
    total_chars: int
    total_sentences: int
    total_paragraphs: int
    heading_count: int
    section_count: int
    list_count: int
    table_count: int
    code_block_count: int
    avg_sentence_length: float
    avg_paragraph_length: float
    structure_score: float  # 0-1: how structured the document is
    narrative_score: float  # 0-1: how narrative/flowing the text is
    density_score: float    # 0-1: information density
    recommended_strategy: str
    reasoning: str


# Regex patterns for content analysis
HEADING_PATTERNS = [
    re.compile(r'^#{1,6}\s+.+', re.MULTILINE),           # Markdown headings
    re.compile(r'^[一二三四五六七八九十]+[、.]\s*.+', re.MULTILINE),  # Chinese numbered sections
    re.compile(r'^第[一二三四五六七八九十\d]+[章节部分]', re.MULTILINE),  # Chapter markers
    re.compile(r'^\d+\.\d*\s+[A-Z\u4e00-\u9fff]', re.MULTILINE),  # Numbered sections
    re.compile(r'^[A-Z][A-Z\s]{3,}$', re.MULTILINE),      # ALL CAPS headings
]

LIST_PATTERNS = [
    re.compile(r'^[\s]*[-*•]\s+.+', re.MULTILINE),        # Bullet lists
    re.compile(r'^[\s]*\d+[.)]\s+.+', re.MULTILINE),      # Numbered lists
    re.compile(r'^[\s]*[a-zA-Z][.)]\s+.+', re.MULTILINE), # Lettered lists
]

TABLE_PATTERN = re.compile(r'\|.*\|.*\|', re.MULTILINE)
CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```|`[^`]+`')
URL_PATTERN = re.compile(r'https?://\S+')
EMAIL_PATTERN = re.compile(r'\S+@\S+\.\S+')


def clean_content(text: str, file_type: str = "") -> Tuple[str, Dict[str, Any]]:
    """
    Clean document content while preserving original meaning.

    Returns:
        Tuple of (cleaned_text, cleaning_report)
    """
    original_length = len(text)
    cleaning_report = {
        "whitespace_normalized": 0,
        "encoding_fixed": 0,
        "artifacts_removed": 0,
        "original_chars": original_length,
    }

    # Fix common encoding issues
    replacements = {
        "\u00a0": " ",       # Non-breaking space
        "\u200b": "",        # Zero-width space
        "\u200c": "",        # Zero-width non-joiner
        "\u200d": "",        # Zero-width joiner
        "\ufeff": "",        # BOM
        "\u2028": "\n",      # Line separator
        "\u2029": "\n\n",    # Paragraph separator
        "\r\n": "\n",        # Windows line endings
        "\r": "\n",          # Old Mac line endings
        "\t": "    ",        # Tabs to spaces
    }

    for old, new in replacements.items():
        count = text.count(old)
        if count > 0:
            text = text.replace(old, new)
            cleaning_report["encoding_fixed"] += count

    # Normalize excessive whitespace
    text, ws_count = re.subn(r'[ \t]+', ' ', text)
    cleaning_report["whitespace_normalized"] += ws_count

    # Normalize excessive blank lines (keep max 2)
    text, blank_count = re.subn(r'\n{4,}', '\n\n\n', text)
    cleaning_report["whitespace_normalized"] += blank_count

    # Remove PDF artifacts
    if file_type == "pdf":
        # Remove page numbers at line boundaries
        text, page_count = re.subn(r'\n\s*\d+\s*\n', '\n', text)
        cleaning_report["artifacts_removed"] += page_count

        # Remove "Page X of Y" patterns
        text, page_count2 = re.subn(r'(?:第\s*\d+\s*页\s*共\s*\d+\s*页|Page\s*\d+\s*of\s*\d+)', '', text, flags=re.IGNORECASE)
        cleaning_report["artifacts_removed"] += page_count2

        # Fix hyphenated words split across lines
        text, hyphen_count = re.subn(r'(\w+)-\n\s*(\w+)', r'\1\2', text)
        cleaning_report["artifacts_removed"] += hyphen_count

    # Remove trailing whitespace per line
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)

    # Strip leading/trailing whitespace
    text = text.strip()

    cleaning_report["cleaned_chars"] = len(text)
    cleaning_report["chars_removed"] = original_length - len(text)

    return text, cleaning_report


def analyze_content(text: str, file_type: str = "") -> ContentProfile:
    """
    Analyze document content to determine optimal chunking strategy.
    """
    if not text.strip():
        return ContentProfile(
            total_chars=0, total_sentences=0, total_paragraphs=0,
            heading_count=0, section_count=0, list_count=0, table_count=0,
            code_block_count=0, avg_sentence_length=0, avg_paragraph_length=0,
            structure_score=0, narrative_score=0, density_score=0,
            recommended_strategy="recursive", reasoning="空文档，使用默认策略",
        )

    # Basic metrics
    total_chars = len(text)

    # Sentences (Chinese + English)
    sentence_endings = re.compile(r'[。！？.!?\n]+')
    sentences = [s.strip() for s in sentence_endings.split(text) if s.strip()]
    total_sentences = max(len(sentences), 1)
    avg_sentence_length = total_chars / total_sentences if total_sentences > 0 else 0

    # Paragraphs
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    total_paragraphs = max(len(paragraphs), 1)
    avg_paragraph_length = sum(len(p) for p in paragraphs) / total_paragraphs

    # Structural elements
    heading_count = sum(len(p.findall(text)) for p in HEADING_PATTERNS)
    list_count = sum(len(p.findall(text)) for p in LIST_PATTERNS)
    table_count = len(TABLE_PATTERN.findall(text))
    code_block_count = len(CODE_BLOCK_PATTERN.findall(text))

    # Section detection (consecutive headings or clear section breaks)
    section_markers = re.findall(
        r'(?:^#{1,3}\s|^[一二三四五六七八九十]+[、.]|^第[一二三四五六七八九十\d]+[章节])',
        text, re.MULTILINE
    )
    section_count = len(section_markers)

    # Calculate scores
    structure_score = _calculate_structure_score(
        total_chars, heading_count, section_count, list_count,
        table_count, code_block_count, total_paragraphs,
    )

    narrative_score = _calculate_narrative_score(
        avg_sentence_length, avg_paragraph_length, heading_count,
        total_sentences, total_paragraphs, structure_score,
    )

    density_score = _calculate_density_score(
        total_chars, total_sentences, total_paragraphs,
        heading_count, list_count,
    )

    # Determine strategy
    strategy, reasoning = _recommend_strategy(
        total_chars=total_chars,
        structure_score=structure_score,
        narrative_score=narrative_score,
        density_score=density_score,
        heading_count=heading_count,
        section_count=section_count,
        total_paragraphs=total_paragraphs,
        avg_paragraph_length=avg_paragraph_length,
        file_type=file_type,
    )

    return ContentProfile(
        total_chars=total_chars,
        total_sentences=total_sentences,
        total_paragraphs=total_paragraphs,
        heading_count=heading_count,
        section_count=section_count,
        list_count=list_count,
        table_count=table_count,
        code_block_count=code_block_count,
        avg_sentence_length=round(avg_sentence_length, 1),
        avg_paragraph_length=round(avg_paragraph_length, 1),
        structure_score=round(structure_score, 3),
        narrative_score=round(narrative_score, 3),
        density_score=round(density_score, 3),
        recommended_strategy=strategy,
        reasoning=reasoning,
    )


def _calculate_structure_score(
    total_chars: int, heading_count: int, section_count: int,
    list_count: int, table_count: int, code_block_count: int,
    total_paragraphs: int,
) -> float:
    """Score 0-1: how structured/organized the document is."""
    score = 0.0

    # Headings per 1000 chars
    heading_density = heading_count / max(total_chars / 1000, 1)
    score += min(heading_density * 0.15, 0.3)

    # Sections
    section_density = section_count / max(total_chars / 1000, 1)
    score += min(section_density * 0.12, 0.25)

    # Lists
    list_density = list_count / max(total_paragraphs, 1)
    score += min(list_density * 0.1, 0.2)

    # Tables
    if table_count > 0:
        score += min(table_count * 0.08, 0.15)

    # Code blocks
    if code_block_count > 0:
        score += min(code_block_count * 0.05, 0.1)

    # Paragraph count (more paragraphs = more structure)
    if total_paragraphs > 10:
        score += 0.05
    elif total_paragraphs > 20:
        score += 0.1

    return min(score, 1.0)


def _calculate_narrative_score(
    avg_sentence_length: float, avg_paragraph_length: float,
    heading_count: int, total_sentences: int, total_paragraphs: int,
    structure_score: float,
) -> float:
    """Score 0-1: how much the text flows as continuous narrative."""
    score = 0.0

    # Long sentences suggest narrative flow
    if avg_sentence_length > 30:
        score += 0.2
    elif avg_sentence_length > 20:
        score += 0.15
    elif avg_sentence_length > 10:
        score += 0.1

    # Long paragraphs suggest narrative
    if avg_paragraph_length > 300:
        score += 0.25
    elif avg_paragraph_length > 150:
        score += 0.15
    elif avg_paragraph_length > 80:
        score += 0.1

    # Few headings relative to paragraphs = narrative
    if total_paragraphs > 0:
        heading_ratio = heading_count / total_paragraphs
        if heading_ratio < 0.1:
            score += 0.25
        elif heading_ratio < 0.2:
            score += 0.15

    # Many sentences relative to paragraphs
    if total_paragraphs > 0:
        sentences_per_para = total_sentences / total_paragraphs
        if sentences_per_para > 5:
            score += 0.15
        elif sentences_per_para > 3:
            score += 0.1

    # Inverse relationship with structure
    score += max(0, 0.15 - structure_score * 0.15)

    return min(score, 1.0)


def _calculate_density_score(
    total_chars: int, total_sentences: int, total_paragraphs: int,
    heading_count: int, list_count: int,
) -> float:
    """Score 0-1: information density (mixed content types)."""
    score = 0.0

    # Mix of content types
    content_types = sum([
        heading_count > 0,
        list_count > 0,
        total_paragraphs > 3,
        total_sentences > total_paragraphs * 2,
    ])
    score += content_types * 0.15

    # Moderate paragraph lengths (not too long, not too short)
    avg_para = total_chars / max(total_paragraphs, 1)
    if 50 < avg_para < 200:
        score += 0.2

    # Ratio of sentences to paragraphs
    if total_paragraphs > 0:
        ratio = total_sentences / total_paragraphs
        if 2 < ratio < 6:
            score += 0.2

    return min(score, 1.0)


def _recommend_strategy(
    total_chars: int,
    structure_score: float,
    narrative_score: float,
    density_score: float,
    heading_count: int,
    section_count: int,
    total_paragraphs: int,
    avg_paragraph_length: float,
    file_type: str,
) -> Tuple[str, str]:
    """
    Recommend chunking strategy based on content profile.

    Returns:
        Tuple of (strategy_name, reasoning_text)
    """
    # Very short documents: simple recursive chunking
    if total_chars < 1000:
        return "recursive", "文档较短，使用递归字符分块即可保证完整性"

    # High structure: parent-child chunking preserves hierarchy
    if structure_score >= 0.5 and heading_count >= 3:
        return "parent_child", (
            f"检测到 {heading_count} 个标题和 {section_count} 个章节，"
            f"文档结构清晰（结构评分 {structure_score:.2f}），"
            f"使用父子分块保留层级上下文"
        )

    # High narrative: semantic chunking groups by meaning
    if narrative_score >= 0.5 and structure_score < 0.3:
        return "semantic", (
            f"文档以叙述为主（叙事评分 {narrative_score:.2f}，结构评分 {structure_score:.2f}），"
            f"使用语义分块按主题相关性聚合内容"
        )

    # Mixed content: hybrid strategy
    if density_score >= 0.4 and structure_score >= 0.2:
        return "hybrid", (
            f"文档内容混合（密度评分 {density_score:.2f}，结构评分 {structure_score:.2f}），"
            f"使用混合分块：结构化部分用父子分块，叙述部分用语义分块"
        )

    # Long documents with moderate structure
    if total_chars > 5000 and structure_score >= 0.25:
        return "parent_child", (
            f"文档较长（{total_chars} 字符）且有一定结构（{heading_count} 个标题），"
            f"使用父子分块兼顾上下文和检索精度"
        )

    # Long narrative documents
    if total_chars > 5000 and narrative_score >= 0.35:
        return "semantic", (
            f"文档较长（{total_chars} 字符）且以叙述为主，"
            f"使用语义分块保持主题连贯性"
        )

    # Default: recursive
    return "recursive", (
        f"文档特征不明显（结构 {structure_score:.2f}，叙事 {narrative_score:.2f}，"
        f"密度 {density_score:.2f}），使用通用递归分块"
    )


def get_analysis_summary(profile: ContentProfile) -> Dict[str, Any]:
    """Convert content profile to a JSON-serializable summary for metadata."""
    strategy_labels = {
        "fixed": "固定大小分块",
        "recursive": "递归字符分块",
        "parent_child": "父子分块",
        "semantic": "语义分块",
        "hybrid": "混合分块",
    }

    return {
        "content_analysis": {
            "total_chars": profile.total_chars,
            "total_sentences": profile.total_sentences,
            "total_paragraphs": profile.total_paragraphs,
            "headings": profile.heading_count,
            "sections": profile.section_count,
            "lists": profile.list_count,
            "tables": profile.table_count,
            "code_blocks": profile.code_block_count,
            "avg_sentence_length": profile.avg_sentence_length,
            "avg_paragraph_length": profile.avg_paragraph_length,
        },
        "scores": {
            "structure": profile.structure_score,
            "narrative": profile.narrative_score,
            "density": profile.density_score,
        },
        "strategy": {
            "selected": profile.recommended_strategy,
            "label": strategy_labels.get(profile.recommended_strategy, profile.recommended_strategy),
            "reasoning": profile.reasoning,
        },
    }
