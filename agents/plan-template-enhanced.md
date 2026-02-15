---
name: plan-template-enhanced
description: "Enhanced plan template with test strategy and production validation"
type: template
---

# Enhanced Plan Template

Use this structure for spec plans that include test strategy and validation gates.

## Required Sections

### 1. Project Overview
```json
{
  "title": "Brief descriptive title",
  "status": "DRAFT",
  "created": "2025-01-15T10:00:00Z",
  "description": "What are we building and why?",
  "stack": ["Flask", "React", "TypeScript", "PostgreSQL"],
  "repository": "https://github.com/user/repo"
}
```

### 2. Test Strategy ⭐ NEW

```json
{
  "test_strategy": {
    "unit_tests": {
      "framework": "pytest / jest / etc",
      "coverage_target": "90%",
      "focus": ["Core business logic", "Validation", "Authentication"]
    },
    "integration_tests": {
      "framework": "pytest / supertest / etc",
      "focus": ["API endpoints", "Database interactions", "External services"]
    },
    "production_validation": {
      "enabled": true,
      "smoke_tests": [
        "Server starts successfully",
        "Health endpoint responds",
        "Frontend loads without 404",
        "Main user flow completes"
      ]
    },
    "test_production_parity": {
      "risks": [
        "Tests use temp directories, production uses relative paths",
        "Tests mock HTTP, production uses real API calls"
      ],
      "mitigations": [
        "Add integration test with production-like directory structure",
        "Add test that starts actual server and makes HTTP requests"
      ]
    }
  }
}
```

### 3. Framework Gotchas ⭐ NEW

```json
{
  "framework_gotchas": [
    {
      "framework": "Flask",
      "gotcha": "send_from_directory requires absolute paths",
      "detection": "Check for send_from_directory calls with relative paths",
      "mitigation": "Use Path().absolute() before calling send_from_directory"
    },
    {
      "framework": "React + Vite",
      "gotcha": "Type-only imports need 'import type'",
      "detection": "Look for type imports without 'type' keyword",
      "mitigation": "Use 'import type { Type } from' syntax"
    }
  ]
}
```

### 4. Tasks

```json
{
  "tasks": [
    {
      "id": 1,
      "name": "Task name (verb + noun)",
      "description": "Detailed description of what to implement",
      "dependencies": [],
      "dod": [
        "Acceptance criterion 1",
        "Acceptance criterion 2",
        "Unit tests pass",
        "Integration tests pass"
      ],
      "files": [
        "path/to/new/file.py",
        "path/to/modified/file.py"
      ],
      "passes": false,
      "test_notes": {
        "unit_tests": "Test X, Y, Z behavior",
        "integration_tests": "Test API endpoint with real HTTP request",
        "gotchas_checked": ["Flask send_from_directory paths"]
      }
    }
  ]
}
```

### 5. Validation Plan ⭐ NEW

```json
{
  "validation": {
    "unit_test_command": "uv run pytest",
    "integration_test_command": "uv run pytest tests/integration/",
    "type_check_command": "mypy .",
    "lint_command": "ruff check .",

    "production_validation": {
      "start_command": "./start.sh",
      "health_endpoint": "http://localhost:5000/health",
      "frontend_url": "http://localhost:5000/",
      "critical_endpoints": [
        {
          "method": "POST",
          "path": "/api/register",
          "expected_status": 201
        },
        {
          "method": "POST",
          "path": "/api/login",
          "expected_status": 200
        }
      ],
      "user_flows": [
        {
          "name": "Complete authentication flow",
          "steps": [
            "Register new user",
            "Login with credentials",
            "Access protected endpoint with token",
            "Verify token persistence"
          ]
        }
      ]
    }
  }
}
```

### 6. Risks

```json
{
  "risks": [
    {
      "risk": "Static file serving breaks in production",
      "likelihood": "Medium",
      "impact": "High",
      "mitigation": "Use absolute paths, add production validation",
      "related_gotcha": "Flask send_from_directory"
    }
  ]
}
```

## Complete Example

```json
{
  "title": "Flask Authentication API with React Frontend",
  "status": "DRAFT",
  "created": "2025-01-15T10:00:00Z",
  "description": "Build a JWT-based authentication system with React SPA frontend",
  "stack": ["Flask", "React", "TypeScript", "JWT"],

  "test_strategy": {
    "unit_tests": {
      "framework": "pytest",
      "coverage_target": "90%",
      "focus": ["AuthService", "JWT validation", "Password hashing"]
    },
    "integration_tests": {
      "framework": "pytest with test_client",
      "focus": ["Flask routes", "Static file serving", "CORS"]
    },
    "production_validation": {
      "enabled": true,
      "smoke_tests": [
        "Server starts on port 5000",
        "GET /health returns 200",
        "GET / returns React HTML (not 404)",
        "Auth flow: register → login → access profile"
      ]
    },
    "test_production_parity": {
      "risks": [
        "Tests use tempfile.TemporaryDirectory(), production uses frontend/dist/"
      ],
      "mitigations": [
        "Add integration test with realistic directory structure",
        "Verify static serving with absolute paths"
      ]
    }
  },

  "framework_gotchas": [
    {
      "framework": "Flask",
      "gotcha": "send_from_directory requires absolute paths",
      "detection": "search for send_from_directory calls",
      "mitigation": "Use Path(folder).absolute()"
    }
  ],

  "tasks": [
    {
      "id": 1,
      "name": "Implement static file serving",
      "description": "Configure Flask to serve React build from frontend/dist",
      "dependencies": [],
      "dod": [
        "Flask serves index.html at /",
        "Static assets served from /assets/",
        "SPA routing works (all routes serve index.html)",
        "Tests pass with temp and real directories"
      ],
      "files": [
        "adapters/inbound/flask_routes.py",
        "tests/test_flask_routes.py"
      ],
      "passes": false,
      "test_notes": {
        "unit_tests": "Test with tempdir",
        "integration_tests": "Test with frontend/dist structure",
        "gotchas_checked": ["Use absolute paths in send_from_directory"]
      }
    }
  ],

  "validation": {
    "unit_test_command": "uv run pytest",
    "type_check_command": "mypy .",
    "lint_command": "ruff check .",

    "production_validation": {
      "start_command": "./start.sh",
      "health_endpoint": "http://localhost:5000/health",
      "frontend_url": "http://localhost:5000/",
      "critical_endpoints": [
        {"method": "GET", "path": "/", "expected_status": 200},
        {"method": "POST", "path": "/register", "expected_status": 201},
        {"method": "POST", "path": "/login", "expected_status": 200}
      ],
      "user_flows": [
        {
          "name": "Authentication flow",
          "steps": [
            "Register: POST /register → 201",
            "Login: POST /login → 200 with token",
            "Profile: GET /me with token → 200"
          ]
        }
      ]
    }
  },

  "risks": [
    {
      "risk": "Frontend returns 404 in production",
      "likelihood": "Medium",
      "impact": "High",
      "mitigation": "Use absolute paths, production validation gate",
      "related_gotcha": "Flask send_from_directory"
    }
  ]
}
```

## Usage

### During Planning (spec-plan)
1. Use this template structure
2. Fill in test_strategy section based on project needs
3. Identify framework-specific gotchas from gotchas database
4. Define production validation criteria

### During Implementation (spec-implement)
1. Reference test_strategy for each task
2. Check gotchas before finalizing code
3. Write integration tests that match production setup

### During Validation (spec-verify)
1. Run all test commands from validation section
2. Launch production-validator agent with config from validation section
3. Only mark COMPLETE if production validation passes

## Benefits

✅ **Test-Production Parity:** Explicit risks and mitigations prevent "works in test, fails in production"

✅ **Framework Awareness:** Gotchas database prevents common pitfalls

✅ **Production Gate:** Validation ensures it actually works, not just tests pass

✅ **Clarity:** Everyone knows what "done" means (tests + production)

✅ **Completeness:** No detail left to assumption
