---
globs: "*.ts,*.tsx"
---

# TypeScript Rules

## Tooling
- **Strict mode:** always enabled in tsconfig
- **Validation:** `zod` at system boundaries
- **Type checking:** `tsc --noEmit`

## Standards
- Prefer `interface` over `type` for object shapes
- Use `const` by default, `let` only when needed
- Explicit return types on exported functions
- No `any` — use `unknown` and narrow
- Barrel exports (`index.ts`) only at package boundaries

## Project Structure
```
src/
├── core/          # Business logic + port interfaces
├── adapters/      # Inbound (HTTP/CLI) + outbound (DB/API)
└── index.ts       # Wiring
__tests__/         # or colocated .test.ts files
```

## Commands
```bash
npx tsc --noEmit         # type check
npm test                 # run tests
npx eslint .             # lint (if configured)
```
