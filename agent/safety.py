import json
import logging

logger = logging.getLogger("agent.safety")

MIN_GREEN_SECONDS = 20
MAX_GREEN_SECONDS = 80
FIXED_TIME_FALLBACK = 30


class SafetyResult:
    def __init__(self, green_seconds: float, was_clamped: bool, was_fallback: bool, reason: str):
        self.green_seconds = green_seconds
        self.was_clamped = was_clamped
        self.was_fallback = was_fallback
        self.reason = reason

    def __repr__(self):
        return (
            f"SafetyResult(green_seconds={self.green_seconds}, "
            f"was_clamped={self.was_clamped}, was_fallback={self.was_fallback}, "
            f"reason={self.reason!r})"
        )


def _clamp_one(tls_id: str, proposed) -> SafetyResult:
    if proposed is None:
        return SafetyResult(
            green_seconds=FIXED_TIME_FALLBACK,
            was_clamped=False,
            was_fallback=True,
            reason=f"[{tls_id}] Missing/invalid value; used fixed-time fallback.",
        )

    try:
        proposed = float(proposed)
    except (TypeError, ValueError):
        return SafetyResult(
            green_seconds=FIXED_TIME_FALLBACK,
            was_clamped=False,
            was_fallback=True,
            reason=f"[{tls_id}] Non-numeric value; used fixed-time fallback.",
        )

    if proposed < MIN_GREEN_SECONDS:
        return SafetyResult(
            green_seconds=MIN_GREEN_SECONDS,
            was_clamped=True,
            was_fallback=False,
            reason=f"[{tls_id}] {proposed}s below minimum; clamped up to {MIN_GREEN_SECONDS}s.",
        )

    if proposed > MAX_GREEN_SECONDS:
        return SafetyResult(
            green_seconds=MAX_GREEN_SECONDS,
            was_clamped=True,
            was_fallback=False,
            reason=f"[{tls_id}] {proposed}s exceeded maximum; clamped down to {MAX_GREEN_SECONDS}s.",
        )

    return SafetyResult(
        green_seconds=proposed,
        was_clamped=False,
        was_fallback=False,
        reason=f"[{tls_id}] Within safe limits; applied as-is.",
    )


def parse_llm_response(raw_text: str) -> float | None:
    try:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()
        data = json.loads(cleaned)
        value = data.get("green_seconds")
        if value is None:
            return None
        return float(value)
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as e:
        logger.warning(f"Failed to parse LLM response: {e} | raw: {raw_text!r}")
        return None


def apply_safety_check(raw_llm_text: str) -> SafetyResult:
    proposed = parse_llm_response(raw_llm_text)
    return _clamp_one("signal", proposed)


def apply_safety_check_multi(raw_llm_text: str, expected_tls_ids: list) -> dict:
    results = {}

    parsed_list = None
    try:
        cleaned = raw_llm_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()
        parsed_list = json.loads(cleaned)
        if not isinstance(parsed_list, list):
            parsed_list = None
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as e:
        logger.warning(f"Failed to parse multi-signal LLM response: {e} | raw: {raw_llm_text!r}")
        parsed_list = None

    proposals_by_id = {}
    if parsed_list is not None:
        for item in parsed_list:
            try:
                tls_id = str(item.get("tls_id"))
                proposals_by_id[tls_id] = item.get("green_seconds")
            except (AttributeError, TypeError):
                continue

    for tls_id in expected_tls_ids:
        proposed = proposals_by_id.get(tls_id)
        results[tls_id] = _clamp_one(tls_id, proposed)

    return results
