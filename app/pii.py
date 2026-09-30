from __future__ import annotations

import hashlib
import re
from typing import Any

PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "cccd": r"(?<!\d)\d{12}(?!\d)",
    "phone_vn": r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    "passport_vn": r"\b[A-Z]\d{7}\b",
}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def scrub_value(value: Any) -> Any:
    """Redact nested structured log fields before serialization."""
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if key == "trace_id" and isinstance(item, str) and re.fullmatch(r"[0-9a-f]{32}", item):
                cleaned[key] = item
            elif key == "correlation_id" and isinstance(item, str) and re.fullmatch(r"req-[0-9a-fA-F]{8}", item):
                cleaned[key] = item
            elif key == "user_id_hash" and isinstance(item, str) and re.fullmatch(r"[0-9a-f]{12}", item):
                cleaned[key] = item
            else:
                cleaned[scrub_value(key)] = scrub_value(item)
        return cleaned
    if isinstance(value, list):
        return [scrub_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(scrub_value(item) for item in value)
    if isinstance(value, BaseException):
        return scrub_text(str(value))
    return value


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
