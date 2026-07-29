import difflib
from typing import Dict, List

# [Part 4 guardrail] If a fix rewrites more than this fraction of the original
# lines, it is too large to review at a glance — hold it for a human even if the
# score looks safe.
MAX_AUTOFIX_CHANGE_RATIO = 0.5


def _change_ratio(original_lines: List[str], fixed_lines: List[str]) -> float:
    """Fraction of lines that differ between the original and the fix (0.0–1.0)."""
    if not original_lines:
        return 1.0
    matcher = difflib.SequenceMatcher(a=original_lines, b=fixed_lines)
    return 1.0 - matcher.ratio()


def assess_risk(
    original_code: str,
    fixed_code: str,
    issues: List[Dict[str, str]],
) -> Dict[str, object]:
    """
    Simple, explicit risk assessment used as a guardrail layer.

    Returns a dict with:
    - score: int from 0 to 100
    - level: "low" | "medium" | "high"
    - reasons: list of strings explaining deductions
    - should_autofix: bool
    """

    reasons: List[str] = []
    score = 100

    if not fixed_code.strip():
        return {
            "score": 0,
            "level": "high",
            "reasons": ["No fix was produced."],
            "should_autofix": False,
        }

    original_lines = original_code.strip().splitlines()
    fixed_lines = fixed_code.strip().splitlines()

    # Guardrail: If issues are detected but code is unchanged, don't autofix.
    # This prevents the confusion of "auto-applying" a no-op fix.
    if issues and fixed_code.strip() == original_code.strip():
        score -= 25
        reasons.append("Issues detected but code remains unchanged. Fixer may not handle these issue types.")

    # ----------------------------
    # Issue severity based risk
    # ----------------------------
    for issue in issues:
        severity = str(issue.get("severity", "")).lower()

        if severity == "high":
            score -= 40
            reasons.append("High severity issue detected.")
        elif severity == "medium":
            score -= 20
            reasons.append("Medium severity issue detected.")
        elif severity == "low":
            score -= 5
            reasons.append("Low severity issue detected.")

    # ----------------------------
    # Structural change checks
    # ----------------------------
    if len(fixed_lines) < len(original_lines) * 0.5:
        score -= 20
        reasons.append("Fixed code is much shorter than original.")

    if "return" in original_code and "return" not in fixed_code:
        score -= 30
        reasons.append("Return statements may have been removed.")

    if "except:" in original_code and "except:" not in fixed_code:
        # This is usually good, but still risky.
        score -= 5
        reasons.append("Bare except was modified, verify correctness.")

    # ----------------------------
    # Clamp score
    # ----------------------------
    score = max(0, min(100, score))

    # ----------------------------
    # Risk level
    # ----------------------------
    if score >= 75:
        level = "low"
    elif score >= 40:
        level = "medium"
    else:
        level = "high"

    # ----------------------------
    # Auto-fix policy
    # ----------------------------
    should_autofix = level == "low"

    # [Part 3 change] Never auto-apply when a High severity issue is present,
    # regardless of the numeric score. High severity means "a human should look."
    has_high_severity = any(str(i.get("severity", "")).lower() == "high" for i in issues)
    if should_autofix and has_high_severity:
        should_autofix = False
        reasons.append("High severity issue present; auto-fix disabled pending human review.")

    # [Part 4 guardrail] Refuse to auto-apply a fix that rewrites too much of the
    # file. A large diff is hard to review and more likely to change behavior,
    # so it goes to a human even when the score would otherwise allow auto-fix.
    change_ratio = _change_ratio(original_lines, fixed_lines)
    if should_autofix and change_ratio > MAX_AUTOFIX_CHANGE_RATIO:
        should_autofix = False
        reasons.append(
            f"Fix rewrites {int(change_ratio * 100)}% of the lines; too large to auto-apply."
        )

    if not reasons:
        reasons.append("No significant risks detected.")

    return {
        "score": score,
        "level": level,
        "reasons": reasons,
        "should_autofix": should_autofix,
    }
