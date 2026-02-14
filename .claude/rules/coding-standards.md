---
globs: "*"
---

# Coding Standards

## Architecture
- Core business logic = standalone library with zero external dependencies
- Domain errors in core, technical errors in adapters
- Constructor injection for dependencies
- Clean architecture over backward compatibility

## Code Quality
- Comments explain "why", not "what"
- Fix all lint warnings — zero tolerance
- No dead code, no commented-out code
- Prefer editing existing files over creating new ones
- Avoid over-engineering: minimum complexity for current requirements

## Logging
- Structured logging at system boundaries
- No logging inside pure business logic

## Error Handling
- Use language-idiomatic error types
- Errors should be specific and actionable
- Don't catch errors you can't handle meaningfully
