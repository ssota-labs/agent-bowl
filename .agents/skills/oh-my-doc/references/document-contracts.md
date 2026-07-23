# Document contracts

## Frontmatter expectations

Planning documents carry machine-readable frontmatter. Common fields:

| Field | Used by |
|---|---|
| `id` / `ticker` | Stable identity |
| `title`, `description`, `summary` | Human and catalog display |
| `type` | Document role (`guide`, overview, …) |
| `status` / `stage` | Lifecycle |
| `prd`, `specs`, `stories` | Graph links |
| `codeAreas` | Paths a plan authorizes |
| `related` | Handbook cross-links |

Lifecycle fields:

| Kind | Field | Values |
|---|---|---|
| PRD | `status` | `draft`, `active`, `done` |
| Spec | `stage` | `draft`, `accepted`, `superseded` |
| ADR | `stage` | `accepted`, `locked`, `superseded` |
| Plan | `stage` | `draft`, `ready`, `active`, `done`, `superseded` |

`node <skill>/scripts/omd.mjs check` / `pnpm check:planning` enforce titles,
kind-prefixed IDs, `meta.json` registration, PRD→story→spec→plan references,
lifecycle states, and non-empty plan `codeAreas`. Treat IDs as immutable once
published; update the existing document instead of duplicating intent.

## Marker blocks

`AGENTS.md` and `CLAUDE.md` may contain a managed block:

```html
<!-- oh-my-docs:start -->
…
<!-- oh-my-docs:end -->
```

Only `adopt` / `sync` should create or refresh that block. Surrounding project
content outside the markers is preserved.

## Skill trees

Installed skills live under host discovery paths. Refresh them with `adopt` or
`sync` (`--force` when a local copy diverged and should be replaced).
