---
description: "Phase 2: TDD implementation with production validation gate"
user-invocable: false
model: opus
---

# Spec Implementation Phase (Enhanced)

You are in the **implementation phase** of spec-driven development with production validation.

## Input
- Path to an APPROVED plan file (JSON) in `docs/plans/`

## Process

### For each task where `passes` is `false` (in dependency order):

#### 1. RED — Write failing test
- Create or update test file following project conventions
- Write test(s) that describe the expected behavior from the `dod`
- Run ONLY the targeted test file: e.g., `uv run pytest tests/test_<module>.py -x 2>&1 | tail -20`
- It MUST fail — show the failing output

#### 2. GREEN — Write minimal implementation
- Write the minimum code to make the test pass
- Run ONLY the targeted test file again
- It MUST pass — show the passing output

#### 3. REFACTOR — Clean up
- Improve code structure, naming, duplication
- Run full test suite: e.g., `uv run pytest 2>&1 | tail -30`
- They MUST still pass — show the output
- Run linter — fix any warnings

#### 4. Completion Evidence Gate
Before marking a task as passing, you MUST:
1. Paste the EXACT test command and its output (minimum 3 lines)
2. Output must contain a recognizable pass indicator (e.g., "passed", "test result: ok", "Tests: X passed")
3. If any test fails, fix it before proceeding — do not mark `passes: true`

#### 5. Update Plan
- Read the current JSON plan file
- Set the completed task's `passes` field to `true`
- Write the updated JSON back (preserve all other fields exactly)
- Do NOT modify `name`, `description`, or `dod` fields

### After all tasks complete:

#### A. Unit/Integration Test Suite
1. Run full test suite and show output (pipe through `| tail -30`)
2. Run type checker and show output
3. Run linter and show output
4. All three must pass — paste exact output as evidence

#### B. **Production Validation Gate** 🆕

**CRITICAL:** Before marking plan as COMPLETE, validate in production environment.

##### 1. Check Framework Gotchas
- Read `agents/framework-gotchas.md`
- Search codebase for gotcha patterns relevant to this project's stack
- For each match, verify code uses "WORKS" pattern, not "FAILS" pattern
- Document any gotchas found and fixed

##### 2. Launch Production Validator Agent
```
Use Task tool with agent: production-validator

Provide:
- Project directory path
- Expected endpoints (from plan description)
- Key user flows to validate
```

The agent will:
- Start the actual application (not tests)
- Verify server starts without errors
- Test all critical endpoints return expected responses
- Validate at least one complete user flow works
- Return PASS/FAIL with detailed error information

##### 3. Handle Validation Results

**If PASS:**
- Document validation output
- Proceed to mark plan as COMPLETE

**If FAIL:**
- **DO NOT** mark plan as COMPLETE
- Read failure details from validator output
- Identify root cause (often: path issues, env vars, build artifacts)
- Fix the issue
- Re-run validator
- Maximum 3 validation attempts
- If still failing after 3 attempts, escalate to user

##### 4. Production Validation Checklist

Ensure validator checked:
- [x] Server starts successfully
- [x] Health endpoint responds (if applicable)
- [x] Frontend loads (if web app)
- [x] Static assets serve correctly
- [x] All API endpoints return expected status codes
- [x] At least one complete user flow works end-to-end
- [x] No unexpected 404/500 errors
- [x] No console errors in browser (if web app)

#### C. Final Plan Update

Only after both test suite AND production validation pass:
1. Update plan `status` to `"COMPLETE"`
2. Add `production_validated: true` field to plan
3. Add `validation_timestamp` with current ISO timestamp

## Rules
- Follow dependency order strictly — never start a task whose dependencies have `passes: false`
- Every source file change must have a corresponding test change
- Show actual command output at each step, never summarize
- Use targeted tests during RED/GREEN, full suite only at REFACTOR and phase boundaries
- **🆕 NEVER skip production validation** — tests passing ≠ production working
- If production validation fails, it's a bug that must be fixed
- If you discover the plan needs changes, note them but don't modify the plan structure without user approval
- Maximum 3 full test suite runs per session — use targeted tests otherwise

## Common Production Validation Failures

### Static File Serving (Flask, Django)
**Symptom:** Tests pass, but GET / returns 404 in production
**Cause:** Relative paths in `send_from_directory()` or similar
**Fix:** Convert to absolute paths: `Path(folder).absolute()`

### Environment Variables
**Symptom:** Tests pass (use defaults), production crashes (missing vars)
**Cause:** Required env vars not set
**Fix:** Add startup validation, document required vars

### Build Artifacts
**Symptom:** Frontend tests pass, but production serves empty/404
**Cause:** `npm run build` not executed or wrong output dir
**Fix:** Verify build artifacts exist before starting server

### CORS Issues
**Symptom:** Frontend dev works, production API calls fail
**Cause:** CORS not configured for production origin
**Fix:** Add proper CORS headers or make it configurable

## Output Format

After production validation completes:

```markdown
## Implementation Complete

### ✅ Unit Tests: PASS
<test output>

### ✅ Type Check: PASS
<type check output>

### ✅ Linter: PASS
<linter output>

### ✅ Production Validation: PASS

**Server Start:**
- Command: `./start.sh`
- Status: Running on http://localhost:5000

**Endpoint Tests:**
- GET /health → 200 OK ✓
- GET / → 200 OK (HTML) ✓
- POST /api/register → 201 Created ✓

**User Flow: Auth**
1. Register user → 201 ✓
2. Login → 200 with token ✓
3. Access protected route → 200 ✓
4. Logout → Session cleared ✓

**Framework Gotchas Checked:**
- Flask send_from_directory: Using absolute paths ✓
- CORS configuration: Configurable via env var ✓

### 📋 Plan Status
- Tasks completed: 9/9
- All tests passing: ✓
- Production validated: ✓
- Status: COMPLETE
```

If validation fails, show detailed error info before attempting fixes.
