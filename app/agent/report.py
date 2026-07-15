"""Structured investigation report schema.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Escalation(BaseModel):
    required: bool
    target: str | None = Field(None, description="Role/team to escalate to")
    contact: str | None = Field(None, description="Name / email of the contact")
    rationale: str | None = None


class InvestigationReport(BaseModel):
    summary: str = Field(..., description="One-paragraph situation summary")
    equipment: str | None = Field(None, description="Tool involved")
    alarm: str | None = Field(None, description="Alarm code + severity")
    evidence: list[str] = Field(
        default_factory=list,
        description="Concrete facts retrieved via tools (incidents, PM, sensors, SOP)",
    )
    probable_root_causes: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    escalation: Escalation
    confidence: str = Field("Medium", description="Low | Medium | High")
    missing_information: list[str] = Field(
        default_factory=list,
        description="What the engineer should clarify/provide, if anything",
    )
