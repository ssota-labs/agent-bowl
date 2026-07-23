# agent-bowl

독립적으로 관리되는 에이전트 생태계 패키지를 찾고, 조합해, 설치 가능한 App으로 만드는 레지스트리·플랫폼 구상이다.

현재 단계는 설계 문서 초안이다. 문서는 holiday와 같은 Fumadocs 사이트에서 관리한다.

## 문서 사이트

```bash
pnpm install
pnpm --filter @agent-bowl/docs dev
```

브라우저에서 `http://localhost:3000/docs`를 연다.

| 경로 | 역할 |
|---|---|
| `/docs` | 문서 UI |
| `/docs/<page>.md` | 에이전트용 raw markdown twin |

## Oh My Docs

이 저장소는 [Oh My Docs](https://github.com/ssota-labs/oh-my-docs) docs-first 워크플로를 사용한다. 스킬은 `.agents/skills/oh-my-doc`(및 Cursor/Claude 미러)에 있다.

```bash
pnpm check:planning
# 또는
node .agents/skills/oh-my-doc/scripts/omd.mjs check --json
node .agents/skills/oh-my-doc/scripts/omd.mjs new prd --title "…" --yes --json
```

계약·상태는 `.omd/`에 있다. 플래닝 UI 어휘는 `packages/ui`(`@oh-my-docs/ui`)에 스냅샷되어 있다.

## 레이아웃

```
apps/docs/          Fumadocs 문서 사이트 (holiday apps/docs와 동일 chrome)
packages/core/      AutoTypeTable용 stub tsconfig
packages/ui/        Oh My Docs planning vocabulary (@oh-my-docs/ui)
.omd/               Oh My Docs contract + state
.agents/skills/     oh-my-doc skill (runtime)
```

콘텐츠는 `apps/docs/content/docs/`에 있다. Package 구현·레지스트리 런타임은 아직 없다.
