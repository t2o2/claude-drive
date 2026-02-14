---
globs: "*.rs"
---

# Rust Rules

## Tooling
- **Error handling:** `thiserror` (library errors), `anyhow` (application errors)
- **Async:** native async traits (Rust 1.75+)
- **Dependency injection:** `Arc<dyn Port>` for trait objects

## Standards
- `cargo clippy -- -D warnings` must pass with zero warnings
- `cargo fmt --check` must pass
- Use `#[must_use]` on functions returning important values
- Prefer `impl Trait` in argument position for simple generics
- Use `?` operator, avoid `.unwrap()` except in tests

## Project Structure
```
src/
├── core/          # Business logic + port traits
├── adapters/      # Inbound + outbound implementations
├── lib.rs         # Public API
└── main.rs        # Wiring + DI
tests/             # Integration tests
```

## Commands
```bash
cargo test                              # run tests
cargo clippy -- -D warnings             # lint
cargo fmt --check                       # format check
cargo check --message-format=short      # quick compile check
```
