# Production Validation Framework

Enhancements to Claude Drive that ensure implementations work in production, not just in tests.

## Problem

Traditional TDD workflow:
1. Write failing test ✅
2. Implement code ✅
3. Tests pass ✅
4. **Declare done** ❌

**Issue:** Tests passing ≠ production working

Real example from Flask + React project:
- All 64 tests passed ✅
- Production returned 404 ❌
- Root cause: `send_from_directory()` needed absolute paths
- Tests used temp directories (different behavior)

## Solution

Enhanced workflow with production validation gate:
1. Write failing test
2. Implement code
3. Tests pass
4. **Production validation** ← NEW GATE
5. Declare done only if production works

## Architecture

### 1. Production Validator Agent

**File:** `agents/production-validator.md`

**Purpose:** Validate implementation in production-like environment

**What it does:**
- Starts actual server (not test client)
- Tests real HTTP endpoints
- Verifies complete user flows
- Checks frontend loads (no 404)
- Tests static assets serve correctly
- Uses browser automation for web apps

**Output:** PASS/FAIL with detailed errors

### 2. Framework Gotchas Database

**File:** `agents/framework-gotchas.md`

**Purpose:** Prevent common test-production gaps

**Coverage:**
- Flask (static files, CORS, routing)
- React + Vite (env vars, imports, public dir)
- Next.js (client components, server components)
- Django (static files, DEBUG mode)
- Express (middleware order)
- Rails (asset pipeline)
- Docker (permissions, build context)

**Format:**
```markdown
## Flask

### Static File Serving

❌ FAILS: send_from_directory(relative_path, ...)
✅ WORKS: send_from_directory(str(Path(folder).absolute()), ...)

Why: Flask resolves relative to module, not CWD
Detection: Check for relative paths in send_from_directory
```

### 3. Enhanced Plan Template

**File:** `agents/plan-template-enhanced.md`

**New sections:**
- `test_strategy` - Unit, integration, production validation
- `test_production_parity` - Risks and mitigations
- `framework_gotchas` - Relevant gotchas for this project
- `validation.production_validation` - Smoke test criteria

**Benefits:**
- Explicit about test-production differences
- Clear validation criteria
- Framework-aware from the start

### 4. Enhanced Implementation Command

**File:** `commands/spec-implement-v2.md`

**Changes:**
- After tests pass, run framework gotcha checks
- Launch production-validator agent
- Only mark COMPLETE if validation passes
- Maximum 3 validation attempts
- Escalate to user if still failing

## Usage

### For Plan Authors

When creating a spec plan:

```bash
/spec-plan
```

Follow enhanced template structure:
1. Define test strategy (unit, integration, production)
2. Identify test-production parity risks
3. List relevant framework gotchas
4. Specify production validation criteria

### For Implementers

When implementing a plan:

```bash
/spec-implement path/to/plan.json
```

Process now includes:
1. TDD cycles (RED-GREEN-REFACTOR)
2. Full test suite validation
3. **Framework gotcha check** ← NEW
4. **Production validation** ← NEW
5. Mark COMPLETE only if all gates pass

### For Validators

Production validator runs automatically during implementation, but can be invoked manually:

```bash
# Use Task tool
agent: production-validator
input:
  - project_dir: /path/to/project
  - start_command: ./start.sh
  - endpoints: [...]
  - user_flows: [...]
```

## Example: Catching the Flask Bug

### Without Production Validation

```
1. Implement static serving with relative paths
2. Write test with tempfile.TemporaryDirectory()
3. Test passes ✅
4. Mark complete ✅
5. Deploy to production
6. **Frontend returns 404** ❌
```

### With Production Validation

```
1. Implement static serving with relative paths
2. Write test with tempfile.TemporaryDirectory()
3. Test passes ✅
4. Run production validator
   - Start actual server
   - Test GET /
   - **Returns 404** ❌
5. Check gotchas database
   - "Flask send_from_directory requires absolute paths"
6. Fix: Use Path().absolute()
7. Re-run validator
   - GET / returns HTML ✅
8. Mark complete ✅
```

**Result:** Bug caught before deployment, not after.

## Validation Criteria

### Minimum Checks (All Projects)

- [x] Server starts without errors
- [x] Health endpoint responds (if exists)
- [x] No unexpected crashes in logs

### Web Apps

- [x] Frontend URL returns HTML (not 404/500)
- [x] Static assets load (JS, CSS)
- [x] No console errors in browser
- [x] At least one page route works

### API Services

- [x] All critical endpoints return expected status
- [x] Request/response formats match spec
- [x] At least one complete user flow works

### Full Stack Apps

- [x] All of the above
- [x] Frontend can communicate with backend
- [x] CORS configured correctly (if needed)
- [x] Authentication flow works end-to-end

## Common Failures & Fixes

### 1. Static Files Return 404

**Symptom:** GET /assets/main.js → 404
**Cause:** Relative paths, wrong directory
**Fix:** Use absolute paths, verify build output location

### 2. Frontend Returns Generic Error Page

**Symptom:** GET / → Flask/Django error page
**Cause:** SPA routing not configured
**Fix:** Add catch-all route that serves index.html

### 3. API Calls Fail from Frontend

**Symptom:** CORS error, 401/403
**Cause:** CORS not enabled, wrong origin
**Fix:** Enable CORS for development, configure allowed origins

### 4. Environment Variables Missing

**Symptom:** Server crashes on startup
**Cause:** Required env vars not set
**Fix:** Add validation, document required vars

### 5. Build Artifacts Missing

**Symptom:** Static files 404
**Cause:** `npm run build` not executed
**Fix:** Add build step to start script, document in README

## Integration with Existing Workflow

### Before (Original)

```
spec-plan → spec-implement → spec-verify
            (TDD only)        (code review)
```

### After (Enhanced)

```
spec-plan → spec-implement → spec-verify
(+ gotchas) (+ prod validate) (+ production evidence)
```

### Backward Compatible

- Original workflow still works
- Enhancements are additive
- Opt-in via spec-implement-v2.md
- Can gradually adopt features

## Metrics

Track these to measure effectiveness:

- **Pre-deployment failures caught:** How many bugs caught by validator before deployment?
- **Validation success rate:** What % pass validation on first try?
- **Gotchas prevented:** How many times gotcha database prevented an issue?
- **Production incidents reduced:** Are production bugs decreasing?

## Future Enhancements

### 1. Auto-Gotcha Detection

Scan codebase and automatically check for gotcha patterns:

```bash
python scripts/check-gotchas.py --framework flask
```

### 2. Production Validator Plugins

Framework-specific validators:

```bash
# Flask validator knows about send_from_directory
# React validator checks for import type issues
```

### 3. CI/CD Integration

Run production validator in CI:

```yaml
# .github/workflows/ci.yml
- name: Unit Tests
  run: pytest
- name: Production Validation
  run: claude-drive validate --plan plan.json
```

### 4. Gotchas Auto-Update

Learn from failures and update database:

```
Validation failed: send_from_directory returned 404
→ Check if this matches existing gotcha
→ If not, add to database automatically
```

## Contributing

### Adding a New Gotcha

1. Identify the pattern (FAILS example)
2. Find the fix (WORKS example)
3. Explain why it happens
4. Add detection criteria
5. Submit PR to `agents/framework-gotchas.md`

### Improving Validator

1. Identify missing validation check
2. Add to `agents/production-validator.md`
3. Test with real project
4. Submit PR with before/after example

## References

- `agents/production-validator.md` - Validator agent definition
- `agents/framework-gotchas.md` - Gotchas database
- `agents/plan-template-enhanced.md` - Enhanced plan structure
- `commands/spec-implement-v2.md` - Implementation with validation
