from reliability.risk_assessor import assess_risk


def test_no_fix_is_high_risk():
    risk = assess_risk(
        original_code="print('hi')\n",
        fixed_code="",
        issues=[{"type": "Code Quality", "severity": "Low", "msg": "print"}],
    )
    assert risk["level"] == "high"
    assert risk["should_autofix"] is False
    assert risk["score"] == 0


def test_low_risk_when_minimal_change_and_low_severity():
    original = "import logging\n\ndef add(a, b):\n    return a + b\n"
    fixed = "import logging\n\ndef add(a, b):\n    return a + b\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[{"type": "Code Quality", "severity": "Low", "msg": "minor"}],
    )
    assert risk["level"] in ("low", "medium")  # depends on scoring rules
    assert 0 <= risk["score"] <= 100


def test_high_severity_issue_drives_score_down():
    original = "def f():\n    try:\n        return 1\n    except:\n        return 0\n"
    fixed = "def f():\n    try:\n        return 1\n    except Exception as e:\n        return 0\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[{"type": "Reliability", "severity": "High", "msg": "bare except"}],
    )
    assert risk["score"] <= 60
    assert risk["level"] in ("medium", "high")


def test_missing_return_is_penalized():
    original = "def f(x):\n    return x + 1\n"
    fixed = "def f(x):\n    x + 1\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[],
    )
    assert risk["score"] < 100
    assert any("Return" in r or "return" in r for r in risk["reasons"])


def test_high_severity_issue_blocks_autofix():
    """Safety rule: High severity issues always require human review.

    Even with a low-severity-only assessment (high score),
    if there's a High severity issue present, autofix is blocked.
    """
    original = "def add(a, b):\n    print('adding')\n    return a + b\n"
    fixed_low = "import logging\n\ndef add(a, b):\n    logging.info('adding')\n    return a + b\n"

    # Only Low severity issue (print statement) - with actual fix applied
    risk_low_only = assess_risk(
        original_code=original,
        fixed_code=fixed_low,
        issues=[{"type": "Code Quality", "severity": "Low", "msg": "print statement"}],
    )
    assert risk_low_only["should_autofix"] is True

    # Now add a High severity issue but apply fix for both
    fixed_both = "import logging\n\ndef add(a, b):\n    logging.info('adding')\n    try:\n        return a + b\n    except Exception as e:\n        return 0\n"
    issues_with_high = [
        {"type": "Code Quality", "severity": "Low", "msg": "print statement"},
        {"type": "Reliability", "severity": "High", "msg": "bare except"}
    ]
    risk_with_high = assess_risk(
        original_code=original,
        fixed_code=fixed_both,
        issues=issues_with_high,
    )
    # High severity blocks autofix even though score is low and code is fixed
    assert risk_with_high["should_autofix"] is False


def test_unaddressed_issues_block_autofix():
    """Safety rule: If issues are detected but code is unchanged, don't autofix.

    This catches the case where the analyzer finds problems but the fixer
    can't address them (e.g., docstring issues), producing a no-op fix.
    Auto-applying a no-op is confusing and breaks the fix contract.
    """
    original = "def add(a, b):\n    return a + b\n"

    # Issues detected (missing docstring) but code unchanged (fixer can't handle it)
    risk = assess_risk(
        original_code=original,
        fixed_code=original,  # No change despite issues
        issues=[{"type": "Maintainability", "severity": "Low", "msg": "Missing docstring"}],
    )

    # Should NOT autofix when issues remain unaddressed
    assert risk["should_autofix"] is False
    assert "unaddressed" in " ".join(risk["reasons"]).lower() or risk["score"] < 75


def test_large_rewrite_is_not_autofixed_even_when_low_severity():
    # [Part 4 guardrail] A low-severity issue keeps the score high (level "low"),
    # but a fix that rewrites most of the file should still be held for a human.
    # Without the over-editing guardrail this would auto-apply; with it, it must not.
    original = "def add(a, b):\n    print(a + b)\n    return a + b\n"
    fixed = (
        "import logging\n\n"
        "def add(a, b):\n"
        "    logging.info('adding %s and %s', a, b)\n"
        "    result = a + b\n"
        "    logging.info('result is %s', result)\n"
        "    return result\n"
    )
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[{"type": "Code Quality", "severity": "Low", "msg": "print"}],
    )
    assert risk["level"] == "low"          # score is high...
    assert risk["should_autofix"] is False  # ...but the rewrite is too large to auto-apply
    assert any("too large" in r.lower() for r in risk["reasons"])
