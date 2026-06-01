from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.embedding import embed_texts


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
) -> List[ChunkResult]:
    strategy_map = {
        "fixed": _chunk_fixed,
        "recursive": _chunk_recursive,
        "parent_child": _chunk_parent_child,
        "semantic": _chunk_semantic,
        "hybrid": _chunk_hybrid,
    }
    func = strategy_map.get(strategy, _chunk_recursive)
    return func(text, metadata, chunk_size, chunk_overlap)


def _chunk_fixed(
    text: str, metadata: Dict[str, Any], chunk_size: int, chunk_overlap: int
) -> List[ChunkResult]:
    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end]
        if chunk_text.strip():
            chunks.append(ChunkResult(
                text=chunk_text.strip(),
                metadata=metadata,
                chunk_index=idx,
            ))
            idx += 1
        start = end - chunk_overlap
    return chunks


def _chunk_recursive(
    text: str, metadata: Dict[str, Any], chunk_size: int, chunk_overlap: int
) -> List[ChunkResult]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", ".", "！", "!", "？", "?", "；", ";", " ", ""],
    )
    texts = splitter.split_text(text)
    return [
        ChunkResult(text=t, metadata=metadata, chunk_index=i)
        for i, t in enumerate(texts)
        if t.strip()
    ]


def _chunk_parent_child(
    text: str, metadata: Dict[str, Any], chunk_size: int, chunk_overlap: int
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

    parents = parent_splitter.split_text(text)
    chunks = []
    idx = 0
    for parent in parents:
        children = child_splitter.split_text(parent)
        for child in children:
            if child.strip():
                chunks.append(ChunkResult(
                    text=child.strip(),
                    parent_text=parent.strip(),
                    metadata=metadata,
                    chunk_index=idx,
                ))
                idx += 1
    return chunks


def _chunk_semantic(
    text: str, metadata: Dict[str, Any], chunk_size: int, chunk_overlap: int
) -> List[ChunkResult]:
    base_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size // 2,
        chunk_overlap=0,
        separators=["\n\n", "\n", "。", ".", ""],
    )
    small_chunks = base_splitter.split_text(text)
    if len(small_chunks) <= 1:
        return [ChunkResult(text=text.strip(), metadata=metadata, chunk_index=0)] if text.strip() else []

    try:
        embeddings = embed_texts(small_chunks)
    except Exception:
        return _chunk_recursive(text, metadata, chunk_size, chunk_overlap)

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


def _chunk_hybrid(
    text: str, metadata: Dict[str, Any], chunk_size: int, chunk_overlap: int
) -> List[ChunkResult]:
    """
    Hybrid chunking: uses parent-child for structured sections,
    semantic chunking for narrative sections.

    Detects section boundaries (headings, double newlines) and applies
    the appropriate strategy to each section.
    """
    import re

    # Split text into sections by headings or double newlines
    section_pattern = re.compile(
        r'(?=^#{1,6}\s|^[一二三四五六七八九十]+[、.]|^第[一二三四五六七八九十\d]+[章节]|\n\n)',
        re.MULTILINE,
    )
    raw_sections = section_pattern.split(text)
    sections = [s.strip() for s in raw_sections if s.strip()]

    if not sections:
        return _chunk_recursive(text, metadata, chunk_size, chunk_overlap)

    chunks = []
    idx = 0

    for section in sections:
        # Detect if section is structured (has sub-headings or lists)
        has_heading = bool(re.search(r'^#{1,6}\s|^[一二三四五六七八九十]+[、.]', section, re.MULTILINE))
        has_list = bool(re.search(r'^[\s]*[-*•\d.]\s+.+', section, re.MULTILINE))
        is_structured = has_heading or has_list

        if is_structured and len(section) > chunk_size:
            # Use parent-child for structured sections
            section_chunks = _chunk_parent_child(section, metadata, chunk_size, chunk_overlap)
        elif len(section) > chunk_size * 2:
            # Use semantic for longer narrative sections
            section_chunks = _chunk_semantic(section, metadata, chunk_size, chunk_overlap)
        else:
            # Use recursive for shorter sections
            section_chunks = _chunk_recursive(section, metadata, chunk_size, chunk_overlap)

        # Re-index chunks sequentially
        for chunk in section_chunks:
            chunk.chunk_index = idx
            chunks.append(chunk)
            idx += 1

    return chunks


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
