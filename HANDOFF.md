# Handoff

이 폴더는 `ssota-labs/agent-bowl`로 옮기기 위한 스냅샷이다.

Cloud Agent(`cursor[bot]`)는 아직 `agent-bowl` 저장소에 push 권한이 없다.
권한을 받은 뒤 이 폴더에서 새 저장소로 옮긴다.

```bash
cd tmp/agent-bowl
git init -b main
git add .
git commit -m "docs: initial agent-bowl Fumadocs site"
git remote add origin https://github.com/ssota-labs/agent-bowl.git
git push -u origin main
```
