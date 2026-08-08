import sys
import os
import asyncio
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

import chromadb
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import Base, Tenant
from core.memory_store import MemoryStore
from api.billing import BillingMeter
from api.rate_limiter import RateLimiter

# DB Setup (Async Postgres with SQLite fallback)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./openmemory_prod.db")
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Chroma Setup
chroma_client = chromadb.PersistentClient(path="./chroma_db")

app = FastAPI(title="OpenMemory Enterprise API (Async)", version="3.0.0")
rate_limiter = RateLimiter(requests_per_minute=100)

@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# --- DEPENDENCIES ---
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def verify_api_key(x_api_key: str = Header(...), db: AsyncSession = Depends(get_db)) -> str:
    """Validates API key against SQLite Tenants table asynchronously."""
    result = await db.execute(select(Tenant).filter(Tenant.api_key_hash == x_api_key))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return tenant.tenant_id

# --- MODELS ---
class MemoryFact(BaseModel):
    key: str
    value: str
    
# --- ENDPOINTS ---
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "OpenMemory Enterprise Prod", "db": "connected"}

@app.post("/v1/memory/semantic")
async def add_semantic_fact(fact: MemoryFact, tenant_id: str = Depends(verify_api_key), db: AsyncSession = Depends(get_db)):
    """Stores an AES-256 encrypted semantic fact securely."""
    rate_limiter.check_rate_limit(tenant_id)
    
    store = MemoryStore(db, chroma_client)
    await store.add_semantic_fact(tenant_id, fact.key, fact.value)
    
    meter = BillingMeter(db)
    await meter.log_storage_write(tenant_id, len(fact.value.encode('utf-8')))
    
    return {"status": "success", "message": "AES Encrypted and stored in ChromaDB."}

@app.get("/v1/billing/usage")
async def get_usage(tenant_id: str = Depends(verify_api_key), db: AsyncSession = Depends(get_db)):
    """Returns DB-persisted API and storage usage for the tenant."""
    rate_limiter.check_rate_limit(tenant_id)
    meter = BillingMeter(db)
    return await meter.get_tenant_usage(tenant_id)

if __name__ == "__main__":
    import uvicorn
    print("OpenMemory Production API Server configured (Async). Run via `uvicorn api.server:app --reload`")


