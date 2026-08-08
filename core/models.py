from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import declarative_base, relationship
import datetime

Base = declarative_base()

class Tenant(Base):
    __tablename__ = 'tenants'
    
    tenant_id = Column(String, primary_key=True)
    api_key_hash = Column(String, unique=True, nullable=False)
    encryption_key = Column(String, nullable=False) # Base64 Fernet Key
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class EpisodicMemory(Base):
    __tablename__ = 'episodic_memory'
    
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey('tenants.tenant_id'), index=True)
    session_id = Column(String, index=True, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    role = Column(String, nullable=False) # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False) # Encrypted content
    metadata_json = Column(Text, nullable=True) # Encrypted metadata

class BillingLog(Base):
    __tablename__ = 'billing_logs'
    
    event_id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey('tenants.tenant_id'), index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    event_type = Column(String, nullable=False) # 'context_compression', 'storage_write'
    quantity = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
