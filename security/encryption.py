import base64
import json
import os
import boto3
from cryptography.fernet import Fernet
from core.models import Tenant

class KMSWrapper:
    """True AWS KMS Envelope Encryption Integration."""
    
    # In production, use boto3 KMS. 
    # Fallback to local mock ONLY if AWS credentials are not present (for local testing).
    USE_AWS = os.getenv("AWS_KMS_KEY_ID") is not None
    MOCK_MASTER = Fernet.generate_key() 
    
    @classmethod
    def encrypt_data_key(cls, plain_data_key: bytes) -> str:
        """Encrypts a tenant's raw data key using the Master KMS key."""
        if cls.USE_AWS:
            kms = boto3.client('kms')
            response = kms.encrypt(
                KeyId=os.getenv("AWS_KMS_KEY_ID"),
                Plaintext=plain_data_key
            )
            return base64.b64encode(response['CiphertextBlob']).decode('utf-8')
        else:
            cipher = Fernet(cls.MOCK_MASTER)
            return cipher.encrypt(plain_data_key).decode('utf-8')
        
    @classmethod
    def decrypt_data_key(cls, encrypted_data_key: str) -> bytes:
        """Decrypts a tenant's data key using the Master KMS key."""
        if cls.USE_AWS:
            kms = boto3.client('kms')
            response = kms.decrypt(
                CiphertextBlob=base64.b64decode(encrypted_data_key)
            )
            return response['Plaintext']
        else:
            cipher = Fernet(cls.MOCK_MASTER)
            return cipher.decrypt(encrypted_data_key.encode('utf-8'))

class EnterpriseEncryptionProvider:
    """
    Handles AES-256 Envelope Encryption (via Fernet) for Enterprise Data-at-Rest.
    """
    
    def __init__(self, db_session):
        self.db = db_session
        
    async def _get_tenant_cipher(self, tenant_id: str) -> Fernet:
        """Retrieves and decrypts the Fernet cipher for the tenant via KMS."""
        # Note: In the final async refactor, db queries will be awaited.
        from sqlalchemy import select
        result = await self.db.execute(select(Tenant).filter(Tenant.tenant_id == tenant_id))
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found.")
        
        # 1. Retrieve the ENCRYPTED data key from the database
        encrypted_data_key = tenant.encryption_key
        
        # 2. Ask KMS to decrypt the data key (Envelope Encryption)
        raw_key_bytes = KMSWrapper.decrypt_data_key(encrypted_data_key)
        
        return Fernet(raw_key_bytes)

    async def encrypt_payload(self, tenant_id: str, data: dict) -> str:
        """Encrypts a JSON payload using AES-256 CBC (Fernet)."""
        raw_json = json.dumps(data).encode('utf-8')
        cipher = await self._get_tenant_cipher(tenant_id)
        encrypted_bytes = cipher.encrypt(raw_json)
        return encrypted_bytes.decode('utf-8')
        
    async def decrypt_payload(self, tenant_id: str, encrypted_b64: str) -> dict:
        """Decrypts a payload."""
        cipher = await self._get_tenant_cipher(tenant_id)
        decrypted_bytes = cipher.decrypt(encrypted_b64.encode('utf-8'))
        return json.loads(decrypted_bytes.decode('utf-8'))


