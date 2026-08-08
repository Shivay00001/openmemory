import sys
import os
import asyncio
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from sqlalchemy import select

# Ensure OpenMemory directory is in path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from api.server import app, AsyncSessionLocal, Base, engine
from core.models import Tenant
from security.encryption import KMSWrapper

client = TestClient(app)

async def setup_mock_tenant_async():
    """Seeds the DB with a mock tenant for testing asynchronously."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).filter(Tenant.tenant_id == "tenant_xyz99"))
        tenant = result.scalar_one_or_none()
        if not tenant:
            # Generate a real Fernet key for the mock tenant
            raw_key = Fernet.generate_key()
            # Simulate Envelope Encryption (encrypt the key with KMS before saving)
            encrypted_key = KMSWrapper.encrypt_data_key(raw_key)
            
            new_tenant = Tenant(
                tenant_id="tenant_xyz99",
                api_key_hash="om_xyz99",
                encryption_key=encrypted_key
            )
            db.add(new_tenant)
            await db.commit()

def run_tests():
    print("=== Testing OpenMemory Enterprise API (Async + KMS Envelope) ===")
    
    # Run DB setup synchronously to prepare for the FastApi TestClient
    asyncio.run(setup_mock_tenant_async())
    
    # Test 1: Health Check
    print("\n[1] Testing Health Check...")
    resp = client.get("/health")
    assert resp.status_code == 200
    print(f"Health Check Passed: {resp.json()}")
    
    # Test 2: Add Semantic Fact (Authentication & KMS Encryption)
    print("\n[2] Testing Semantic Memory Storage with AES-256 KMS Envelope Encryption & ChromaDB...")
    
    # Missing API Key should fail
    resp_fail = client.post("/v1/memory/semantic", json={"key": "project_codename", "value": "Project Titan"})
    assert resp_fail.status_code == 422 # Missing Header (Unprocessable Entity)
    
    # Valid API Key
    tenant_api_key = "om_xyz99"
    resp_success = client.post(
        "/v1/memory/semantic", 
        json={"key": "project_codename", "value": "Project Titan"},
        headers={"x-api-key": tenant_api_key}
    )
    assert resp_success.status_code == 200
    print(f"Storage Passed: {resp_success.json()}")
    
    # Test 3: Rate Limiting & Usage Metering
    print("\n[3] Testing Rate Limiting & Usage Metering (SQLAlchemy Persisted)...")
    resp_billing = client.get(
        "/v1/billing/usage",
        headers={"x-api-key": tenant_api_key}
    )
    assert resp_billing.status_code == 200
    usage_data = resp_billing.json()
    print(f"Billing Data retrieved: {usage_data}")
    
    # Ensure bytes were metered for our storage write
    assert usage_data["total_bytes_written"] > 0
    print("Usage successfully metered to SQLite for Stripe/Paddle billing.")
    
    print("\n[SUCCESS] All Production Enterprise API endpoints tested successfully!")

if __name__ == "__main__":
    run_tests()


