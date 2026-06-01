from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
from typing import List, Dict, Any, Optional
from app.config import settings


class MilvusService:
    def __init__(self):
        self._ensure_connected()

    def _ensure_connected(self):
        try:
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT,
                db_name=settings.MILVUS_DATABASE,
            )
        except Exception:
            pass

    def create_collection(self, name: str, dim: int = None):
        dim = dim or settings.EMBEDDING_DIM
        if utility.has_collection(name):
            collection = Collection(name)
            # Verify dim matches, drop and recreate if not
            try:
                schema = collection.schema
                for field in schema.fields:
                    if field.dtype == 101:  # FLOAT_VECTOR
                        existing_dim = field.params.get("dim", 0)
                        if existing_dim != dim:
                            self.drop_collection(name)
                            break
                else:
                    return collection
            except Exception:
                pass

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="parent_text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="metadata", dtype=DataType.JSON),
            FieldSchema(name="document_id", dtype=DataType.INT64),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
        ]
        schema = CollectionSchema(fields=fields, description=f"Knowledge base collection: {name}")
        collection = Collection(name=name, schema=schema)

        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128},
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        return collection

    def insert(
        self,
        collection_name: str,
        embeddings: List[List[float]],
        chunk_texts: List[str],
        parent_texts: List[str],
        metadata_list: List[Dict[str, Any]],
        document_ids: List[int],
        chunk_indices: List[int],
    ) -> List[int]:
        collection = Collection(collection_name)
        data = [
            embeddings,
            chunk_texts,
            parent_texts,
            metadata_list,
            document_ids,
            chunk_indices,
        ]
        result = collection.insert(data)
        collection.flush()
        return result.primary_keys

    def search(
        self,
        collection_name: str,
        query_embedding: List[float],
        top_k: int = 5,
        filter_expr: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        collection = Collection(collection_name)
        collection.load()

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
        output_fields = ["chunk_text", "parent_text", "metadata", "document_id", "chunk_index"]

        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filter_expr,
            output_fields=output_fields,
        )

        hits = []
        for hits_batch in results:
            for hit in hits_batch:
                entity = hit.entity
                hits.append({
                    "id": hit.id,
                    "score": hit.score,
                    "chunk_text": entity.chunk_text if hasattr(entity, 'chunk_text') else "",
                    "parent_text": entity.parent_text if hasattr(entity, 'parent_text') else "",
                    "metadata": entity.metadata if hasattr(entity, 'metadata') else {},
                    "document_id": entity.document_id if hasattr(entity, 'document_id') else 0,
                    "chunk_index": entity.chunk_index if hasattr(entity, 'chunk_index') else 0,
                })
        return hits

    def delete_by_document(self, collection_name: str, document_id: int):
        if not utility.has_collection(collection_name):
            return
        collection = Collection(collection_name)
        collection.load()
        collection.delete(f"document_id == {document_id}")
        collection.flush()

    def drop_collection(self, name: str):
        if utility.has_collection(name):
            utility.drop_collection(name)

    def get_collection_stats(self, name: str) -> Dict[str, Any]:
        if not utility.has_collection(name):
            return {"exists": False}
        collection = Collection(name)
        stats = collection.stats
        return {"exists": True, "row_count": stats.get("row_count", 0)}
