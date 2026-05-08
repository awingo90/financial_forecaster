"""Strict pydantic schemas matching VAULT.md §7."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


AgentName = Literal["Researcher", "Analyst", "Critic", "Trader", "Reflection"]
EvidenceKind = Literal["primary", "secondary", "social"]
ActionType = Literal["watchlist", "paper_trade", "update_thesis", "new_source"]


class Evidence(BaseModel):
    source: str
    weight: float = Field(ge=-1.0, le=1.0)
    kind: EvidenceKind


class Claim(BaseModel):
    statement: str
    prior: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = []
    posterior: float = Field(ge=0.0, le=1.0)
    falsifier: str


class Risk(BaseModel):
    max_drawdown_pct: float = 0.0
    stop_loss_pct: float = 0.0
    position_size_pct: float = 0.0
    horizon_days: int = 0
    invalidation_conditions: list[str] = []


class Backtest(BaseModel):
    ran: bool = False
    sample_size: int = 0
    sharpe: float = 0.0
    max_dd: float = 0.0
    regimes_covered: list[str] = []


class Action(BaseModel):
    type: ActionType
    payload: dict[str, Any] = {}


class AgentOutput(BaseModel):
    """The single canonical object passed between agents and persisted to logs."""

    agent: AgentName
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    thesis_id: str | None = None
    summary: str = Field(max_length=280)
    claims: list[Claim] = []
    confidence: int = Field(ge=0, le=100)
    risk: Risk = Risk()
    backtest: Backtest = Backtest()
    actions: list[Action] = []
    disclaimers_acknowledged: bool = True
    status: Literal[
        "DRAFT",
        "REVIEWED",
        "PUBLISHED",
        "SIMULATED — NOT FOR EXECUTION",
    ] = "DRAFT"

    @field_validator("confidence")
    @classmethod
    def cap_confidence_until_critic(cls, v: int, info: Any) -> int:
        # Hard ceiling; the Critic must explicitly raise it.
        return max(0, min(100, v))


class BriefRequest(BaseModel):
    horizon: Literal["intraday", "swing", "macro"] = "swing"
    universe: list[str] | None = None
    force_refresh: bool = False


class BriefResponse(BaseModel):
    date: str
    regime: str
    ideas: list[AgentOutput]
    markdown_path: str
    json_log_path: str
    status: str = "SIMULATED — NOT FOR EXECUTION"
