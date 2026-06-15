import re
from typing import List, Dict, Any, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.embedding import embed_texts


# === Heading detection ===
_HEADING_PATTERNS = [
    re.compile(r'^#{1,6}\s+(.+)', re.MULTILINE),                        # Markdown headings
    re.compile(r'^第[一二三四五六七八九十\d]+[章节部分]\s*(.+)', re.MULTILINE),  # 第一章 xxx
    re.compile(r'^[一二三四五六七八九十]+[、.]\s*(.+)', re.MULTILINE),      # 一、xxx
    re.compile(r'^(\d+(?:\.\d+){0,2})\s+(.+)', re.MULTILINE),            # 1.1 xxx
]


def _extract_heading(text: str) -> Optional[str]:
    """Extract the first heading found in a text fragment."""
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        for pat in _HEADING_PATTERNS:
            m = pat.match(line)
            if m:
                # Return the full heading line (including numbering)
                return line
    return None


def _heading_path(text: str, current_heading: Optional[str] = None) -> str:
    """
    Build a heading path showing where this content belongs.
    Returns the best available heading context.
    """
    heading = _extract_heading(text)
    if heading and current_heading:
        return f"{current_heading} > {heading}"
    return heading or current_heading or ""


def _build_llm_heading_index(
    heading_boundaries: List[Dict[str, Any]] = None,
) -> Dict[str, Optional[str]]:
    """
    Build a heading→parent lookup from LLM heading_boundaries.
    Returns dict mapping heading text to its parent text (None for top-level).
    """
    index: Dict[str, Optional[str]] = {}
    if not heading_boundaries:
        return index
    for hb in heading_boundaries:
        parent = hb.get("parent", "")
        if parent:
            index[parent] = None  # top-level
        for child in hb.get("children", []):
            if child:
                index[child] = parent
    return index


def _resolve_heading(heading_text: str, llm_index: Dict[str, Optional[str]]) -> str:
    """
    Resolve a heading using the LLM's heading index.
    Strips markdown prefixes for flexible matching.
    Returns the full context path if found, otherwise the original heading.
    """
    if not heading_text or not llm_index:
        return heading_text
    clean = re.sub(r'^#{1,6}\s+', '', heading_text).strip()
    for key, parent in llm_index.items():
        key_clean = re.sub(r'^#{1,6}\s+', '', key).strip()
        if heading_text == key or clean == key_clean:
            if parent:
                return f"{parent} > {heading_text}"
            return heading_text
    return heading_text


# === Table detection for table-aware chunking ===
# Matches markdown tables (header row + separator row + data rows).
# Supports both standard format (with trailing |) and simplified format
# (without trailing |) produced by some converters.
_TABLE_BLOCK_RE = re.compile(
    r'('
    r'(?:\|[^\n]+\|\n\|[\s\-:|]+\|\n(?:\|[^\n]+\|\n?)+)'   # with trailing |
    r'|'
    r'(?:\|[^\n]+\n\|[\s\-:|]+\n(?:\|[^\n]+\n?)+)'          # without trailing |
    r')', re.MULTILINE
)


# === Split-table repair ===
# Docling sometimes breaks a single table across page boundaries,
# creating continuation tables whose "header" row is actually a data row
# (e.g. containing phone numbers, emails, dates). These patterns detect
# data-like rows so we can restore the correct header.

_DATA_ROW_INDICATORS = [
    re.compile(r'\d{3,4}[-\s]?\d{7,8}'),               # phone number
    re.compile(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}'),      # email
    re.compile(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}'),    # date
    re.compile(r'\d{10,}'),                              # long digit sequence (ID, phone)
]


def _is_data_like_row(row: str) -> bool:
    """Check if a table row looks like data (contains phone, email, date, etc.)."""
    for pat in _DATA_ROW_INDICATORS:
        if pat.search(row):
            return True
    return False


def _count_table_columns(table_text: str) -> int:
    """Count columns in a markdown table by examining the first row."""
    lines = table_text.strip().split('\n')
    if not lines:
        return 0
    cells = [c.strip() for c in lines[0].split('|')][1:-1]
    return len(cells)


def fix_split_tables(markdown: str) -> str:
    """
    Repair markdown where docling split a single table into two,
    causing the second half to lose its header row.

    Detection: if a table's header row contains data patterns (phone,
    email, date) and a previous table has the same column count with a
    clean header, replace the continuation table's fake header with the
    real one and move the fake header back to a data row.
    """
    table_blocks = []
    for m in _TABLE_BLOCK_RE.finditer(markdown):
        table_blocks.append({
            'text': m.group(0),
            'start': m.start(),
            'end': m.end(),
            'cols': _count_table_columns(m.group(0)),
            'header': m.group(0).strip().split('\n')[0] if m.group(0).strip() else '',
        })

    if len(table_blocks) < 2:
        return markdown

    # Collect replacements to apply right-to-left
    replacements = []
    for i in range(1, len(table_blocks)):
        curr = table_blocks[i]
        prev = table_blocks[i - 1]

        if curr['cols'] != prev['cols'] or curr['cols'] < 2:
            continue
        if not _is_data_like_row(curr['header']):
            continue
        if _is_data_like_row(prev['header']):
            continue

        # Found a continuation table: fix it
        lines = curr['text'].strip().split('\n')
        fake_header = lines[0]
        separator = lines[1] if len(lines) > 1 else '|' + '---|' * curr['cols']
        data_rows = lines[2:] if len(lines) > 2 else []

        prev_lines = prev['text'].strip().split('\n')
        real_header = prev_lines[0]
        real_sep = prev_lines[1] if len(prev_lines) > 1 else separator

        fixed = '\n'.join([real_header, real_sep, fake_header] + data_rows)
        replacements.append((curr['start'], curr['end'], fixed))

    # Apply right-to-left to preserve positions
    result = markdown
    for start, end, new_text in reversed(replacements):
        result = result[:start] + new_text + result[end:]

    return result


def _extract_tables_and_chunk_text(
    text: str,
    metadata: Dict[str, Any],
    text_chunk_fn,
    start_index: int = 0,
) -> List:
    """
    Extract markdown tables as intact units, chunk the remaining text.

    This prevents tables from being split mid-row by the chunker.
    Returns combined results with tables as single chunks and text
    processed by text_chunk_fn.

    Table chunks get is_table=True and chunk_type="table" in their metadata.
    """
    parts = _TABLE_BLOCK_RE.split(text)
    chunks = []
    idx = start_index

    def _table_meta(base_meta: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich metadata for a table chunk."""
        meta = dict(base_meta) if base_meta else {}
        meta["is_table"] = True
        meta["chunk_type"] = "table"
        return meta

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if _TABLE_BLOCK_RE.fullmatch(part):
            # Parse the table
            lines = part.strip().split('\n')
            if len(lines) < 3:
                continue  # malformed table, skip

            header_line = lines[0]
            sep_line = lines[1]  # separator like |---|---|
            data_rows = lines[2:]

            # Parse header cells (strip leading/trailing |, split, trim)
            header_cells = [c.strip() for c in header_line.split('|')][1:-1]
            if not header_cells:
                continue

            # Check if the "header" is actually a data row (continuation table)
            header_is_data = _is_data_like_row(header_line)

            # Single-row tables or data-like headers: keep as one chunk
            if len(data_rows) <= 1 or header_is_data:
                meta = _table_meta(metadata)
                if header_is_data:
                    meta["continuation_table"] = True
                chunks.append(ChunkResult(
                    text=part,
                    metadata=meta,
                    chunk_index=idx,
                ))
                idx += 1
            else:
                # Large table: split into row-level enriched chunks
                # Each row becomes a natural-language key-value chunk
                # Original markdown row is kept as parent_text for context
                for row_line in data_rows:
                    cells = [c.strip() for c in row_line.split('|')][1:-1]
                    if len(cells) != len(header_cells):
                        # Row has different column count, skip or include as-is
                        enriched = row_line
                    else:
                        # Adaptive natural language template.
                        # Template A (subject-style): "val0的col1是val1，col2是val2。"
                        #   Best when val0 is a meaningful noun: 薪酬福利, CSS, 用户管理
                        # Template B (column-first): "col0为val0，col1是val1，col2是val2。"
                        #   Best when val0 is a number/ID/time: 1, 14:00, 2024
                        val0 = cells[0]
                        val0_is_subject = bool(
                            re.search(r'[^\d\s\-:.#/\\(\\)（）]', val0)
                        )

                        if val0_is_subject and len(header_cells) >= 2:
                            # Template A: "薪酬福利的联系人是周筱莉，联系方式是0571-86621852。"
                            parts = []
                            if cells[1]:
                                parts.append(f"{val0}的{header_cells[1]}是{cells[1]}")
                            else:
                                parts.append(val0)
                            for j in range(2, len(header_cells)):
                                if cells[j]:
                                    parts.append(f"{header_cells[j]}是{cells[j]}")
                            enriched = "，".join(parts) + "。"
                        else:
                            # Template B: "序号为1，模块是用户管理，状态是已完成。"
                            parts = []
                            if val0:
                                parts.append(f"{header_cells[0]}为{val0}")
                            else:
                                parts.append(header_cells[0])
                            for j in range(1, len(header_cells)):
                                if cells[j]:
                                    parts.append(f"{header_cells[j]}是{cells[j]}")
                            enriched = "，".join(parts) + "。"

                    # Keep original markdown as parent_text
                    original_row = f"{header_line}\n{sep_line}\n{row_line}"

                    meta = _table_meta(metadata)
                    meta["row_index"] = idx  # track row position
                    chunks.append(ChunkResult(
                        text=enriched,
                        parent_text=original_row,
                        metadata=meta,
                        chunk_index=idx,
                    ))
                    idx += 1
        else:
            # Regular text — delegate to the provided chunking function
            text_chunks = text_chunk_fn(part)
            for tc in text_chunks:
                tc.chunk_index = idx
                chunks.append(tc)
                idx += 1

    # Merge fragments: very short text chunks (< MIN_CHUNK_CHARS) have
    # poor retrieval quality and confuse the LLM. Merge them with the
    # preceding text chunk so each chunk is semantically self-contained.
    MIN_CHUNK_CHARS = 50
    merged = []
    pending = None  # short text chunk waiting to be merged

    def _merge_text(a: str, b: str) -> str:
        """Join two text fragments, avoiding double newlines."""
        a = a.rstrip()
        b = b.lstrip()
        return a + "\n" + b if a and b else (a or b)

    for c in chunks:
        is_table = c.metadata.get("is_table", False) if c.metadata else False

        if is_table:
            if pending:
                merged.append(pending)
                pending = None
            merged.append(c)
        elif len(c.text) < MIN_CHUNK_CHARS:
            if merged and not merged[-1].metadata.get("is_table", False):
                prev = merged[-1]
                prev.text = _merge_text(prev.text, c.text)
                prev.metadata["merged_fragments"] = True
            else:
                if pending:
                    pending.text = _merge_text(pending.text, c.text)
                else:
                    pending = c
        else:
            if pending:
                c.text = _merge_text(pending.text, c.text)
                c.metadata["merged_fragments"] = True
                pending = None
            merged.append(c)

    if pending:
        if merged and not merged[-1].metadata.get("is_table", False):
            merged[-1].text = _merge_text(merged[-1].text, pending.text)
            merged[-1].metadata["merged_fragments"] = True
        else:
            merged.append(pending)

    for i, c in enumerate(merged):
        c.chunk_index = i

    return merged


class ChunkResult:
    def __init__(self, text: str, parent_text: str = None, metadata: Dict[str, Any] = None, chunk_index: int = 0):
        self.text = text
        self.parent_text = parent_text or ""
        self.metadata = metadata or {}
        self.chunk_index = chunk_index


def chunk_text(
    text: str,
    strategy: str = "recursive",
    metadata: Dict[str, Any] = None,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    heading_boundaries: List[Dict[str, Any]] = None,
) -> List[ChunkResult]:
    """
    Chunk text using the specified strategy.

    Args:
        text: The full document text to chunk.
        strategy: One of fixed, recursive, parent_child, semantic, hybrid.
        metadata: Base metadata applied to every chunk.
        chunk_size: Target chunk size in characters.
        chunk_overlap: Overlap between consecutive chunks.
        heading_boundaries: LLM-analyzed heading hierarchy, e.g.:
            [{"parent": "第一章", "children": ["1.1", "1.2"], "note": "..."}]
            Used by hybrid and parent_child to guide section detection.
    """
    strategy_map = {
        "fixed": _chunk_fixed,
        "recursive": _chunk_recursive,
        "parent_child": _chunk_parent_child,
        "semantic": _chunk_semantic,
        "hybrid": _chunk_hybrid,
    }
    func = strategy_map.get(strategy, _chunk_recursive)
    return func(text, metadata, chunk_size, chunk_overlap, heading_boundaries)


def _chunk_fixed(
    text: str, metadata: Dict[str, Any], chunk_size: int, chunk_overlap: int,
    heading_boundaries: List[Dict[str, Any]] = None,
) -> List[ChunkResult]:
    def _fixed_chunk_text(text_part: str) -> List[ChunkResult]:
        chunks = []
        start = 0
        idx = 0
        while start < len(text_part):
            end = start + chunk_size
            chunk_text = text_part[start:end]
            if chunk_text.strip():
                chunks.append(ChunkResult(
                    text=chunk_text.strip(),
                    metadata=metadata,
                    chunk_index=idx,
                ))
                idx += 1
            start = end - chunk_overlap
        return chunks

    return _extract_tables_and_chunk_text(text, metadata, _fixed_chunk_text)


def _chunk_recursive(
    text: str, metadata: Dict[str, Any], chunk_size: int, chunk_overlap: int,
    heading_boundaries: List[Dict[str, Any]] = None,
) -> List[ChunkResult]:
    def _recursive_chunk_text(text_part: str) -> List[ChunkResult]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", ".", "！", "!", "？", "?", "；", ";", " ", ""],
        )
        texts = splitter.split_text(text_part)
        return [
            ChunkResult(text=t, metadata=metadata, chunk_index=i)
            for i, t in enumerate(texts)
            if t.strip()
        ]

    return _extract_tables_and_chunk_text(text, metadata, _recursive_chunk_text)


def _chunk_parent_child(
    text: str, metadata: Dict[str, Any], chunk_size: int, chunk_overlap: int,
    heading_boundaries: List[Dict[str, Any]] = None,
) -> List[ChunkResult]:
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size * 4,
        chunk_overlap=chunk_overlap * 2,
        separators=["\n\n", "\n", "。", ".", ""],
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", ".", "！", "!", "？", "?", " ", ""],
    )

    # Build LLM heading index for cross-referencing
    llm_index = _build_llm_heading_index(heading_boundaries)

    def _pc_chunk_text(text_part: str) -> List[ChunkResult]:
        """Parent-child chunk a text fragment (no tables)."""
        parents = parent_splitter.split_text(text_part)
        result = []
        section_heading = _extract_heading(text_part) or ""
        section_heading = _resolve_heading(section_heading, llm_index)
        for parent in parents:
            parent_heading = _extract_heading(parent) or section_heading
            parent_heading = _resolve_heading(parent_heading, llm_index)
            children = child_splitter.split_text(parent)
            for child in children:
                if child.strip():
                    child_meta = dict(metadata) if metadata else {}
                    child_meta["has_parent"] = True
                    child_meta["chunk_type"] = "child"
                    if parent_heading:
                        child_meta["heading"] = parent_heading
                    result.append(ChunkResult(
                        text=child.strip(),
                        parent_text=parent.strip(),
                        metadata=child_meta,
                    ))
        return result

    return _extract_tables_and_chunk_text(text, metadata, _pc_chunk_text)


def _chunk_semantic(
    text: str, metadata: Dict[str, Any], chunk_size: int, chunk_overlap: int,
    heading_boundaries: List[Dict[str, Any]] = None,
) -> List[ChunkResult]:
    def _semantic_chunk_text(text_part: str) -> List[ChunkResult]:
        base_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size // 2,
            chunk_overlap=0,
            separators=["\n\n", "\n", "。", ".", ""],
        )
        small_chunks = base_splitter.split_text(text_part)
        if len(small_chunks) <= 1:
            return [ChunkResult(text=text_part.strip(), metadata=metadata, chunk_index=0)] if text_part.strip() else []

        try:
            embeddings = embed_texts(small_chunks)
        except Exception:
            return _chunk_recursive(text_part, metadata, chunk_size, chunk_overlap, heading_boundaries)

        merged = []
        current_group = [small_chunks[0]]
        current_embedding = embeddings[0]

        for i in range(1, len(small_chunks)):
            similarity = _cosine_similarity(current_embedding, embeddings[i])
            if similarity > 0.7 and len("".join(current_group)) < chunk_size:
                current_group.append(small_chunks[i])
                for j in range(len(current_embedding)):
                    current_embedding[j] = (current_embedding[j] + embeddings[i][j]) / 2
            else:
                merged.append("\n".join(current_group))
                current_group = [small_chunks[i]]
                current_embedding = embeddings[i]

        if current_group:
            merged.append("\n".join(current_group))

        return [
            ChunkResult(text=t.strip(), metadata=metadata, chunk_index=i)
            for i, t in enumerate(merged)
            if t.strip()
        ]

    return _extract_tables_and_chunk_text(text, metadata, _semantic_chunk_text)


def _chunk_hybrid(
    text: str, metadata: Dict[str, Any], chunk_size: int, chunk_overlap: int,
    heading_boundaries: List[Dict[str, Any]] = None,
) -> List[ChunkResult]:
    """
    Hybrid chunking: uses parent-child for structured sections,
    semantic chunking for narrative sections.

    Tables are extracted first as intact units, then the remaining text
    is split by section boundaries and chunked with the appropriate strategy.

    When heading_boundaries is provided (from LLM analysis), it is used to:
    - Build a known-heading index for validating regex-detected headings
    - Guide parent-child relationship detection
    - Enrich chunk metadata with LLM-identified heading context
    """

    # Build heading index from LLM analysis for cross-referencing
    llm_index = _build_llm_heading_index(heading_boundaries)

    # Split text into sections by headings, numeric headings, or double newlines
    section_pattern = re.compile(
        r'(?=^#{1,6}\s|^[一二三四五六七八九十]+[、.]|^第[一二三四五六七八九十\d]+[章节]|^\d+(?:\.\d+){0,2}\s+\S|\n\n)',
        re.MULTILINE,
    )

    def _hybrid_chunk_section(
        section: str, section_meta: Dict[str, Any] = None
    ) -> List[ChunkResult]:
        """Chunk a single section (guaranteed no tables)."""
        # Merge section-level metadata (heading) into the base metadata
        effective_meta = dict(metadata) if metadata else {}
        if section_meta:
            effective_meta.update(section_meta)

        # Detect if section is structured (has sub-headings, numeric headings, or lists)
        has_heading = bool(re.search(
            r'^#{1,6}\s|^[一二三四五六七八九十]+[、.]|^\d+(?:\.\d+){0,2}\s+\S',
            section, re.MULTILINE,
        ))
        has_list = bool(re.search(r'^[\s]*[-*•]\s+.+', section, re.MULTILINE))
        is_structured = has_heading or has_list

        if is_structured and len(section) > chunk_size:
            return _chunk_parent_child(section, effective_meta, chunk_size, chunk_overlap, heading_boundaries)
        elif len(section) > chunk_size * 2:
            return _chunk_semantic(section, effective_meta, chunk_size, chunk_overlap, heading_boundaries)
        else:
            return _chunk_recursive(section, effective_meta, chunk_size, chunk_overlap, heading_boundaries)

    def _hybrid_chunk_text(text_part: str) -> List[ChunkResult]:
        """Hybrid-chunk a text fragment (no tables)."""
        raw_sections = section_pattern.split(text_part)
        sections = [s.strip() for s in raw_sections if s.strip()]
        if not sections:
            return _chunk_recursive(text_part, metadata, chunk_size, chunk_overlap, heading_boundaries)

        all_chunks = []
        for section in sections:
            # Extract the heading for this section, cross-reference with LLM analysis
            heading = _extract_heading(section)
            section_meta = {}
            if heading:
                # Use LLM-resolved path if available, otherwise raw heading
                resolved = _resolve_heading(heading, llm_index)
                section_meta["heading"] = resolved
            all_chunks.extend(_hybrid_chunk_section(section, section_meta))
        return all_chunks

    return _extract_tables_and_chunk_text(text, metadata, _hybrid_chunk_text)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
