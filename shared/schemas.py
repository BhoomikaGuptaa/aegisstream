"""
AegisStream shared event schema.
OpenTelemetry-inspired LLM event trace model.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class LLMEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    span_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: Optional[str] = None
    user_id_hash: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Routing / deployment
    app_name: str = "default"
    route_name: str = "default"
    environment: str = "production"
    deployment_version: str = "v1.0.0"
    prompt_template_version: str = "v1.0.0"
    guardrail_config_version: str = "v1.0.0"

    # Model identity
    model_name: str
    model_family: str
    provider: str

    # Content
    prompt: str
    response: str
    system_prompt_hash: Optional[str] = None
    retrieved_context: Optional[str] = None
    expected_answer: Optional[str] = None
    ground_truth_label: Optional[str] = None

    # Params
    temperature: float = 0.7
    max_tokens: int = 1024

    # Telemetry
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    estimated_cost_usd: float = 0.0

    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvaluatorResult(BaseModel):
    evaluator_name: str
    passed: bool
    severity: str  # info | low | medium | high | critical
    score_delta: float  # how much this adds to risk_score
    label: str
    explanation: str
    evidence: str
    confidence: float  # 0.0–1.0


class EvaluatedEvent(BaseModel):
    event: LLMEvent

    risk_score: float  # 0–100
    reliability_score: float  # 0–100
    usefulness_score: float  # 0–100
    safety_score: float  # 0–100
    groundedness_score: float  # 0–100

    review_required: bool
    deployment_blocking: bool
    primary_failure_mode: Optional[str] = None

    evaluator_results: List[EvaluatorResult] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewRecord(BaseModel):
    event_id: str
    risk_score: float
    primary_failure_mode: Optional[str]
    review_status: str = "pending"  # pending | approved | rejected | escalated
    reviewer_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class DriftAlert(BaseModel):
    alert_id: str = Field(default_factory=lambda: str(uuid4()))
    alert_type: str
    severity: str
    model_name: Optional[str] = None
    route_name: Optional[str] = None
    metric_name: str
    current_value: float
    baseline_value: float
    threshold: float
    message: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class DeploymentCheckRequest(BaseModel):
    model_name: str
    route_name: str
    environment: str = "production"
    window_minutes: int = 60
    thresholds: Optional[Dict[str, float]] = None


class DeploymentCheckResult(BaseModel):
    passed: bool
    model_name: str
    route_name: str
    environment: str
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    metrics: Dict[str, float]
    thresholds: Dict[str, float]
    failures: List[str]
    warnings: List[str]
    recommendation: str
