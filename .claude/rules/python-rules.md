---
globs: "*.py"
---

# Python Rules

## Tooling
- **Package manager:** `uv`
- **Linter/Formatter:** `ruff`
- **Test runner:** `pytest`
- **Type checking:** type hints required, `pyright` for checking

## Standards
- Use `Protocol` or `ABC` for port interfaces
- Type hints on all function signatures
- f-strings over `.format()` or `%`
- `pathlib.Path` over `os.path`
- `dataclasses` or `pydantic` for data structures

## Project Structure
```
src/<package>/
├── core/          # Business logic + ports
├── adapters/      # Inbound (HTTP/CLI) + outbound (DB/API)
└── main.py        # Wiring
tests/
├── unit/          # Core tests with fakes
└── integration/   # Adapter tests
```

## Commands
```bash
uv run pytest                    # run tests
uv run ruff check .              # lint
uv run ruff format .             # format
uv run ruff check --fix .        # autofix
```
