import uuid
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlalchemy import select
from core.models import BillingLog

class BillingMeter:
    """
    Handles usage metering for the OpenMemory B2B API, persisting to DB.
    """
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        
    async def log_compression(self, tenant_id: str, tokens_compressed: int):
        """Logs a context compression event."""
        record = BillingLog(
            event_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            event_type="context_compression",
            quantity=float(tokens_compressed),
            unit="tokens"
        )
        self.db.add(record)
        await self.db.commit()
        return record

    async def log_storage_write(self, tenant_id: str, bytes_written: int):
        """Logs memory storage usage."""
        record = BillingLog(
            event_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            event_type="storage_write",
            quantity=float(bytes_written),
            unit="bytes"
        )
        self.db.add(record)
        await self.db.commit()
        return record
        
    async def get_tenant_usage(self, tenant_id: str) -> Dict[str, Any]:
        """Calculates current usage for a tenant by aggregating DB records."""
        tokens_result = await self.db.execute(
            select(func.sum(BillingLog.quantity)).filter(
                BillingLog.tenant_id == tenant_id,
                BillingLog.event_type == "context_compression"
            )
        )
        tokens_query = tokens_result.scalar()
        
        bytes_result = await self.db.execute(
            select(func.sum(BillingLog.quantity)).filter(
                BillingLog.tenant_id == tenant_id,
                BillingLog.event_type == "storage_write"
            )
        )
        bytes_query = bytes_result.scalar()
        
        return {
            "tenant_id": tenant_id,
            "total_tokens_compressed": tokens_query or 0.0,
            "total_bytes_written": bytes_query or 0.0
        }


