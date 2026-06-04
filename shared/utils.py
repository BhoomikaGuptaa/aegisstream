"""Shared utility functions."""
import hashlib
import math
import re
from datetime import datetime, timezone
from typing import List, Optional


def hash_string(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def contains_any(text: str, patterns: List[str]) -> Optional[str]:
    """Return the first matching pattern found in text (case-insensitive)."""
    lower = text.lower()
    for p in patterns:
        if p.lower() in lower:
            return p
    return None


def token_count_estimate(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, math.ceil(len(text) / 4))


def cost_estimate(input_tokens: int, output_tokens: int, provider: str, model_name: str) -> float:
    """Rough cost per 1M tokens in USD."""
    RATES = {
        "gpt-4o": (5.0, 15.0),
        "gpt-4-turbo": (10.0, 30.0),
        "claude-3-opus": (15.0, 75.0),
        "claude-3-sonnet": (3.0, 15.0),
        "claude-3-haiku": (0.25, 1.25),
        "llama-3-70b": (0.9, 0.9),
        "mistral-7b": (0.2, 0.2),
        "gemma-7b": (0.1, 0.1),
        "default": (1.0, 2.0),
    }
    in_rate, out_rate = RATES.get(model_name, RATES["default"])
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000


def extract_json_block(text: str) -> Optional[str]:
    """Try to find a JSON object in text."""
    match = re.search(r'\{.*?\}', text, re.DOTALL)
    return match.group(0) if match else None
