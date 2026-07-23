# Planning workflow

1. Classify the change (`product`, `bugfix`, `maintenance`, or docs-only).
2. Reuse an existing artifact when it already explains the intent. Do not mint
   a new ID for the same idea.
3. Write in dependency order: vision → PRD → story → specification/ADR → plan.
4. Create drafts with `omdocs new prd|story|spec|plan|adr --title "…"` (or copy
   from `docs/templates`). Give every artifact a stable, kind-prefixed ID and
   register its filename in the sibling `meta.json`.
5. Set lifecycle states for implementation readiness:
   - PRD: `status: active`
   - Specification: `stage: accepted`
   - Plan: `stage: ready` (or `active` while implementing) with `codeAreas`
6. Review and merge planning separately from code. Do not introduce a missing
   ready plan in the same change as its implementation.
7. Validate with `omd.mjs check` / `pnpm check:planning`, and
   `pnpm check:docs-first` on implementation PRs.
