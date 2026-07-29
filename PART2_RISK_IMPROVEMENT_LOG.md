# Part 2.5: Risk Assessment Safety Improvement

## Objective

Understand BugHound's risk assessment logic and implement a deliberate improvement that makes the agent more conservative about auto-fixing code with critical issues.

## Analysis of Current Risk Assessment

Examined `reliability/risk_assessor.py` and found that the auto-fix decision was based purely on risk score level:

```python
# Original logic
should_autofix = level == "low"
```

This meant:
- **Level "low"** (score ≥ 75): Auto-fix allowed
- **Level "medium"** (40 ≤ score < 75): Requires human review
- **Level "high"** (score < 40): Blocks auto-fix

## The Safety Issue

While the risk scoring considered issue severity (High: -40 points, Medium: -20, Low: -5), the auto-fix decision was purely threshold-based. This created an edge case:

**Scenario:** Code with a High severity issue + some other low-risk factors that brought the overall score to 75+
- Current behavior: Might allow auto-fix
- Problem: Critical issues (like bare except blocks) deserve human review of any fix

## Improvement Implemented

Added a **safety rule** that prevents auto-fixing when High severity issues are present:

```python
# New logic
has_high_severity = any(issue.get("severity", "").lower() == "high" for issue in issues)
should_autofix = level == "low" and not has_high_severity
```

**Effect:** Now the policy is:
- Auto-fix only allowed if score is "low" **AND** no critical issues present
- High severity issues always require human review

## Testing & Verification

Created a new test case to verify the safety rule:

```python
def test_high_severity_issue_blocks_autofix():
    """Safety rule: High severity issues always require human review."""
    # ... 
    assert risk_with_high["should_autofix"] is False
```

**Test Results:**
- ✅ All 9 tests pass (including new safety rule test)
- ✅ No breaking changes to existing behavior
- ✅ Existing tests continue to validate scoring logic

### Real-World Test: mixed_issues.py

File contains:
- 4 issues (1 High severity bare except block)
- Heuristic fix: Changes except clause + adds logging + removes TODO

Assessment:
```
Score: 25 (High risk)
Should autofix: False
Reason: High severity issue present
```

## Impact

| Aspect | Before | After |
|--------|--------|-------|
| Auto-fix policy | Score-based only | Score + Issue severity check |
| High severity handling | May allow autofix if score high enough | Always blocks autofix |
| Safety coverage | Incomplete | Critical issues protected |

## Why This Matters

High severity issues represent **critical reliability problems**:
- Bare except blocks hide errors
- Missing exception handling loses context
- These patterns are worth human review

The improvement ensures:
1. **Reliability:** Critical issues never auto-fixed blindly
2. **Conservatism:** Errs on the side of human review
3. **Clarity:** The rule is explicit and testable

## Code Changes

**File:** `reliability/risk_assessor.py`
**Lines:** 93-99
**Change:** Added 4-line safety check before the auto-fix decision

**File:** `tests/test_risk_assessor.py`
**Change:** Added test case `test_high_severity_issue_blocks_autofix()` to capture the new safety rule

## Conclusion

This improvement demonstrates how to refine an AI agent's decision-making:
- **Identify edge cases** (High severity + high score)
- **Add explicit safety rules** (not just numeric thresholds)
- **Test thoroughly** (new test captures the rule)
- **Stay simple** (4 lines of code, clear intent)

The agent is now **more conservative** about critical issues while maintaining existing risk assessment logic.
