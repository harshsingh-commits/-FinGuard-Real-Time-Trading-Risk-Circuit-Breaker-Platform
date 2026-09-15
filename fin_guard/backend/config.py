"""Application configuration."""

from pathlib import Path
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR.parent / ".env")
DB_PATH = ROOT_DIR / "data" / "fin_guard.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class RiskLimits(BaseModel):
    """Configurable governance thresholds."""

    max_drawdown_pct: float = Field(default=10.0, gt=0)
    max_volatility_score: float = Field(default=78.0, ge=0, le=100)
    critical_risk_score: float = Field(default=80.0, ge=0, le=100)


class AppSettings(BaseModel):
    """Runtime settings with provider selection for news analysis."""

    llm_provider: str = "mock"
    llm_model: str = "risk-classifier"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic: str = "finguard.market.ticks"
    database_path: Path = DB_PATH
    risk_limits: RiskLimits = RiskLimits()


settings = AppSettings(
    llm_provider=os.getenv("LLM_PROVIDER", "mock"),
    llm_model=os.getenv("LLM_MODEL", "risk-classifier"),
    groq_api_key=os.getenv("GROQ_API_KEY", ""),
    groq_base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
)
