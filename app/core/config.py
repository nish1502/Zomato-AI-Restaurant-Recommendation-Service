from dotenv import load_dotenv
load_dotenv()
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    """
    Minimal configuration for Phase 1 (dataset ingestion & normalization).

    Values can be overridden via environment variables if needed.
    """

    # HuggingFace dataset identifiers
    HF_DATASET_NAME: str = os.getenv(
        "HF_DATASET_NAME", "ManikaSaini/zomato-restaurant-recommendation"
    )
    HF_DATASET_SPLIT: str = os.getenv("HF_DATASET_SPLIT", "train")

    # Local data paths (relative to project root by default)
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data"))
    RAW_CACHE_DIR: Path = Path(os.getenv("RAW_CACHE_DIR", "data/raw"))
    PROCESSED_DIR: Path = Path(os.getenv("PROCESSED_DIR", "data/processed"))
    PROCESSED_DATASET_PATH: Path = Path(
        os.getenv(
            "PROCESSED_DATASET_PATH",
            "data/processed/restaurants.parquet",
        )
    )

    # Groq LLM configuration (Phase 3)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")

    # Feature flags for LLM usage
    USE_LLM_RANKING: bool = os.getenv("USE_LLM_RANKING", "false").lower() == "true"
    MAX_LLM_CANDIDATES: int = int(os.getenv("MAX_LLM_CANDIDATES", "30"))


settings = Settings()

