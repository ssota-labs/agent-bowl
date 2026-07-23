# Methodology

Oh My Docs treats the Fumadocs handbook as the single source of truth for
product intent. Code follows reviewed documents; documents are not reverse
engineered from an implementation after the fact.

## Dependency direction

```text
product vision → PRD → story → specification/ADR → implementation plan → code
```

Earlier artifacts describe user needs without depending on later implementation
terminology. Later artifacts cite earlier IDs through frontmatter.

## Change classes

| Class | Required planning |
|---|---|
| Product behavior | PRD, story, specification, ready plan |
| Bug fix | Existing PRD/specification, ready plan |
| Maintenance | Ready plan; specification if a contract changes |
| Documentation only | No prior plan |

## Agent responsibility

1. Resolve intent from the handbook and `AGENTS.md`.
2. Refuse to implement when required artifacts are missing or not ready.
3. Keep marker blocks and skills under CLI control (`adopt/sync`).
