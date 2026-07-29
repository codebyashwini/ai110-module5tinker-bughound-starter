# BugHound Mini Model Card (Reflection)

Fill this out after you run BugHound in **both** modes (Heuristic and Gemini).

---

## 1) What is this system?

**Name:** BugHound  
**Purpose:** Analyze a Python code snippet, propose a fix, and run reliability checks before deciding whether the fix should be auto-applied.

**Core behavior:** BugHound implements a small agentic loop that detects code issues (using either heuristic pattern matching or Gemini API calls), proposes fixes, assesses risk, and makes a conservative auto-fix decision. It prioritizes reliability over automation—when in doubt, it defers to human review.

**Intended users:** Students learning agentic workflows, AI reliability, and human-in-the-loop decision-making patterns.

---

## 2) How does it work?

**The 5-step workflow:**

1. **PLAN** (logging only): Log that analysis and fixing will happen.

2. **ANALYZE** (heuristics + optional LLM):
   - If no LLM client available: Use heuristic pattern matching to detect issues (bare except blocks, print statements, TODO comments, missing docstrings, magic numbers).
   - If LLM available: Call Gemini API to analyze code with semantic understanding.
   - **Safety layer:** After LLM analysis, run heuristics as verification. If LLM misses a "critical" issue (Reliability + High severity), add it back. This hybrid approach prevents the agent from relying solely on the LLM and being blindsided by missed issues.

3. **ACT** (heuristics + optional LLM):
   - If no issues: Return original code unchanged.
   - Otherwise, propose a fix using either heuristic rules (convert `print()` to `logging`, change `except:` to `except Exception`) or LLM-generated code.
   - Include fallback: If LLM fails or returns empty, revert to heuristic fixer.

4. **TEST** (always heuristic, in risk_assessor.py):
   - Run explicit safety checks: syntax validation, issue severity assessment, structural change detection (missing return statements, shortened code).
   - Compute a risk score (0–100) and level (low/medium/high).

5. **REFLECT** (policy-based decision):
   - **Auto-fix policy:** Only apply fixes automatically if:
     - Risk level is "low" (score ≥ 75), **AND**
     - No High severity issues are present.
   - Otherwise, recommend human review and log the reason.

**Key distinction:**
- Heuristics: Fast, reliable, pattern-based (handles ~80% of common issues).
- Gemini: Slower but semantically aware; used to catch complex issues the patterns miss.
- Hybrid validation: Ensures critical issues are never missed by the LLM.

---

## 3) Inputs and outputs

**Inputs tested:**

1. **mixed_issues.py**: A function with multiple low-priority issues (print statements, TODO comment, missing docstring) plus one high-priority bare except block.
   - Shape: Simple 10-line function with try/except.

2. **flaky_try_except.py**: A function that opens a file, reads it, but has a bare except block that silently ignores errors without closing the file.
   - Shape: File I/O with resource leak risk.

3. **print_spam.py**: A function with multiple print statements.
   - Shape: Logging quality issue (straightforward).

4. **cleanish.py**: Already well-formed code (logging used correctly).
   - Shape: Baseline for "no issues" case.

**Output: Issue types detected**

The system reports issues with three fields: `type`, `severity` (Low/Medium/High), and `msg`.

- **Heuristic detection** finds: bare except blocks (High), print statements (Low), TODO comments (Medium), missing docstrings (Low), magic numbers (Low).
- **Gemini detection** adds: semantic code-quality issues, context-aware refactoring suggestions (e.g., resource management, error handling patterns).

**Output: Fix proposals**

- Bare except → changed to `except Exception as e:` with a comment about error handling.
- Print statements → replaced with `logging.debug()` or `logging.info()` calls; imports logging module if needed.
- Other low-severity issues → Gemini may suggest improvements, but heuristic fixer skips them (conservative).

**Output: Risk report** contains:
- `score` (0–100 integer)
- `level` ("low", "medium", "high")
- `reasons` (list of strings explaining score deductions)
- `should_autofix` (boolean—whether the agent will apply the fix automatically)

Example risk report for mixed_issues.py:
```json
{
  "score": 25,
  "level": "high",
  "reasons": [
    "High severity issue detected.",
    "Medium severity issue detected.",
    "Low severity issue detected.",
    "Low severity issue detected."
  ],
  "should_autofix": false
}
```

---

## 4) Reliability and safety rules

**Rule 1: Bare except block = High severity → blocks auto-fix**

- **What it checks:** Detects `except:` with no exception type specified.
- **Why it matters:** A bare except silently catches all exceptions, including `KeyboardInterrupt` and `SystemExit`, hiding bugs and making debugging harder. It's a reliability anti-pattern.
- **False positive:** None expected—bare except is always a problem.
- **False negative:** The heuristic uses regex `r"\bexcept\s*:\s*(\n|#|$)"` which may miss bare except on the same line as other code, but in practice Python style strongly discourages this.

**Rule 2: High severity issue present → always block auto-fix**

- **What it checks:** If any issue has `severity == "High"`, the `should_autofix` flag is forced to `False` regardless of risk score.
- **Why it matters:** Critical reliability issues (like bare except) deserve human review of the proposed fix. A bare except block needs context-aware fixing, not blind automation.
- **False positive:** Could be overly conservative if a High severity issue is pre-existing and the fixer intentionally leaves it (though our heuristic will detect and block this).
- **False negative:** None—the rule is a safety blanket that errs on the side of caution.

**Rule 3: Unaddressed issues → block auto-fix**

- **What it checks:** If issues are detected but the fixed code is identical to the original, the fixer failed to address them. In this case, deduct 25 points and log the failure.
- **Why it matters:** Auto-applying a no-op fix creates false confidence ("we fixed the issue!") when the issue remains. This is confusing and breaks the fix contract.
- **False positive:** A fixer might intentionally decline to fix certain issues (e.g., docstrings) on principle. The rule penalizes this but doesn't block auto-fix entirely—it just lowers the score.
- **False negative:** Some issues (like docstring quality) may genuinely be unfixable by heuristic rules, and the rule will correctly flag them.

**Rule 4: Syntax errors in fixed code → high risk**

- **What it checks:** Parses fixed code with `ast.parse()`. If it has syntax errors, deduct 50 points.
- **Why it matters:** Broken code is worse than unfixed code. The risk scorer must reject it before auto-applying.
- **False positive:** None—a syntax error is definitive.
- **False negative:** None—this is a hard gate.

---

## 5) Observed failure modes

**Failure Mode 1: Gemini misclassifies severity of critical issues**

*Scenario:* Running `flaky_try_except.py` (file I/O with bare except) in Gemini mode **before** the hybrid validation fix.

*What happened:*
- Heuristic detected: bare except → (Reliability, High) ✓
- Gemini detected: bare except → (Error Handling, Medium) ✗
- Gemini's output was valid JSON, so the agent trusted it and replaced the High severity with Medium.
- Result: The risk assessment scored it as medium-risk, potentially allowing auto-fix of a critical issue.

*Root cause:*
- The LLM has semantic understanding but may be trained on codebases where "bare except" is categorized differently or treated as a style issue rather than a reliability issue.
- The agent had no verification mechanism when LLM output was valid JSON (unlike parse failures, where it falls back to heuristics).

*How it was fixed:*
- Added `_validate_critical_issues()` method that runs heuristics as a **verification check after LLM analysis**.
- If heuristics find a (Reliability, High) issue and LLM missed it, the heuristic issue is added back to the result.
- Logged when this happens: `"Added X critical issue(s) from heuristics."` for transparency.

---

**Failure Mode 2: Heuristic fixer generates import overhead for print-only issues**

*Scenario:* Code with a single print statement in a small script.

*What happened:*
- Heuristic detects: print() → (Code Quality, Low)
- Heuristic fixer adds: `import logging` at the top of the file
- Even for a 5-line script, the result is now 7 lines (2 extra for import + blank line).
- Risk scorer flags: "Fixed code structure changed significantly" (length grew by 40%).

*Root cause:*
- The heuristic fixer applies a blanket rule: "print → logging" without checking if logging is already imported or if the cost-to-benefit is worth it for short scripts.
- It adds `import logging` unconditionally to avoid duplicate imports, but doesn't weigh the overhead.

*Mitigation (current):*
- Risk scorer penalizes large structural changes with `-20` points for code much shorter than fixed code.
- This doesn't block auto-fix but makes it less likely.

*A better fix (proposed):*
- Check if the file is a "test" or "short script" (few functions, few lines).
- For such files, suggest the human review the fix before auto-applying the logging import.
- Or: Don't add logging import if only one print statement exists; just suggest deletion instead.

---

## 6) Heuristic vs Gemini comparison

**What Gemini detected that heuristics did not:**

When tested on `mixed_issues.py` and `flaky_try_except.py`, Gemini added semantic insights:
- Identified "Resource Management" issue in `flaky_try_except.py` (file not closed in exception path)—the heuristic only flagged the bare except.
- Proposed more sophisticated error handling patterns (e.g., context managers, logging with exception context).
- Suggested docstring improvements with specific parameter documentation (vs. heuristic's generic "missing docstring" message).

**What heuristics caught consistently:**

- Bare except blocks (100% detection rate via regex)
- Print statements (reliable pattern match)
- TODO comments (simple string search)
- Basic structural issues (presence/absence of return statements)

**How the proposed fixes differed:**

- **Heuristic:** Mechanical, literal replacements (print → logging, except: → except Exception). Safe but may add unnecessary imports or overhead.
- **Gemini:** Contextual suggestions (e.g., "use a context manager instead of try/finally"). More sophisticated but required review.

**Risk scorer agreement:**

- Risk scorer aligned well with heuristic output: bare except = High severity, print = Low severity.
- Risk scorer initially aligned poorly with Gemini when Gemini downgraded severity (Medium for bare except). This was a design flaw, not the scorer's fault—the scorer was misled by incorrect input.
- After the hybrid validation layer was added, the scorer and agent agreed: Critical issues (bare except) are always human-review-worthy.

---

## 7) Human-in-the-loop decision

**Scenario:** Code with a bare except block in a production API handler.

```python
def handle_request(req):
    try:
        result = process_data(req.body)
        return {"status": "ok", "data": result}
    except:
        return {"status": "error"}
```

**Why auto-fix is dangerous:**
- The bare except is masking errors (could be network timeouts, missing fields, database failures, etc.).
- A fix that changes it to `except Exception` doesn't address the root problem: *which* exceptions should be caught and *how* should they be logged/reported?
- An automated fix might change exception behavior in a way that breaks callers or hides critical errors from monitoring.

**Trigger:** Bare except block detected in any function.

**Implementation location:** In `risk_assessor.py`, add a **Hard Rule** (not a score penalty) that blocks auto-fix for any code containing bare except:

```python
# Inside assess_risk(), after line 104
if "except:" in original_code:
    should_autofix = False
    reasons.append("Bare except block detected. Manual review required to understand error handling intent.")
```

Alternatively, in `bughound_agent.py` REFLECT step:
```python
if any(issue.get("type") == "Reliability" for issue in issues):
    self._log("REFLECT", "Critical reliability issue detected. Deferring to human for review of fix intent.")
```

**User message:**

```
⚠️  BugHound found a bare except block, which hides errors and makes debugging harder.
    This is a **critical reliability issue** and requires human review.
    
    Detected in line X:
      except:
    
    Suggested fix:
      except Exception as e:
          # [BugHound] log or handle the error
    
    ✋ NOT auto-applying. Please review:
       1. Which specific exceptions should be caught here?
       2. How should errors be logged/reported?
       3. Should this function propagate the error instead?
    
    Once you've reviewed the context and intent, apply the fix or suggest your own.
```

---

## 8) Improvement idea

**Proposal: Add a "minimal diff" guardrail that detects when fixes add unnecessary imports or boilerplate.**

**Rationale:**

The current system detects broken fixes (syntax errors, missing returns) and severe structural changes (code much shorter), but it doesn't catch the common case of a low-risk fix that adds overhead:

- Single print statement → introduces `import logging` (2 extra lines).
- Simple docstring addition → introduces verbose formatting (3+ extra lines).
- Add type hints → introduces `from typing import ...` (1 extra line for each type).

These fixes are *correct* but not *minimal*, and they may annoy reviewers or trigger unnecessary CI violations. A guardrail here would improve acceptance.

**Implementation (low complexity):**

1. **Track "imports added"**: After the fixer runs, compare the set of imports in fixed vs. original code.

2. **Flag if imports were added for a single-issue fix**:
   ```python
   def _check_import_overhead(original: str, fixed: str, issues: List[Dict]) -> bool:
       original_imports = _extract_imports(original)
       fixed_imports = _extract_imports(fixed)
       imports_added = fixed_imports - original_imports
       
       if len(imports_added) > 0 and len(issues) == 1:
           return True  # overhead detected
       return False
   ```

3. **Deduct risk score** (not a hard block, just a penalty like syntax errors):
   ```python
   if _check_import_overhead(original_code, fixed_code, issues):
       score -= 10
       reasons.append("Fix adds imports; verify necessity for a single-issue fix.")
   ```

4. **Test**: Add a test case:
   ```python
   def test_import_overhead_penalizes_score():
       original = "print('hi')"
       fixed = "import logging\nlogging.info('hi')"
       issues = [{"type": "Code Quality", "severity": "Low", "msg": "print"}]
       risk = assess_risk(original, fixed, issues)
       assert risk["score"] < 95  # Penalized for overhead
   ```

**Why this matters:**

- **Prevents fix churn**: Developers don't have to add noisy imports for trivial fixes.
- **Improves UX**: The agent becomes less aggressive about "perfect" fixes and more pragmatic about minimal changes.
- **Educational value**: Teaches students that automation should serve human workflows, not override them.
- **Low complexity**: ~15 lines of code, one helper function, one test.

**Trade-off**: Adds a slight bias toward "do nothing" vs. "apply a comprehensive fix." But this aligns with the agent's existing conservative philosophy.
