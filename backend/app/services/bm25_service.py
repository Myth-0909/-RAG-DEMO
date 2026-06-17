"""
BM25 keyword search service via SQLite FTS5.

Provides BM25-based keyword retrieval on document_chunks.chunk_text,
as a complement to the existing Milvus vector similarity search.

Uses jieba for Chinese text tokenization before inserting into FTS5,
since FTS5's default tokenizer splits on whitespace only.
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

# ── FTS5 table DDL ──────────────────────────────────────────────────────────

FTS_TABLE_NAME = "document_chunks_fts"

CREATE_FTS_TABLE_SQL = f"""
    CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE_NAME} USING fts5(
        chunk_text,
        tokenize='porter unicode61'
    )
"""


class BM25Service:
    """
    BM25 keyword search via SQLite FTS5.

    The FTS5 virtual table uses a standalone (non-content-sync) design:
    chunk text is pre-tokenized with jieba before insertion, and the
    FTS5 rowid is set to document_chunks.id for direct JOIN.

    Usage:
        bm25 = BM25Service(db)
        results = bm25.search("查询关键词", knowledge_base_ids=[1, 2], top_k=10)
    """

    def __init__(self, db: Session):
        self.db = db
        self._ensure_table()

    # ── Table management ─────────────────────────────────────────────────

    def _ensure_table(self):
        """Create FTS5 virtual table if it doesn't exist."""
        try:
            self.db.execute(text(CREATE_FTS_TABLE_SQL))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.warning(f"FTS5 table creation skipped: {e}")

    def table_exists(self) -> bool:
        """Check if the FTS5 virtual table exists."""
        try:
            result = self.db.execute(text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name=:name"
            ), {"name": FTS_TABLE_NAME})
            return result.fetchone() is not None
        except Exception:
            return False

    def chunk_count(self) -> int:
        """Number of indexed chunks in FTS5."""
        if not self.table_exists():
            return 0
        try:
            result = self.db.execute(text(
                f"SELECT COUNT(*) FROM {FTS_TABLE_NAME}"
            ))
            return result.scalar() or 0
        except Exception:
            return 0

    # ── Tokenization ─────────────────────────────────────────────────────

    @staticmethod
    def tokenize(text: str) -> str:
        """
        Tokenize text with jieba for Chinese word segmentation.

        Returns space-separated tokens suitable for FTS5 insertion.
        Single-character non-ASCII tokens are filtered out (Chinese
        single characters carry little semantic value for search).
        ASCII tokens (English words) are kept regardless of length.
        """
        import jieba

        if not text or not text.strip():
            return ""

        tokens = jieba.cut(text.strip())
        meaningful = [
            t.strip()
            for t in tokens
            if len(t.strip()) > 1 or t.strip().isascii()
        ]
        return " ".join(meaningful)

    # ── Search ───────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        knowledge_base_ids: List[int],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search FTS5 with BM25 ranking.

        Tokenizes the query with jieba, executes a MATCH query against
        the FTS5 table, and joins back to document_chunks for full data.

        Returns a list of dicts with the same shape as MilvusService.search():
        {id, score, chunk_text, parent_text, metadata, document_id, chunk_index}
        """
        if not self.table_exists():
            logger.warning("FTS5 table does not exist, returning empty results")
            return []

        tokenized = self.tokenize(query)
        if not tokenized:
            logger.info("Query tokenized to empty string, returning empty results")
            return []

        # Build FTS5 query — each token becomes a prefix match term
        fts_query = " OR ".join(
            f'"{token}"' for token in tokenized.split() if token
        )
        if not fts_query:
            return []

        try:
            # Build the parameterized query
            # The inner query gets FTS5 rowid + BM25 rank
            # The outer query joins to document_chunks for full data
            # and filters by knowledge_base_ids
            kb_filter = ""
            kb_params = {}
            if knowledge_base_ids:
                kb_filter = (
                    "AND dc.document_id IN ("
                    "SELECT id FROM documents WHERE knowledge_base_id IN ("
                    + ",".join(f":kb_{i}" for i in range(len(knowledge_base_ids)))
                    + "))"
                )
                kb_params = {f"kb_{i}": kb_id for i, kb_id in enumerate(knowledge_base_ids)}

            sql = text(f"""
                SELECT
                    dc.id,
                    dc.document_id,
                    dc.chunk_index,
                    dc.chunk_text,
                    dc.parent_text,
                    dc.metadata_json,
                    fts_ranks.rank AS bm25_score
                FROM (
                    SELECT rowid, bm25({FTS_TABLE_NAME}) AS rank
                    FROM {FTS_TABLE_NAME}
                    WHERE {FTS_TABLE_NAME} MATCH :query
                    ORDER BY rank
                    LIMIT :top_k
                ) AS fts_ranks
                JOIN document_chunks dc ON dc.id = fts_ranks.rowid
                WHERE 1=1 {kb_filter}
                ORDER BY fts_ranks.rank
                LIMIT :top_k
            """)

            params = {"query": fts_query, "top_k": top_k, **kb_params}

            result = self.db.execute(sql, params)
            rows = result.fetchall()

            # Convert BM25 rank (negative, lower=better) to positive score (higher=better)
            # We negate and then min-max normalize within the result set
            if not rows:
                return []

            raw_scores = [row.bm25_score for row in rows]
            min_score = min(raw_scores)
            max_score = max(raw_scores)
            score_range = max_score - min_score if max_score != min_score else 1.0

            hits = []
            for row in rows:
                # Negate BM25 score (lower FTS rank = better match)
                # and normalize to [0, 1] range
                normalized_score = 1.0 - (row.bm25_score - min_score) / score_range

                hits.append({
                    "id": row.id,
                    "score": round(normalized_score, 4),
                    "chunk_text": row.chunk_text or "",
                    "parent_text": row.parent_text or "",
                    "metadata": row.metadata_json if row.metadata_json else {},
                    "document_id": row.document_id or 0,
                    "chunk_index": row.chunk_index or 0,
                })

            return hits

        except Exception as e:
            logger.error(f"FTS5 search failed: {e}", exc_info=True)
            return []

    # ── Index maintenance ────────────────────────────────────────────────

    def index_chunk(self, chunk_id: int, chunk_text: str):
        """
        Insert or replace a single chunk in the FTS index.

        Uses INSERT OR REPLACE so this is safe to call on updates.
        """
        if not self.table_exists():
            self._ensure_table()

        tokenized = self.tokenize(chunk_text)
        if not tokenized:
            return

        try:
            self.db.execute(text(
                f"INSERT OR REPLACE INTO {FTS_TABLE_NAME}(rowid, chunk_text) "
                "VALUES(:rowid, :text)"
            ), {"rowid": chunk_id, "text": tokenized})
        except Exception as e:
            logger.warning(f"FTS5 index_chunk failed (chunk_id={chunk_id}): {e}")

    def index_chunks_batch(self, chunks: List[Tuple[int, str]]):
        """
        Batch insert (chunk_id, chunk_text) tuples into FTS index.

        Args:
            chunks: List of (chunk_id, chunk_text) tuples.
        """
        if not chunks:
            return
        if not self.table_exists():
            self._ensure_table()

        try:
            for chunk_id, chunk_text in chunks:
                tokenized = self.tokenize(chunk_text)
                if not tokenized:
                    continue
                self.db.execute(text(
                    f"INSERT OR REPLACE INTO {FTS_TABLE_NAME}(rowid, chunk_text) "
                    "VALUES(:rowid, :text)"
                ), {"rowid": chunk_id, "text": tokenized})
        except Exception as e:
            logger.warning(f"FTS5 index_chunks_batch failed: {e}")

    def delete_chunk(self, chunk_id: int):
        """Remove a single chunk from the FTS index."""
        if not self.table_exists():
            return
        try:
            self.db.execute(text(
                f"DELETE FROM {FTS_TABLE_NAME} WHERE rowid = :rowid"
            ), {"rowid": chunk_id})
        except Exception as e:
            logger.warning(f"FTS5 delete_chunk failed (chunk_id={chunk_id}): {e}")

    def delete_by_document(self, document_id: int):
        """
        Remove all chunks belonging to a document from the FTS index.

        Finds chunk IDs via the document_chunks table, then deletes them
        from the FTS table.
        """
        if not self.table_exists():
            return
        try:
            # Find chunk IDs for this document
            result = self.db.execute(text(
                "SELECT id FROM document_chunks WHERE document_id = :doc_id"
            ), {"doc_id": document_id})
            chunk_ids = [row[0] for row in result.fetchall()]

            if chunk_ids:
                for cid in chunk_ids:
                    self.db.execute(text(
                        f"DELETE FROM {FTS_TABLE_NAME} WHERE rowid = :rowid"
                    ), {"rowid": cid})
                logger.info(
                    f"FTS5: deleted {len(chunk_ids)} chunks for document {document_id}"
                )
        except Exception as e:
            logger.warning(
                f"FTS5 delete_by_document failed (document_id={document_id}): {e}"
            )

    def delete_by_knowledge_base(self, knowledge_base_id: int):
        """
        Remove all chunks belonging to a knowledge base from the FTS index.
        """
        if not self.table_exists():
            return
        try:
            result = self.db.execute(text(
                "SELECT dc.id FROM document_chunks dc "
                "JOIN documents d ON dc.document_id = d.id "
                "WHERE d.knowledge_base_id = :kb_id"
            ), {"kb_id": knowledge_base_id})
            chunk_ids = [row[0] for row in result.fetchall()]

            if chunk_ids:
                for cid in chunk_ids:
                    self.db.execute(text(
                        f"DELETE FROM {FTS_TABLE_NAME} WHERE rowid = :rowid"
                    ), {"rowid": cid})
                logger.info(
                    f"FTS5: deleted {len(chunk_ids)} chunks "
                    f"for knowledge base {knowledge_base_id}"
                )
        except Exception as e:
            logger.warning(
                f"FTS5 delete_by_knowledge_base failed "
                f"(kb_id={knowledge_base_id}): {e}"
            )

    def rebuild_index(self, progress_callback=None):
        """
        Full rebuild: drop and recreate the FTS table, then re-index all chunks.

        Args:
            progress_callback: Optional callable(processed, total) for progress.
        """
        if not self.table_exists():
            self._ensure_table()

        try:
            # Drop and recreate for a clean rebuild
            self.db.execute(text(f"DROP TABLE IF EXISTS {FTS_TABLE_NAME}"))
            self.db.execute(text(CREATE_FTS_TABLE_SQL))
            self.db.commit()

            # Load all chunks
            result = self.db.execute(text(
                "SELECT id, chunk_text FROM document_chunks ORDER BY id"
            ))
            all_chunks = [(row[0], row[1]) for row in result.fetchall()]

            total = len(all_chunks)
            logger.info(f"FTS5: rebuilding index for {total} chunks...")

            for i, (cid, ctext) in enumerate(all_chunks):
                tokenized = self.tokenize(ctext)
                if tokenized:
                    self.db.execute(text(
                        f"INSERT INTO {FTS_TABLE_NAME}(rowid, chunk_text) "
                        "VALUES(:rowid, :text)"
                    ), {"rowid": cid, "text": tokenized})

                if progress_callback and i % 100 == 0:
                    progress_callback(i + 1, total)

            self.db.commit()
            logger.info(f"FTS5: rebuild complete — {total} chunks indexed")

        except Exception as e:
            self.db.rollback()
            logger.error(f"FTS5 rebuild_index failed: {e}", exc_info=True)
            raise
