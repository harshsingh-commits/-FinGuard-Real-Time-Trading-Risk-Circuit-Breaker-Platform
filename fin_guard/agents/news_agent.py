"""News sentiment agent with switchable LLM backends and deterministic fallback."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from fin_guard.graph.state import FinGuardState
from fin_guard.backend.config import settings


class SentimentProvider(Protocol):
    def score(self, headlines: list[str]) -> tuple[float, float]: ...
    def analyze(self, headlines: list[str]) -> tuple[float, list[dict[str, Any]]]: ...


class NewsEvent(BaseModel):
    category: str = Field(description="earnings, layoffs, war, interest_rate, liquidity, or other")
    headline: str
    impact_score: float = Field(ge=0, le=100)
    rationale: str = ""


class NewsAnalysis(BaseModel):
    sentiment_score: float = Field(ge=0, le=100)
    market_impact_score: float = Field(ge=0, le=100)
    events: list[NewsEvent] = Field(default_factory=list)


class RuleBasedSentiment:
    """Offline provider used for local development and tests."""

    def score(self, headlines: list[str]) -> tuple[float, float]:
        text = " ".join(headlines).lower()
        fear_words = ("warning", "selloff", "investigate", "uncertainty", "crash", "volatility")
        positive_words = ("beat", "accelerates", "steady", "growth")
        fear = sum(text.count(word) for word in fear_words)
        positive = sum(text.count(word) for word in positive_words)
        sentiment_risk = min(100.0, max(0.0, 50 + fear * 16 - positive * 8))
        return round(sentiment_risk, 2), round(min(100.0, fear * 20), 2)

    def analyze(self, headlines: list[str]) -> tuple[float, list[dict[str, Any]]]:
        sentiment, impact = self.score(headlines)
        return impact, extract_events(headlines)


def extract_events(headlines: list[str]) -> list[dict]:
    """Extract governance-relevant event categories without requiring a network LLM."""
    categories = {
        "fear": ("warning", "selloff", "crash", "fear", "investigate"),
        "earnings": ("earnings", "revenue", "profit", "beat"),
        "war": ("war", "invasion", "conflict", "sanction", "geopolitical"),
        "geopolitical": ("sanction", "geopolitical", "election"),
        "interest_rate": ("interest rate", "rate hike", "rate cut", "central bank", "fed "),
        "layoffs": ("layoff", "job cuts", "workforce reduction"),
        "liquidity": ("liquidity", "spread", "funding", "bank"),
    }
    events = []
    for headline in headlines:
        lowered = headline.lower()
        matches = [name for name, terms in categories.items() if any(term in lowered for term in terms)]
        if matches:
            events.append({"headline": headline, "categories": matches, "category": matches[0], "impact_score": min(100.0, 35.0 + 15.0 * len(matches))})
    return events


class LangChainNewsProvider:
    """Structured LangChain provider for Groq, Gemini, OpenAI, or Ollama."""

    def __init__(self, provider: str):
        if provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            model = ChatGoogleGenerativeAI(model=settings.llm_model or "gemini-2.0-flash", temperature=0)
        elif provider in {"openai", "groq"}:
            from langchain_openai import ChatOpenAI
            if provider == "groq":
                model = ChatOpenAI(
                    model=(
                        settings.llm_model
                        if settings.llm_model != "risk-classifier"
                        else "llama-3.3-70b-versatile"
                    ),
                    api_key=settings.groq_api_key,
                    base_url=settings.groq_base_url,
                    temperature=0,
                )
            else:
                model = ChatOpenAI(model=settings.llm_model or "gpt-4o-mini", temperature=0)
        elif provider == "ollama":
            from langchain_ollama import ChatOllama
            model = ChatOllama(model=settings.llm_model or "llama3.1", temperature=0)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        self.model = model.with_structured_output(NewsAnalysis)

    def _invoke(self, headlines: list[str]) -> NewsAnalysis:
        prompt = (
            "You are a financial risk intelligence analyst. Extract only material events from these headlines. "
            "Classify events as earnings, layoffs, war, interest_rate, liquidity, or other. "
            "Return a 0-100 sentiment risk and market impact score.\n\n"
            + "\n".join(f"- {headline}" for headline in headlines)
        )
        result = self.model.invoke(prompt)
        return result if isinstance(result, NewsAnalysis) else NewsAnalysis.model_validate(result)

    def score(self, headlines: list[str]) -> tuple[float, float]:
        result = self._invoke(headlines)
        return result.sentiment_score, result.market_impact_score

    def analyze(self, headlines: list[str]) -> tuple[float, list[dict[str, Any]]]:
        result = self._invoke(headlines)
        return result.market_impact_score, [event.model_dump() for event in result.events]


def build_sentiment_provider(provider: str = "mock") -> SentimentProvider:
    """Return a provider; hosted providers can be added without changing graph code."""
    if provider == "mock":
        return RuleBasedSentiment()
    try:
        if provider in {"openai", "groq"}:
            from langchain_openai import ChatOpenAI
        elif provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
        elif provider == "ollama":
            from langchain_ollama import ChatOllama
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        return LangChainNewsProvider(provider)
    except ImportError as exc:
        raise RuntimeError(f"Install the {provider} LangChain integration to enable it") from exc


def news_agent(state: FinGuardState) -> dict:
    provider = build_sentiment_provider(settings.llm_provider)
    headlines = state.get("news_data", [])
    try:
        sentiment, market_risk = provider.score(headlines)
        impact, events = provider.analyze(headlines)
    except Exception:
        fallback = RuleBasedSentiment()
        sentiment, market_risk = fallback.score(headlines)
        impact, events = fallback.analyze(headlines)
    impact = max((event.get("impact_score", 0) for event in events), default=impact or market_risk)
    return {"sentiment_score": sentiment, "market_risk_score": market_risk, "news_events": events, "market_impact_score": round(impact, 2)}
