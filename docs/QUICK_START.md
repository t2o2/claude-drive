# Quick Start: Production Validation

Get one-shot project creation with production validation gates.

## TL;DR

**Problem:** Tests pass, but production returns 404/500
**Solution:** Production validation agent + framework gotchas database

## For Project Creators

### 1. Plan with Validation Criteria

```bash
/spec "Build Flask API with React frontend"
```

In the plan, add:

```json
{
  "test_strategy": {
    "production_validation": {
      "enabled": true,
      "smoke_tests": [
        "Server starts on port 5000",
        "GET / returns HTML (not 404)",
        "Auth flow: register → login → profile"
      ]
    }
  },

  "framework_gotchas": [
    {
      "framework": "Flask",
      "gotcha": "send_from_directory requires absolute paths",
      "mitigation": "Use Path().absolute()"
    }
  ]
}
```

### 2. Implement with Validation Gates

```bash
# Will automatically:
# 1. Run TDD cycles
# 2. Check framework gotchas
# 3. Run production validator
# 4. Only mark complete if ALL gates pass
```

### 3. Verify Production Works

Before declaring done, validator will:
- Start actual server
- Test all endpoints
- Verify user flows
- Report PASS/FAIL

## For Implementers

### Quick Checklist

Before marking task complete:

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Framework gotchas checked (see database)
- [ ] Production validator passes
- [ ] Server starts successfully
- [ ] Critical endpoints return expected responses
- [ ] At least one user flow works end-to-end

### Common Gotchas to Check

#### Flask Projects
```bash
# Check: Are paths absolute?
grep "send_from_directory" -r . --include="*.py"
# Should use: str(Path(folder).absolute())
```

#### React Projects
```bash
# Check: Are type imports correct?
grep "import.*FormEvent" -r . --include="*.tsx"
# Should use: import type { FormEvent }
```

#### All Web Apps
```bash
# Check: Does frontend actually load?
curl http://localhost:5000/
# Should return HTML, not 404
```

## Example: Flask + React

### Without Validation

```
✅ Tests pass (64/64)
❌ Production: GET / → 404
⏰ Time to debug: 30+ minutes
```

### With Validation

```
✅ Tests pass (64/64)
🔍 Gotcha check: send_from_directory uses relative path ⚠️
🔍 Production validation: GET / → 404 ❌
📋 Gotcha database says: "Use absolute paths"
✅ Fix applied: Path().absolute()
✅ Production validation: GET / → 200 ✓
⏰ Time to debug: 0 minutes (caught before deployment)
```

## Validation Output Examples

### PASS

```
## Production Validation: PASS

✅ Server starts: Running on http://localhost:5000
✅ Health: GET /health → 200 OK
✅ Frontend: GET / → 200 OK (HTML)
✅ Assets: GET /assets/main.js → 200 OK
✅ Auth flow:
   - POST /register → 201 Created
   - POST /login → 200 OK (token received)
   - GET /me → 200 OK (with token)

Framework Gotchas Checked:
✅ Flask send_from_directory: Using absolute paths
✅ CORS: Configurable via ENABLE_CORS env var
```

### FAIL

```
## Production Validation: FAIL

✅ Server starts: Running on http://localhost:5000
✅ Health: GET /health → 200 OK
❌ Frontend: GET / → 404 NOT FOUND

Error Details:
<!doctype html>
<title>404 Not Found</title>

Likely Cause:
Check framework-gotchas.md for "Flask static file serving"

Suggested Fix:
send_from_directory() requires absolute paths
Current: send_from_directory("frontend/dist", ...)
Should be: send_from_directory(str(Path("frontend/dist").absolute()), ...)
```

## Integration with Workflow

### Standard TDD

```
Write test → Implement → Tests pass → DONE
```

### Enhanced TDD (v2)

```
Write test → Implement → Tests pass → Check gotchas → Validate production → DONE
                                         ↓                ↓
                                    Fix issues      Fix issues
```

## FAQs

### Q: Do I need to write integration tests manually?

A: Validator runs actual server and tests it. You should still write integration tests for complex scenarios, but validator catches basic "does it work at all" issues.

### Q: What if validation keeps failing?

A: After 3 attempts, validator escalates to user. Check the error output against framework-gotchas.md for common patterns.

### Q: Can I skip validation for simple changes?

A: Original spec-implement.md still available for backward compatibility. But validation takes <1 minute and prevents hours of debugging.

### Q: Does this replace manual testing?

A: No. This catches "server won't start" and "404 errors" issues. You still need to test complex user scenarios, edge cases, etc.

### Q: What frameworks are covered?

A: Flask, Django, Express, React, Next.js, Rails, Docker. Database grows as we encounter new gotchas.

## Next Steps

1. Read [PRODUCTION_VALIDATION.md](./PRODUCTION_VALIDATION.md) for full details
2. Check [framework-gotchas.md](../agents/framework-gotchas.md) for your stack
3. Use [plan-template-enhanced.md](../agents/plan-template-enhanced.md) for next project
4. Contribute gotchas you discover!

## Contributing Gotchas

Found a new test-production gap? Add it to the database:

1. Identify pattern: What code fails in production but passes tests?
2. Find fix: What's the correct implementation?
3. Explain why: Why does it behave differently?
4. Add detection: How to automatically check for this?
5. Submit to `agents/framework-gotchas.md`

Example format:

```markdown
### Your Gotcha Name

**Gotcha:** What goes wrong
**Why:** Root cause explanation
**Detection:** How to find it
**Fix:** Correct implementation
```
