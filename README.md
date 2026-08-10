# vq-openmemory

![Banner](https://via.placeholder.com/800x200.png?text=vq-openmemory)

## About
Open-source AI memory system. Stores compressed context, applies envelope encryption, and exposes a rate-limited API with audit logging.

## Features
- Memory storage & compression (`core/`)
- Envelope encryption (`security/encryption.py`)
- Rate-limited API (`api/`)
- Audit trails (`audit/`)
- Python client (`client.py`)

## Installation
```bash
pip install -r requirements.txt
# or
docker-compose up
```

## Usage
```python
from client import MemoryClient
client = MemoryClient()
client.store("context", "value")
```

## License
See LICENSE.