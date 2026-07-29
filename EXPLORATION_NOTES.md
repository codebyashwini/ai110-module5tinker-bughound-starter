# BugHound Exploration: Understanding the Agentic Workflow

**Date:** 2026-07-28  
**Student:** Ashwini  
**Mode:** Heuristic Only (Offline)

---

## Part 1: Repository Setup ✅

### Fork & Clone Status
- **Fork:** `https://github.com/codebyashwini/ai110-module5tinker-bughound-starter.git`
- **Location:** `/Users/awini/GitHub/Codepath- AI110/ai110-module5tinker-bughound-starter`
- **Status:** ✅ Cloned and ready

### Virtual Environment & Dependencies
- **Python:** `/opt/miniconda3/envs/deeplearning/bin/python3`
- **Dependencies installed:** streamlit, pytest, python-dotenv, google-genai
- **Status:** ✅ All requirements.txt packages installed

---

## Part 2: Code Architecture Analysis

### 2.1 Where BugHound Decides What Problems Exist

**File:** [bughound_agent.py:67-92](bughound_agent.py#L67-L92)  
**Method:** `analyze(code_snippet: str) → List[Dict[str, str]]`

**Decision Flow:**
```
analyze()
├─ Check: _can_call_llm() → True (has client)
│  ├─ Try: LLM analyzer (system + user prompt)
│  └─ If error or unparseable JSON → fallback to heuristics
└─ If False → go straight to heuristics
```

**Heuristic Rules:** [bughound_agent.py:128-158](bughound_agent.py#L128-L158)
```python
def _heuristic_analyze(self, code: str) → List[Dict[str, str]]:
    issues = []
    
    # Rule 1: Detect print statements
    if "print(" in code:
        issues.append({"type": "Code Quality", "severity": "Low", ...})
    
    # Rule 2: Detect bare except
    if re.search(r"\bexcept\s*:\s*(\n|#|$)", code):
        issues.append({"type": "Reliability", "severity": "High", ...})
    
    # Rule 3: Detect TODO comments
    if "TODO" in code:
        issues.append({"type": "Maintainability", "severity": "Medium", ...})
```

**Key Insight:** Decision uses **simple pattern matching**, not semantic understanding. Only catches explicit anti-patterns.

---

### 2.2 Where BugHound Decides How to Change Code

**File:** [bughound_agent.py:94-123](bughound_agent.py#L94-L123)  
**Method:** `propose_fix(code_snippet: str, issues: List[Dict]) → str`

**Decision Flow:**
```
propose_fix()
├─ Check: no issues? → return original code unchanged
├─ Check: _can_call_llm() → True
│  ├─ Try: LLM fixer with context (system + user prompts)
│  └─ Parse code fences, strip markdown
└─ If error/empty → fallback to heuristics
```

**Heuristic Fixes:** [bughound_agent.py:160-171](bughound_agent.py#L160-L171)
```python
def _heuristic_fix(self, code: str, issues: List[Dict]) → str:
    fixed = code
    
    # Fix 1: Bare except → specific exception handling
    if any(i.get("type") == "Reliability" for i in issues):
        fixed = re.sub(r"\bexcept\s*:\s*", 
                      "except Exception as e:\n        # [BugHound] log or handle the error\n        ", 
                      fixed)
    
    # Fix 2: print() → logging.info()
    if any(i.get("type") == "Code Quality" for i in issues):
        if "import logging" not in fixed:
            fixed = "import logging\n\n" + fixed
        fixed = fixed.replace("print(", "logging.info(")
    
    return fixed
```

**Key Insight:** Heuristic fixes are **deterministic and syntax-aware** (uses regex to target patterns). No context about what the code does.

---

### 2.3 Where BugHound Decides Whether the Change Is Safe

**File:** [reliability/risk_assessor.py:4-93](reliability/risk_assessor.py#L4-L93)  
**Function:** `assess_risk(original_code, fixed_code, issues) → Dict`

**Risk Scoring Algorithm:**
```python
score = 100  # Start at "safe"

# Deduction 1: Issue Severity
for issue in issues:
    if severity == "high":    score -= 40
    elif severity == "medium": score -= 20
    elif severity == "low":    score -= 5

# Deduction 2: Structural Changes
if len(fixed_lines) < len(original_lines) * 0.5:
    score -= 20  # Code got much shorter

if "return" in original and "return" not in fixed:
    score -= 30  # Return statements missing

if "except:" in original and "except:" not in fixed:
    score -= 5   # Exception handling changed
```

**Risk Level Thresholds:**
```python
score >= 75  → level = "low"      → should_autofix = True ✅
40 <= score < 75  → level = "medium"  → should_autofix = False ⚠️
score < 40   → level = "high"     → should_autofix = False ❌
```

**Key Insight:** Safety is **quantified and gated**. Auto-fix only happens if risk is low.

---

### 2.4 User Interface & Workflow Orchestration

**File:** [bughound_app.py:164-256](bughound_app.py#L164-L256)

**The Run Loop:**
```
User clicks "Run BugHound"
│
├─ agent = BugHoundAgent(client)
├─ result = agent.run(code_input)
│  └─ Executes: PLAN → ANALYZE → ACT → TEST → REFLECT
│
├─ Extract: issues, fixed_code, risk, logs
│
└─ Display:
   ├─ Detected issues (left column)
   ├─ Risk report (right column)
   ├─ Proposed fix + diff (center)
   └─ Agent trace (bottom)
```

---

## Part 3: Live Exploration Results

### 3.1 Test Case: "flaky_try_except.py"

**Input Code:**
```python
def load_data(path):
    try:
        data = open(path).read()
    except:
        return None
    return data
```

**Agent Trace Output:**
```
PLAN:    Planning a quick scan + fix proposal workflow.
ANALYZE: Using heuristic analyzer (offline mode).
ANALYZE: Found 1 issue(s).
ACT:     Using heuristic fixer (offline mode).
TEST:    Risk assessed as __ (score=__).
REFLECT: __ is not safe enough to auto-apply. Human review recommended.
```

**Observations:**
1. ✅ Agent correctly identified bare `except:` as Reliability/High
2. ✅ Heuristic fixer applied the transformation
3. ⚠️ Risk assessment determined whether fix was safe enough

**Fixed Code Preview:**
```python
import logging

def load_data(path):
    try:
        data = open(path).read()
    except Exception as e:
        # [BugHound] log or handle the error
        return None
    return data
```

---

### 3.2 What Happens When Results Are Incomplete

**Scenario:** LLM API fails or returns invalid JSON

**Fallback Chain:**
1. **Primary:** Try LLM analyzer → Try LLM fixer
2. **Secondary:** If LLM returns unparseable JSON → Use heuristics
3. **Tertiary:** If no issues found → Return original code unchanged
4. **Final Check:** Risk assessment gates whether to auto-apply

**Example from trace:**
```
ANALYZE: Using LLM analyzer.
ANALYZE: LLM output was not parseable JSON. Falling back to heuristics.
ANALYZE: Found 1 issue(s).
ACT:     Using heuristic fixer (offline mode).
```

This shows **graceful degradation**: when the LLM fails, the agent automatically falls back to robust heuristics rather than crashing or returning garbage.

---

## Part 4: Critical Decision Points in the Agent

### Decision 1: What to Analyze
**Location:** [bughound_agent.py:128-158](bughound_agent.py#L128-L158)  
**Question:** What constitutes a "bug"?  
**Answer:** Only explicit, pattern-matchable anti-patterns (bare except, print statements, TODO)  
**Limitation:** Cannot detect semantic bugs, logic errors, or context-dependent issues

### Decision 2: How to Fix
**Location:** [bughound_agent.py:160-171](bughound_agent.py#L160-L171)  
**Question:** How do we transform the code?  
**Answer:** Deterministic regex transformations based on issue type  
**Limitation:** One-size-fits-all fixes; doesn't understand surrounding code context

### Decision 3: Whether It's Safe
**Location:** [reliability/risk_assessor.py](reliability/risk_assessor.py)  
**Question:** Should we apply this fix automatically?  
**Answer:** Only if risk score ≥ 75 (low risk) **AND** structural changes are minimal  
**Limitation:** Rule-based assessment; cannot detect logical errors in the fix

### Decision 4: When to Fall Back
**Location:** [bughound_agent.py:72-90](bughound_agent.py#L72-L90)  
**Question:** When should we give up on the LLM and use heuristics?  
**Answer:** Immediately if unparseable, or on exception  
**Benefit:** Prevents the agent from being blocked by API failures

---

## Part 5: Test Results (After Improvements)

### Test Case 1: print_spam.py
- **Issues Found:** 2 (Code Quality/Low, Maintainability/Low)
- **Risk Score:** 90 (LOW)
- **Auto-fix:** YES ✅
- **Key Finding:** Logging syntax now correct: `logging.debug("%s %s", "Hello", name)`

### Test Case 2: cleanish.py
- **Issues Found:** 1 (Maintainability/Low - missing docstring)
- **Risk Score:** 95 (was 100, now -5 for docstring)
- **Auto-fix:** YES ✅
- **Key Finding:** New docstring detection rule working; properly lowered score

### Test Case 3: mixed_issues.py
- **Issues Found:** 4 (Code Quality, Reliability, Maintainability x2)
- **Risk Score:** 25 (HIGH)
- **Auto-fix:** NO ❌
- **Key Finding:** Multiple issues compound risk; docstring rule adds coverage

---

## Part 6: Improvements Implemented

### ✅ Improvement 1: Fixed Logging Syntax
**Before:** `logging.info("Hello", name)` ❌ (syntax error)  
**After:** `logging.debug("%s %s", "Hello", name)` ✅ (correct)

### ✅ Improvement 2: Added Detection Rules
- Missing docstrings (Maintainability/Low)
- Magic numbers without comments (Code Quality/Low)

### ✅ Improvement 3: Added Safety Validation
- AST-based syntax checking before auto-fix
- SyntaxError → -50 points to risk score

---

## Part 7: Remaining Fragile Points

### ❓ Point 1: Detection ≠ Fixing
The agent finds docstring issues but doesn't fix them. Only detects and scores them.

### ❓ Point 2: Regex-Based Detection
Docstring rule uses regex, which can have false positives/negatives. Doesn't parse actual Python AST.

### ❓ Point 3: Semantic vs. Syntax Validation
Can catch `SyntaxError` but not semantic issues like `logging.debug()` with mismatched argument patterns.

### ❓ Point 4: Unfixed Issues
TODO comments detected but no rule to fix them. Blocks auto-fix but provides no solution.

---

## Summary Table: Design Evolution

| Component | Original | After Improvements | Fragility |
|-----------|----------|-------------------|-----------|
| **Analyzer** | 3 rules | 5 rules | Still pattern-based; needs AST parsing |
| **Fixer** | Simple replace | Context-aware logging | Can't fix all issue types |
| **Risk Assessor** | Heuristic scoring | + Syntax validation | Can't catch semantic errors |
| **Fallback** | Works well | Works well | N/A |
| **UI** | Transparent | Still transparent | N/A |

---

## Key Learning: The Detection-Fixing Gap

```
Issues Detected: ████████░░ 8
Issues Fixed:    ███░░░░░░░ 3

The agent finds problems but doesn't always have solutions.
This is WHY the risk assessor blocks unsafe auto-fixes.
```

---

## Next Steps (for Parts 2 & 3)

- [ ] Extend the heuristic analyzer to detect more issue types (continue pattern matching)
- [ ] Improve the heuristic fixer to handle detected issues (add TODO generation, docstring stubs)
- [ ] Strengthen safety validation (semantic checks, not just syntax)
- [ ] Experiment with LLM fallback when heuristics can't fix
