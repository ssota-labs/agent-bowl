# 아이콘 라이선스 고지

`assets/icons/*.json` 은 아래 오픈소스 아이콘 세트에서 **아이콘 본문만 추출해** 다시 담은
것이다. 도형(path/circle/rect 등) 외에는 아무것도 들어 있지 않다 — 스크립트, 이벤트 핸들러,
외부 참조는 굽는 단계에서 검사해 하나라도 있으면 빌드가 중단된다
(`scripts/build_icons.py` 의 `DANGER` / `ALLOWED_ELS`).

전부 재배포가 허용된 라이선스이며, 원저작자 표기는 아래와 같다.

| 세트 | 패키지 | 버전 | 라이선스 | 개수 | 홈 |
|---|---|---|---|---|---|
| `hugeicons` | `@hugeicons/core-free-icons` | 4.2.3 | MIT | 5,436 | https://hugeicons.com |
| `lucide` | `lucide-static` | 1.31.0 | ISC | 2,025 | https://lucide.dev |
| `phosphor` | `@phosphor-icons/core` | 2.1.1 | MIT | 4,536 | https://phosphoricons.com |
| `remix` | `remixicon` | 4.9.1 | Apache-2.0 | 3,229 | https://remixicon.com |
| `tabler` | `@tabler/icons` | 3.46.0 | MIT | 6,184 | https://tabler.io/icons |

다시 구우려면 (버전 올릴 때만):

~~~bash
python3 scripts/build_icons.py            # 전부
python3 scripts/build_icons.py lucide     # 하나만
~~~

`npm install` 이 아니라 `npm pack` 을 쓴다 — 패키지의 설치 스크립트를 실행하지 않는다.

각 라이선스 전문은 위 홈페이지 또는 해당 npm 패키지에 포함돼 있다.
아이콘을 슬라이드에 쓰는 것 자체는 별도 표기 의무가 없으나(ISC/MIT/Apache-2.0),
아이콘 세트를 재배포하는 경우에는 이 고지를 함께 둔다.
