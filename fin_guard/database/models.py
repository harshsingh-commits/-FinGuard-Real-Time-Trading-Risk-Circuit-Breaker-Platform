"""SQLite schema models represented as typed records."""

from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    scenario: str = Field(default="normal", pattern="^(normal|bull|bear|high_volatility|flash_crash)$")


class ApprovalRequest(BaseModel):
    thread_id: str = "default"
    decision: str = Field(pattern="^(APPROVE|REJECT|FORCE CLOSE POSITIONS)$")


class TradingDayRequest(BaseModel):
    scenario: str = Field(default="normal", pattern="^(normal|bull|bear|high_volatility|flash_crash)$")
    close_positions: list[str] = []
