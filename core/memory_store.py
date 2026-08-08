import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

import chromadb
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.models import EpisodicMemory, Tenant
from security.encryption import EnterpriseEncryptionProvider

class MemoryStore:
    """Manages Episodic (SQL) and Semantic (ChromaDB Vector) memories for production."""
    
    def __init__(self, db_session: AsyncSession, chroma_client: chromadb.ClientAPI):
        self.db = db_session
        self.chroma = chroma_client
        self.encryption = EnterpriseEncryptionProvider(db_session)
        
        # Ensure collection exists
        self.semantic_collection = self.chroma.get_or_create_collection(name="semantic_facts")

    async def add_episodic(self, tenant_id: str, role: str, content: str, session_id: str = None, metadata: dict = None) -> str:
        """Adds an encrypted interaction to the episodic memory."""
        mem_id = str(uuid.uuid4())
        
        # Encrypt the content at rest
        encrypted_content = await self.encryption.encrypt_payload(tenant_id, {"text": content})
        encrypted_metadata = await self.encryption.encrypt_payload(tenant_id, metadata or {})
        
        record = EpisodicMemory(
            id=mem_id,
            tenant_id=tenant_id,
            session_id=session_id,
            role=role,
            content=encrypted_content,
            metadata_json=encrypted_metadata
        )
        self.db.add(record)
        await self.db.commit()
        return mem_id

    async def add_semantic_fact(self, tenant_id: str, key: str, value: str, source_id: str = None):
        """Adds or updates a semantic fact in ChromaDB with vector embeddings."""
        encrypted_payload = await self.encryption.encrypt_payload(tenant_id, {"key": key, "value": value})
        
        self.semantic_collection.upsert(
            documents=[value], # Used for generating embeddings
            metadatas=[{
                "tenant_id": tenant_id, 
                "key": key, 
                "source_id": source_id or "system",
                "encrypted_payload": encrypted_payload
            }],
            ids=[f"{tenant_id}_{key}"]
        )

    async def get_recent_episodic(self, tenant_id: str, limit: int = 10, session_id: str = None) -> List[Dict[str, Any]]:
        """Retrieves and decrypts recent episodic memories."""
        stmt = select(EpisodicMemory).filter(EpisodicMemory.tenant_id == tenant_id)
        if session_id:
            stmt = stmt.filter(EpisodicMemory.session_id == session_id)
            
        stmt = stmt.order_by(EpisodicMemory.timestamp.desc()).limit(limit)
        result = await self.db.execute(stmt)
        records = result.scalars().all()
        
        results = []
        for r in reversed(records): # Return in chronological order
            decrypted_content = await self.encryption.decrypt_payload(tenant_id, r.content)
            decrypted_metadata = await self.encryption.decrypt_payload(tenant_id, r.metadata_json)
            results.append({
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "role": r.role,
                "content": decrypted_content.get("text", ""),
                "metadata": decrypted_metadata
            })
        return results

    async def query_semantic_memory(self, tenant_id: str, query_text: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Performs a vector search for relevant semantic facts."""
        results = self.semantic_collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where={"tenant_id": tenant_id} # Strictly isolate by tenant
        )
        
        facts = []
        if results and results["metadatas"] and len(results["metadatas"]) > 0:
            for meta in results["metadatas"][0]:
                decrypted = await self.encryption.decrypt_payload(tenant_id, meta["encrypted_payload"])
                facts.append(decrypted)
        return facts


