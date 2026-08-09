from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="openmemory-ai",
    version="1.0.0",
    author="Shivam Kumar (shivay00001)",
    author_email="shivaysinghrajputofficial@gmail.com",
    description="A 100/100 Enterprise-grade, async, and mathematically secure AI Memory System.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/shivay00001/openmemory-ai",
    packages=find_packages(include=["core", "api", "security"]),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=[
        "fastapi>=0.100.0",
        "uvicorn>=0.23.0",
        "sqlalchemy>=2.0.0",
        "aiosqlite>=0.19.0",
        "chromadb>=0.4.0",
        "cryptography>=41.0.0",
        "pydantic>=2.0.0",
        "redis>=5.0.0",
        "boto3>=1.28.0",
        "asyncpg>=0.28.0"
    ],
)
