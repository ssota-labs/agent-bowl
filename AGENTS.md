# agent-bowl

pnpm monorepo. The only runnable product is the Fumadocs docs site `@agent-bowl/docs` (`apps/docs`). `packages/core` is a stub tsconfig used by Fumadocs' `AutoTypeTable`.

## Cursor Cloud specific instructions

- Node: this repo requires Node >=24 (`engines` in `package.json`), but the VM's default per-command `node` is v22 (a `/exec-daemon/node` shim that is prepended to `PATH`). This is handled: `~/.bashrc` prepends the Node 24 nvm bin, so fresh shells already run Node 24 with `pnpm` 11.5.2 (provided via corepack). Verify with `node --version` (should be v24.x). If a shell ever resolves to v22, run `export PATH="$HOME/.nvm/versions/node/v24.18.0/bin:$PATH"`.
- Standard commands live in `package.json` / `apps/docs/package.json` (dev/build/typecheck) and `README.md`.
- Dev server: `pnpm dev` runs `next dev --turbopack` and serves the site at `http://localhost:3000/docs`. Each doc has a raw markdown twin at `http://localhost:3000/docs/<page>.md` (served via a rewrite in `apps/docs/next.config.mjs`).
- Validation: there is no lint or automated-test setup in this repo. Use `pnpm typecheck` (`tsc --noEmit`), `pnpm build`, and `pnpm check:planning` to validate changes.
- Oh My Docs: skill runtime at `.agents/skills/oh-my-doc` (mirrored under `.cursor/skills` and `.claude/skills`). Drive it with `node .agents/skills/oh-my-doc/scripts/omd.mjs …`; contract lives in `.omd/`.
- Search: the Fumadocs search box opens but returns no results because no search backend (`/api/search`) is wired up in the code. This is a pre-existing code gap, not an environment problem — do not treat it as a setup failure.
- Content is authored in `apps/docs/content/docs/*.mdx` (Korean). `apps/docs/scripts/generate-schema-manifest.mjs` is a placeholder that writes an empty schema manifest during `prebuild`.

<!-- oh-my-docs:start -->
# Oh My Docs

This repository uses a docs-first workflow. Canonical product intent lives under
`docs/content/docs` (or `apps/docs/content/docs` when present).

## Docs-first gate

1. Classify the change as `product`, `bugfix`, `maintenance`, or docs-only.
2. Product changes require an active PRD, a story, an accepted specification, and a ready plan.
3. Bug fixes require an existing PRD/specification and a ready plan.
4. Maintenance requires a ready plan; add a specification if an observable contract changes.
5. If required documents are missing, create and review a docs-only change first.
6. An implementation PR must reference a plan that already exists on the PR base with `stage: ready|active` and covering `codeAreas`.
7. Docs-only edits under the docs content/templates trees (plus root `README.md` / `CHANGELOG.md`) are exempt. There is no general bypass.

Dependency direction:

`product vision → PRD → story → specification/ADR → implementation plan → code`

Create drafts with `node <skill>/scripts/omd.mjs new <kind> --title "…" --yes`.
Run `node <skill>/scripts/omd.mjs check` before opening an implementation PR.
<!-- oh-my-docs:end -->
