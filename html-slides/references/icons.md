# 아이콘

아이콘 세트 5종이 **파일로 구워져** 들어 있다. 네트워크를 쓰지 않고, `build` 하면
슬라이드 HTML 안에 그대로 박힌다 — 받는 사람이 오프라인에서 열어도 보인다.

| 세트 | 개수 | 라이선스 | 결 |
|---|---|---|---|
| `lucide` | 2,025 | ISC | 얇고 균일한 선. **고민되면 이걸 쓴다** |
| `tabler` | 6,184 | MIT | Lucide 와 비슷하나 수가 훨씬 많다 (`-fill` 변형 포함) |
| `phosphor` | 4,536 | MIT | 기하학적. `-fill` `-bold` 변형 포함 |
| `remix` | 3,229 | Apache-2.0 | 이름 끝 `-line` / `-fill` 로 갈린다 |
| `hugeicons` | 5,436 | MIT | 둥근 선. 수가 많다 |

## 찾기

~~~bash
S=<스킬디렉터리>/scripts/slidecraft.py

python3 $S icons sets                      # 어떤 세트가 있나
python3 $S icons find 상승                  # 한글 키워드도 통한다
python3 $S icons find chart --set lucide   # 세트를 정해서
~~~

한글은 자주 쓰는 것만 매핑돼 있다 (`상승` `고객` `매출` `경고` `목표` `성장` `전략`
`위험` `예산` `출시` …). 안 걸리면 영어로 찾으면 된다 — `arrow`, `chart`, `user`,
`check`, `building`. 세트마다 없는 개념도 있다 (예: hugeicons 에는 `trophy` 가 없어
`award`/`medal` 로 대신한다).

**이름은 세트마다 다르다.** 같은 개념도 Lucide 는 `trending-up`, Phosphor 는
`trend-up`, Remix 는 `line-chart-line` 이다. 통일 어휘를 만들지 않았다 —
매핑표를 관리하느니 그때그때 찾는 편이 정확하다.

그래서 **"아이콘 스타일 바꿔줘" 는 자동으로 갈아끼울 수 없다.** 세트를 바꾸려면
쓰던 아이콘을 개념별로 새 세트에서 **다시 찾아** 하나씩 교체해야 한다.
바꿀 일이 있을 것 같으면 처음에 세트를 신중히 고르는 편이 낫고, 바꿀 때는
빠뜨린 아이콘이 없는지 `grep -c '<svg class="ic' <덱>/slides/*.html` 로 세어 본다.

## 넣기

~~~bash
python3 $S icons get lucide:trending-up
# <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" …>…</svg>
~~~

이 조각을 슬라이드에 그대로 붙인다. 슬라이드 `<head>` 에 `icons.css` 링크가 있어야 한다
(`new` 로 만든 덱에는 이미 들어 있다).

~~~html
<link rel="stylesheet" href="../assets/icons.css">
...
<div class="chip">
  <svg class="ic" …>…</svg>      <!-- 칩 안의 숫자 대신 -->
</div>
<p class="t-body">
  <svg class="ic ic-inline" …>…</svg>전년 대비 38% 성장
</p>
~~~

옵션:

| | |
|---|---|
| `--cls "ic ic-lg"` | 크기 클래스 (`ic-lg` 28px · `ic-xl` 40px) |
| `--size 22px` | 크기 직접 지정 |
| `--label "매출 증가"` | 스크린리더용 설명. **없으면 장식으로 처리**(`aria-hidden`)된다 |

## 크기와 색

아이콘은 **글자처럼** 다룬다. 색은 `color` 를 따라가고(`currentColor`),
크기는 `--ic-size` 로 준다. 기본값은 `1em` 이라 옆 글자와 자동으로 맞는다.

~~~html
<span style="color:var(--accent)"><svg class="ic" …></svg></span>
<svg class="ic" style="--ic-size:32px" …></svg>
~~~

준비된 클래스: `.ic-lg` `.ic-xl` `.ic-inline` `.ic-accent` `.ic-brand` `.ic-muted`

**덱 전체의 아이콘 크기를 한 번에 바꾸려면 그 덱의 `assets/icons.css` 를 고친다.**
슬라이드마다 `--ic-size` 를 손보지 말 것 — 한 곳만 고치면 된다.

~~~css
/* <덱>/assets/icons.css */
.ic-inline { --ic-size: 1.4em; }   /* 글자 옆 아이콘을 키운다 */
.chip > .ic { --ic-size: 26px; }   /* 칩 안 아이콘 */
~~~

**단 `fill` 과 `stroke` 만은 건드리지 말 것.** 세트마다 선형
(`fill="none"` + `stroke`)과 채움형(`fill="currentColor"`)이 갈리는데, 그 값은
`<svg>` 태그에 직접 박혀 나온다. CSS 는 표현 속성을 이기므로 여기서 `fill` 을 주면
**선형 아이콘이 통째로 검게 칠해진다.**

## 어디에 넣나

업무 슬라이드에서 아이콘이 값어치를 하는 자리는 사실 몇 군데 안 된다.
**한 덱에서 아래 중 하나만 골라 끝까지 반복한다.**

| 자리 | 크기 | 언제 |
|---|---|---|
| **칩** `.chip > .ic` | 20~26px | 2×2 카드처럼 항목이 나열될 때. **순서가 중요하면 숫자를 그대로 두라** |
| **글줄 앞** `.ic-inline` | `1em` (기본) | 목록 항목, 라벨 앞. 가장 안전하고 가장 자주 쓴다 |
| **카드 좌상단** `.ic-lg` | 28px | 카드가 3~4장이고 각각 성격이 다를 때 |
| **큰 콜아웃** `.ic-xl` | 40px | 한 장에 **하나만**. 그 장의 주제를 상징할 때 |

~~~html
<!-- 글줄 앞 — 기본으로 이걸 쓴다 -->
<p class="t-body"><svg class="ic ic-inline" …></svg>엔터프라이즈가 성장을 끌었다</p>

<!-- 칩 안 — 숫자 대신. 순서가 뜻을 갖지 않을 때만 -->
<div class="chip"><svg class="ic" …></svg></div>
~~~

크기는 **두 종류를 넘기지 말 것.** 글줄용 하나, 강조용 하나면 충분하다.
세 가지 크기가 섞이면 위계가 아니라 소음이 된다.

## 고를 때

**이름만 보고 고르지 말고 실제로 봐라.** 이름이 뜻을 보장하지 않는다 —
`hugeicons:target-01` 은 과녁이 아니라 *화살이 꽂힌 과녁*이고, 순수한 과녁은
`target-03` 이다. 후보가 여러 개면 `icons get` 으로 몇 개 뽑아 슬라이드에 넣고
`shot` 으로 비교한 뒤 고른다.

**한 세트 안에서도 결을 섞지 말 것.** Remix 의 `-line` 과 `-fill`,
Phosphor 의 기본과 `-fill` 을 한 장에 같이 쓰면 세트를 섞은 것과 똑같이 보인다.
접미사까지 통일한다.

## 쓸 때 지킬 것

- **한 덱에는 한 세트만.** 섞으면 선 두께와 모서리 처리가 어긋나 조잡해 보인다
  ([design.md](design.md) — 모티프 하나를 끝까지 반복)
- **모든 항목에 아이콘을 달지 말 것.** 다 달면 아무것도 강조되지 않는다.
  칩·헤더처럼 반복되는 자리 한 종류만 정해 쓴다
- 아이콘만으로 뜻을 전하지 말 것. 옆에 글자가 있어야 한다
- 장식이면 `--label` 없이 (자동으로 `aria-hidden`), 뜻을 담으면 `--label` 을 준다
- 넣은 뒤 `qa` → `shot` 으로 **눈으로 확인.** 작은 크기에서 뭉개지는 아이콘이 있다

`qa` 가 자동으로 잡아 주는 것:

~~~
✗ [아이콘] 아이콘 세트가 섞였다 — lucide(1개) · phosphor(1개). 한 덱에는 한 세트만 쓴다
! [아이콘] remix: 아이콘 결이 섞였다 — -fill 1개 · -line 1개. 접미사까지 통일한다
~~~

세트 혼용은 **오류**(빌드 전에 고쳐야 한다), 결 혼용은 경고다.

## 다시 굽기 (버전 올릴 때만)

~~~bash
python3 scripts/build_icons.py            # 전부
python3 scripts/build_icons.py lucide     # 하나만
~~~

npm 에서 받아 아이콘 본문만 뽑는다. `npm install` 이 아니라 `npm pack` 이라
패키지의 설치 스크립트를 돌리지 않는다. 굽는 중에 스크립트·이벤트 핸들러·외부 참조가
하나라도 발견되면 **중단한다** (`DANGER` / `ALLOWED_ELS`).

라이선스 고지는 [assets/icons/LICENSES.md](../assets/icons/LICENSES.md).
