"""
Intelligent content analyzer for automatic cleaning and chunking strategy selection.

Design principle: analyze content FIRST, then let data drive the decision.
- Measure heading hierarchy depth (not just count)
- Measure content per section (short sections don't need parent-child)
- Distinguish flat structure (many same-level headings) from nested hierarchy

Strategies:
- recursive: Default for most documents, especially flat/short ones
- parent_child: Only for documents with true multi-level heading hierarchy
- semantic: For narrative-heavy text with topic flow
- hybrid: For documents mixing structured and narrative sections
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
    heading_levels: int        # number of distinct heading levels (e.g. #, ##, ### = 3)
    section_count: int
    avg_section_chars: float    # average content length per section
    list_count: int
    table_count: int
    image_count: int
    code_block_count: int
    avg_sentence_length: float
    avg_paragraph_length: float
    structure_score: float
    narrative_score: float
    density_score: float
    hierarchy_score: float     # 0-1: how deeply nested the heading hierarchy is
    recommended_strategy: str
    reasoning: str


# === Markdown heading detection ===
MD_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)', re.MULTILINE)

# === Structural heading patterns (NOT just numbered paragraphs) ===
# Only count as headings if they look like actual section titles
STRUCTURED_HEADING_PATTERNS = [
    MD_HEADING_RE,                                                    # Markdown # headings
    re.compile(r'^第[一二三四五六七八九十\d]+[章节部分]\s*.+', re.MULTILINE),  # 第一章 / 第1节
    re.compile(r'^[一二三四五六七八九十]+[、]\s*.{2,}', re.MULTILINE),  # 一、标题（至少2字内容）
]

# === Numeric hierarchical heading patterns (e.g. "5 xxx", "5.1 xxxx", "5.1.1 xxx") ===
NUMERIC_HEADING_L1_RE = re.compile(r'^(\d+)\s+\S.{1,}', re.MULTILINE)
NUMERIC_HEADING_L2_RE = re.compile(r'^(\d+\.\d+)\s+\S.{1,}', re.MULTILINE)
NUMERIC_HEADING_L3_RE = re.compile(r'^(\d+\.\d+\.\d+)\s+\S.{1,}', re.MULTILINE)
NUMERIC_HEADING_ALL_RE = re.compile(
    r'^(\d+(?:\.\d+){0,2})\s+\S.{1,}', re.MULTILINE
)

# === List detection ===
LIST_PATTERNS = [
    re.compile(r'^[\s]*[-*•]\s+.+', re.MULTILINE),
    re.compile(r'^[\s]*\d+[.)]\s+.+', re.MULTILINE),
    re.compile(r'^[\s]*[a-zA-Z][.)]\s+.+', re.MULTILINE),
]

TABLE_PATTERN = re.compile(r'\|.*\|.*\|', re.MULTILINE)
EXTRACTED_TABLE_PATTERN = re.compile(r'\[表格[^\]]*\]', re.MULTILINE)
EXTRACTED_IMAGE_PATTERN = re.compile(r'\[图片[^\]]*\]', re.MULTILINE)
CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```')


def clean_content(text: str, file_type: str = "") -> Tuple[str, Dict[str, Any]]:
    """Clean document content while preserving original meaning."""
    original_length = len(text)
    report = {
        "whitespace_normalized": 0,
        "encoding_fixed": 0,
        "artifacts_removed": 0,
        "original_chars": original_length,
    }

    replacements = {
        "\u00a0": " ", "\u200b": "", "\u200c": "", "\u200d": "",
        "\ufeff": "", "\u2028": "\n", "\u2029": "\n\n",
        "\r\n": "\n", "\r": "\n", "\t": "    ",
    }
    for old, new in replacements.items():
        count = text.count(old)
        if count > 0:
            text = text.replace(old, new)
            report["encoding_fixed"] += count

    text, n = re.subn(r'[ \t]+', ' ', text)
    report["whitespace_normalized"] += n
    text, n = re.subn(r'\n{4,}', '\n\n\n', text)
    report["whitespace_normalized"] += n

    if file_type == "pdf":
        text, n = re.subn(r'\n\s*\d+\s*\n', '\n', text)
        report["artifacts_removed"] += n
        text, n = re.subn(r'(?:第\s*\d+\s*页\s*共\s*\d+\s*页|Page\s*\d+\s*of\s*\d+)', '', text, flags=re.IGNORECASE)
        report["artifacts_removed"] += n
        text, n = re.subn(r'(\w+)-\n\s*(\w+)', r'\1\2', text)
        report["artifacts_removed"] += n

    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
    text = text.strip()

    report["cleaned_chars"] = len(text)
    report["chars_removed"] = original_length - len(text)
    return text, report


def analyze_content(text: str, file_type: str = "") -> ContentProfile:
    """
    Analyze document content to determine optimal chunking strategy.

    Approach: measure actual content characteristics first, then decide.
    """
    if not text.strip():
        return ContentProfile(
            total_chars=0, total_sentences=0, total_paragraphs=0,
            heading_count=0, heading_levels=0, section_count=0,
            avg_section_chars=0, list_count=0, table_count=0, image_count=0,
            code_block_count=0, avg_sentence_length=0, avg_paragraph_length=0,
            structure_score=0, narrative_score=0, density_score=0,
            hierarchy_score=0,
            recommended_strategy="recursive", reasoning="空文档，使用默认策略",
        )

    total_chars = len(text)

    # --- Sentences ---
    sentences = [s.strip() for s in re.split(r'[。！？.!?\n]+', text) if s.strip()]
    total_sentences = max(len(sentences), 1)
    avg_sentence_length = total_chars / total_sentences

    # --- Paragraphs ---
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    total_paragraphs = max(len(paragraphs), 1)
    avg_paragraph_length = sum(len(p) for p in paragraphs) / total_paragraphs

    # --- Heading analysis (the key improvement) ---
    md_headings = MD_HEADING_RE.findall(text)  # [(level_str, title), ...]
    heading_count = len(md_headings)

    # Extract heading levels for hierarchy analysis
    if md_headings:
        levels = set(len(h[0]) for h in md_headings)  # e.g. {1, 2, 3}
        heading_levels = len(levels)
        max_level = max(levels)
        min_level = min(levels)
        level_span = max_level - min_level
    else:
        heading_levels = 0
        level_span = 0

    # --- Numeric hierarchical headings (e.g. "5 xxx", "5.1 xxxx", "5.1.1 xxx") ---
    numeric_headings = NUMERIC_HEADING_ALL_RE.findall(text)
    if numeric_headings:
        numeric_levels = set()
        for num_str in numeric_headings:
            depth = num_str.count('.') + 1
            numeric_levels.add(depth)
        heading_count += len(numeric_headings)
        if not md_headings:
            heading_levels = len(numeric_levels)
            if numeric_levels:
                max_level = max(numeric_levels)
                min_level = min(numeric_levels)
                level_span = max_level - min_level
        else:
            all_levels = levels | numeric_levels
            heading_levels = len(all_levels)
            max_level = max(all_levels)
            min_level = min(all_levels)
            level_span = max_level - min_level

    # Count non-markdown structural headings
    non_md_headings = 0
    for pat in STRUCTURED_HEADING_PATTERNS[1:]:  # skip MD_HEADING_RE
        non_md_headings += len(pat.findall(text))
    heading_count += non_md_headings

    # --- Section splitting (for measuring content per section) ---
    section_splits = re.split(
        r'(?:^#{1,6}\s+.+|^第[一二三四五六七八九十\d]+[章节部分]\s*.+|^[一二三四五六七八九十]+[、]\s*.+|^\d+(?:\.\d+){0,2}\s+\S.+)',
        text, flags=re.MULTILINE
    )
    section_bodies = [s.strip() for s in section_splits if s.strip()]
    section_count = max(len(section_bodies), 1)
    avg_section_chars = total_chars / section_count

    # --- Other structural elements ---
    list_count = sum(len(p.findall(text)) for p in LIST_PATTERNS)
    md_table_count = len(TABLE_PATTERN.findall(text))
    extracted_table_count = len(EXTRACTED_TABLE_PATTERN.findall(text))
    table_count = max(md_table_count // 3, extracted_table_count)
    image_count = len(EXTRACTED_IMAGE_PATTERN.findall(text))
    code_block_count = len(CODE_BLOCK_PATTERN.findall(text))

    # --- Calculate scores ---
    hierarchy_score = _calculate_hierarchy_score(
        heading_levels, level_span, heading_count, total_paragraphs,
    )

    structure_score = _calculate_structure_score(
        total_chars, heading_count, section_count, list_count,
        table_count, code_block_count, total_paragraphs, hierarchy_score,
    )

    narrative_score = _calculate_narrative_score(
        avg_sentence_length, avg_paragraph_length, heading_count,
        total_sentences, total_paragraphs, structure_score,
    )

    density_score = _calculate_density_score(
        total_chars, total_sentences, total_paragraphs,
        heading_count, list_count,
    )

    # --- Determine strategy based on content ---
    strategy, reasoning = _recommend_strategy(
        total_chars=total_chars,
        structure_score=structure_score,
        narrative_score=narrative_score,
        density_score=density_score,
        hierarchy_score=hierarchy_score,
        heading_count=heading_count,
        heading_levels=heading_levels,
        section_count=section_count,
        avg_section_chars=avg_section_chars,
        total_paragraphs=total_paragraphs,
        avg_paragraph_length=avg_paragraph_length,
        table_count=table_count,
    )

    return ContentProfile(
        total_chars=total_chars,
        total_sentences=total_sentences,
        total_paragraphs=total_paragraphs,
        heading_count=heading_count,
        heading_levels=heading_levels,
        section_count=section_count,
        avg_section_chars=round(avg_section_chars, 1),
        list_count=list_count,
        table_count=table_count,
        code_block_count=code_block_count,
        image_count=image_count,
        avg_sentence_length=round(avg_sentence_length, 1),
        avg_paragraph_length=round(avg_paragraph_length, 1),
        structure_score=round(structure_score, 3),
        narrative_score=round(narrative_score, 3),
        density_score=round(density_score, 3),
        hierarchy_score=round(hierarchy_score, 3),
        recommended_strategy=strategy,
        reasoning=reasoning,
    )


def _calculate_hierarchy_score(
    heading_levels: int,
    level_span: int,
    heading_count: int,
    total_paragraphs: int,
) -> float:
    """
    Score 0-1: how deeply nested the heading hierarchy is.

    This is the KEY differentiator:
    - Flat documents (all ##) → low score → recursive
    - Hierarchical documents (# > ## > ###) → high score → parent_child
    """
    if heading_count == 0:
        return 0.0

    score = 0.0

    # Multiple heading levels = true hierarchy
    if heading_levels >= 3:
        score += 0.5
    elif heading_levels == 2:
        score += 0.3
    else:
        # Single level = flat, even with many headings
        score += 0.05

    # Level span (difference between deepest and shallowest)
    if level_span >= 2:
        score += 0.25
    elif level_span == 1:
        score += 0.1

    # Headings that actually organize content (not just labels)
    if total_paragraphs > 0:
        heading_ratio = heading_count / total_paragraphs
        if 0.05 < heading_ratio < 0.5:
            score += 0.15
        elif heading_ratio >= 0.5:
            # Too many headings relative to content = flat list, not hierarchy
            score += 0.05

    return min(score, 1.0)


def _calculate_structure_score(
    total_chars: int, heading_count: int, section_count: int,
    list_count: int, table_count: int, code_block_count: int,
    total_paragraphs: int, hierarchy_score: float,
) -> float:
    """Score 0-1: how structured/organized the document is."""
    score = 0.0

    # Heading density (capped lower to avoid inflation)
    heading_density = heading_count / max(total_chars / 1000, 1)
    score += min(heading_density * 0.08, 0.15)

    # Section density (capped lower)
    section_density = section_count / max(total_chars / 1000, 1)
    score += min(section_density * 0.06, 0.12)

    # Lists
    list_density = list_count / max(total_paragraphs, 1)
    score += min(list_density * 0.08, 0.15)

    # Tables
    if table_count > 0:
        score += min(table_count * 0.06, 0.12)

    # Code blocks
    if code_block_count > 0:
        score += min(code_block_count * 0.05, 0.1)

    # Boost from actual hierarchy (not just heading count)
    score += hierarchy_score * 0.2

    return min(score, 1.0)


def _calculate_narrative_score(
    avg_sentence_length: float, avg_paragraph_length: float,
    heading_count: int, total_sentences: int, total_paragraphs: int,
    structure_score: float,
) -> float:
    """Score 0-1: how much the text flows as continuous narrative."""
    score = 0.0

    if avg_sentence_length > 30:
        score += 0.2
    elif avg_sentence_length > 20:
        score += 0.15
    elif avg_sentence_length > 10:
        score += 0.1

    if avg_paragraph_length > 300:
        score += 0.25
    elif avg_paragraph_length > 150:
        score += 0.15
    elif avg_paragraph_length > 80:
        score += 0.1

    if total_paragraphs > 0:
        heading_ratio = heading_count / total_paragraphs
        if heading_ratio < 0.1:
            score += 0.25
        elif heading_ratio < 0.2:
            score += 0.15

    if total_paragraphs > 0:
        sentences_per_para = total_sentences / total_paragraphs
        if sentences_per_para > 5:
            score += 0.15
        elif sentences_per_para > 3:
            score += 0.1

    score += max(0, 0.15 - structure_score * 0.15)

    return min(score, 1.0)


def _calculate_density_score(
    total_chars: int, total_sentences: int, total_paragraphs: int,
    heading_count: int, list_count: int,
) -> float:
    """Score 0-1: information density (mixed content types)."""
    score = 0.0

    content_types = sum([
        heading_count > 0,
        list_count > 0,
        total_paragraphs > 3,
        total_sentences > total_paragraphs * 2,
    ])
    score += content_types * 0.12

    avg_para = total_chars / max(total_paragraphs, 1)
    if 50 < avg_para < 200:
        score += 0.15

    if total_paragraphs > 0:
        ratio = total_sentences / total_paragraphs
        if 2 < ratio < 6:
            score += 0.15

    return min(score, 1.0)


def _recommend_strategy(
    total_chars: int,
    structure_score: float,
    narrative_score: float,
    density_score: float,
    hierarchy_score: float,
    heading_count: int,
    heading_levels: int,
    section_count: int,
    avg_section_chars: float,
    total_paragraphs: int,
    avg_paragraph_length: float,
    table_count: int,
) -> Tuple[str, str]:
    """
    Recommend chunking strategy based on content analysis.

    Decision logic:
    1. Check document size (short → recursive)
    2. Check hierarchy depth (parent_child needs true multi-level headings)
    3. Check narrative flow (semantic for flowing text)
    4. Check content mix (hybrid for mixed types)
    5. Default to recursive
    """
    # --- Short documents: always recursive ---
    if total_chars < 1000:
        return "recursive", (
            f"文档较短（{total_chars} 字符），递归分块即可保证完整性"
        )

    # --- Parent-child: requires TRUE hierarchy ---
    # Must have: multiple heading levels AND sections with enough content
    has_hierarchy = heading_levels >= 2 and hierarchy_score >= 0.3
    # The deeper the hierarchy, the lower the avg_section_chars threshold:
    # deep hierarchies naturally create many small sections, but parent-child
    # is still the right strategy because it preserves the nesting context.
    if hierarchy_score >= 0.6:
        min_section_chars = 50
    elif hierarchy_score >= 0.4:
        min_section_chars = 100
    else:
        min_section_chars = 150
    has_substantial_sections = avg_section_chars > min_section_chars

    if has_hierarchy and has_substantial_sections:
        return "parent_child", (
            f"文档具有 {heading_levels} 层标题层级（{heading_count} 个标题），"
            f"平均章节 {avg_section_chars:.0f} 字符，"
            f"层级评分 {hierarchy_score:.2f}，使用父子分块保留层级上下文"
        )

    # --- Semantic: narrative-heavy documents ---
    if narrative_score >= 0.45 and hierarchy_score < 0.2:
        return "semantic", (
            f"文档以叙述为主（叙事评分 {narrative_score:.2f}，层级评分 {hierarchy_score:.2f}），"
            f"使用语义分块按主题相关性聚合内容"
        )

    # --- Hybrid: mixed structured + narrative content ---
    # Needs both structural elements AND narrative flow
    has_mixed = (
        density_score >= 0.35
        and structure_score >= 0.15
        and narrative_score >= 0.25
    )
    if has_mixed and total_chars > 3000:
        return "hybrid", (
            f"文档内容混合（密度 {density_score:.2f}，结构 {structure_score:.2f}，"
            f"叙事 {narrative_score:.2f}），使用混合分块"
        )

    # --- Long documents with tables but NO heading hierarchy ---
    # If heading_levels >= 2, parent_child already handled it above.
    # Only fall through to hybrid when there are tables without deep structure.
    if table_count > 0 and total_chars > 3000 and heading_levels < 2:
        return "hybrid", (
            f"文档包含 {table_count} 个表格（{total_chars} 字符），"
            f"但标题层级不足，使用混合分块分别处理表格和正文"
        )

    # --- Default: recursive ---
    # This is the correct choice for flat documents with same-level headings
    if heading_count > 0 and heading_levels <= 1:
        return "recursive", (
            f"文档有 {heading_count} 个标题但仅 {heading_levels} 层（扁平结构），"
            f"无需父子分块，使用递归字符分块"
        )

    return "recursive", (
        f"文档特征：{total_chars} 字符，{heading_count} 标题/"
        f"{heading_levels} 层，叙事 {narrative_score:.2f}，"
        f"使用通用递归分块"
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
            "heading_levels": profile.heading_levels,
            "sections": profile.section_count,
            "avg_section_chars": profile.avg_section_chars,
            "lists": profile.list_count,
            "tables": profile.table_count,
            "images": profile.image_count,
            "code_blocks": profile.code_block_count,
            "avg_sentence_length": profile.avg_sentence_length,
            "avg_paragraph_length": profile.avg_paragraph_length,
        },
        "scores": {
            "structure": profile.structure_score,
            "narrative": profile.narrative_score,
            "density": profile.density_score,
            "hierarchy": profile.hierarchy_score,
        },
        "strategy": {
            "selected": profile.recommended_strategy,
            "label": strategy_labels.get(profile.recommended_strategy, profile.recommended_strategy),
            "reasoning": profile.reasoning,
        },
    }
