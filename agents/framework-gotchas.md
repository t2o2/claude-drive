---
name: framework-gotchas
description: "Database of common framework pitfalls that cause test-production gaps"
type: knowledge-base
---

# Framework Gotchas Database

Common pitfalls that make tests pass but production fail. Check implementation against these before declaring completion.

## Flask

### Static File Serving

**Gotcha:** `send_from_directory()` requires absolute paths
```python
# ❌ FAILS in production with relative paths
static_dir = "frontend/dist"  # relative
send_from_directory(static_dir, "index.html")  # Returns 404!

# ✅ WORKS - use absolute path
from pathlib import Path
static_dir = Path("frontend/dist").absolute()
send_from_directory(str(static_dir), "index.html")
```

**Why:** Flask resolves paths relative to the app module location, not CWD. In tests with temp dirs this works differently.

**Detection:**
- Code uses `send_from_directory(static_folder, ...)` where `static_folder` is from config
- Tests use temp directories but production uses relative project paths

**Fix:** Always convert to absolute: `Path(static_dir).absolute()`

---

### Route Registration Order

**Gotcha:** Catch-all routes can shadow specific routes if registered first
```python
# ❌ WRONG ORDER - catch-all registered first
@app.route('/<path:path>')  # Catches everything!
def spa(path): ...

@app.route('/api/users')    # Never reached!
def users(): ...

# ✅ CORRECT ORDER - specific routes first
@app.route('/api/users')
def users(): ...

@app.route('/<path:path>')  # Only catches non-API routes
def spa(path): ...
```

**Detection:** Routes with `<path:path>` parameter defined before specific routes

**Fix:** Always register API/specific routes before catch-all routes

---

### CORS Configuration

**Gotcha:** CORS needed for frontend dev but not in production
```python
# ❌ HARD-CODED
from flask_cors import CORS
CORS(app)  # Always enabled!

# ✅ CONFIGURABLE
if os.getenv('ENABLE_CORS') == 'true':
    CORS(app)
```

**Detection:** `CORS(app)` called unconditionally

**Fix:** Make CORS configurable via environment variable

---

## React + Vite

### Environment Variables

**Gotcha:** Vite only exposes variables with `VITE_` prefix
```typescript
// ❌ UNDEFINED in production
const apiUrl = import.meta.env.API_URL  // undefined!

// ✅ WORKS
const apiUrl = import.meta.env.VITE_API_URL
```

**Detection:** Code uses `import.meta.env.VAR` without `VITE_` prefix

**Fix:** Rename env vars: `API_URL` → `VITE_API_URL`

---

### Public Directory

**Gotcha:** Files in `public/` are copied to dist root, not `/public/`
```html
<!-- ❌ 404 in production -->
<img src="/public/logo.png">

<!-- ✅ WORKS -->
<img src="/logo.png">
```

**Detection:** Asset paths include `/public/` prefix

**Fix:** Reference public assets from root: `/logo.png` not `/public/logo.png`

---

### Type-Only Imports

**Gotcha:** TypeScript strict mode requires `import type` for types
```typescript
// ❌ Build fails with verbatimModuleSyntax
import { FormEvent } from "react"

// ✅ WORKS
import type { FormEvent } from "react"
```

**Detection:** `verbatimModuleSyntax: true` in tsconfig + type imports without `type` keyword

**Fix:** Use `import type` for type-only imports

---

## Next.js

### Client Components

**Gotcha:** useState/useEffect require 'use client' directive
```typescript
// ❌ Error: useState only works in Client Components
export function Counter() {
  const [count, setCount] = useState(0)  // Error!
  ...
}

// ✅ WORKS
'use client'

export function Counter() {
  const [count, setCount] = useState(0)
  ...
}
```

**Detection:** Component uses hooks but missing `'use client'`

**Fix:** Add `'use client'` at top of file

---

## Django

### Static Files

**Gotcha:** `DEBUG=False` requires `collectstatic`
```python
# ❌ Static files 404 in production
DEBUG = False
# static files not served!

# ✅ WORKS
# Run: python manage.py collectstatic
# Configure STATIC_ROOT
```

**Detection:** `DEBUG=False` without `STATIC_ROOT` configured

**Fix:** Set `STATIC_ROOT` and run `collectstatic` before deploy

---

## Express.js

### Middleware Order

**Gotcha:** `express.json()` must come before routes
```javascript
// ❌ req.body is undefined
app.post('/api/users', (req, res) => {
  console.log(req.body)  // undefined!
})
app.use(express.json())  // Too late!

// ✅ WORKS
app.use(express.json())  // Parse JSON first
app.post('/api/users', (req, res) => {
  console.log(req.body)  // Works!
})
```

**Detection:** `express.json()` registered after route handlers

**Fix:** Move `app.use(express.json())` before routes

---

## Rails

### Asset Pipeline

**Gotcha:** `image_tag` paths different in dev vs production
```erb
<%# ❌ Breaks in production with asset pipeline %>
<%= image_tag '/images/logo.png' %>

<%# ✅ WORKS - uses asset pipeline %>
<%= image_tag 'logo.png' %>
```

**Detection:** Image paths start with `/images/` or `/assets/`

**Fix:** Use helper without path prefix: `image_tag 'logo.png'`

---

## Docker

### File Permissions

**Gotcha:** Files created by container run as root
```dockerfile
# ❌ Host can't modify files
RUN npm run build  # Creates files as root

# ✅ WORKS - use non-root user
USER node
RUN npm run build
```

**Detection:** Dockerfile doesn't set `USER`

**Fix:** Add `USER <non-root>` before RUN commands

---

### Build Context

**Gotcha:** `.dockerignore` needed to exclude node_modules
```dockerfile
# ❌ SLOW - copies node_modules to container
COPY . .

# ✅ FAST - .dockerignore excludes node_modules
# .dockerignore:
# node_modules
# .git
```

**Detection:** Missing `.dockerignore` file

**Fix:** Create `.dockerignore` with exclusions

---

## General Patterns

### Relative vs Absolute Paths

**Symptoms:**
- ✅ Tests pass (temp directories)
- ❌ Production fails (relative paths)

**Check:**
1. Does code use relative paths from config?
2. Are paths resolved relative to module or CWD?
3. Are file operations using Path().absolute()?

**Fix:** Always convert to absolute paths before file operations

---

### Mock vs Real Dependencies

**Symptoms:**
- ✅ Tests pass (mocked HTTP)
- ❌ Production fails (real HTTP)

**Check:**
1. Do tests mock HTTP clients, database, cache?
2. Are integration tests using real services?
3. Is production using services that tests don't?

**Fix:** Add integration tests with real dependencies

---

### Environment Variables

**Symptoms:**
- ✅ Tests pass (hardcoded defaults)
- ❌ Production fails (missing env vars)

**Check:**
1. Does code have fallback defaults for env vars?
2. Are required env vars documented?
3. Does startup validate required env vars?

**Fix:** Fail fast on missing required env vars

---

## How to Use This Database

### During Implementation

Before declaring a task complete, check:
1. Does code match any gotcha patterns?
2. If yes, is it using the "WORKS" pattern?
3. If using "FAILS" pattern, fix immediately

### During Code Review

Search codebase for gotcha patterns:
```bash
# Check for Flask gotchas
grep -r "send_from_directory" --include="*.py"
# Verify uses absolute paths

# Check for React gotchas
grep -r "import.*FormEvent" --include="*.tsx"
# Verify uses "import type"
```

### During Production Validation

If validation fails with 404/500:
1. Check error against gotcha symptoms
2. Identify likely cause from database
3. Apply fix from "WORKS" pattern

---

## Contributing

When you find a new gotcha:
1. Document the pattern (FAILS example)
2. Document the fix (WORKS example)
3. Explain why it happens
4. Add detection criteria
5. Add to relevant framework section
