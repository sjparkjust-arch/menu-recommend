# 변경 이력

기능/UI 변경 사항을 날짜별로 기록한다. 버그 원인 추적·해결 과정은 `docs/troubleshooting.md` 참고.

---

## 2026-07-15

- **로그인 성공 시 대시보드로 이동**
  `accounts/views.py`의 `login_view` 리다이렉트 대상을 `accounts:index` → `menus:dashboard`로 변경.

- **로그아웃 시 로그인 페이지 대신 대시보드로 이동**
  `accounts/views.py`의 `logout_view` 리다이렉트 대상을 `accounts:login` → `menus:dashboard`로 변경.

- **대시보드 비로그인 접근 허용**
  `menus/views.py`의 `dashboard`에서 `@login_required` 제거. `recommender.recommend()`가 `AnonymousUser`를 안전하게 처리하도록 수정(알러지 필터·최근 먹은 메뉴 제외·선호도 가중치는 로그인 사용자에게만 적용, 비로그인은 끼니/국가/코스 필터만 적용). 대시보드 템플릿은 비로그인 상태에서 알러지/최근 기록 영역을 로그인 유도 문구로 대체하고, 기록 추가 버튼은 숨김.

- **네비게이션에 로그인/회원가입/마이페이지 버튼 추가**
  `templates/base.html` 우측 상단에 비로그인 시 로그인·회원가입 버튼, 로그인 시 마이페이지 버튼(로그아웃 왼쪽) 추가.

- **마이페이지 "메인으로 가기" 버튼 수정**
  `accounts/templates/accounts/profile.html`에서 `accounts:index`(`/accounts/`) → `menus:dashboard`(`/`)로 이동 대상 변경.

- **대시보드에서 식사 기록 바로 추가**
  `menus/templates/menus/dashboard.html`의 "최근 먹은 음식" 카드에 `+ 오늘 뭐 먹었어?` 버튼과 Bootstrap 모달 추가. `records:create`로 그대로 POST(완료 후 `records:history`로 이동, 대시보드에 머무르게 하려면 `records/views.py`에 `next` 지원 추가 필요 — 보류 중).

- **회원가입 완료 시 팝업 후 대시보드 이동**
  `accounts/views.py`의 `signup_view`가 가입 성공 시 `accounts:login`으로 리다이렉트하던 것을 없애고, 같은 페이지에 `signup_success=True`로 다시 렌더링. `accounts/templates/accounts/signup.html`에 완료 팝업(모달) 추가, "확인" 버튼이 대시보드로 이동. 스타일은 `accounts/static/accounts/signup.css`에 페이지 톤(오렌지)에 맞춰 추가.
  - 팝업이 폼 아래에 붙어 보이는 문제 발생 → 원인은 CSS 버그가 아니라 nginx가 `staticfiles/`(collectstatic 결과물)에서 정적 파일을 서빙하는데 `collectstatic`을 다시 안 돌려서 새 CSS가 반영 안 된 것. `collectstatic` 재실행으로 해결(이 자체는 코드 버그가 아니라 배포 절차 문제라 troubleshooting.md 대신 여기 기록).

- **회원가입 아이디 입력창 자동완성 제거**
  `accounts/templates/accounts/signup.html`의 아이디 input에서 `autofocus` 제거, `autocomplete="username"` → `autocomplete="off"`. `autofocus`가 페이지 로드마다(회원가입 완료 재렌더링 시에도) 커서를 아이디 칸에 넣어 브라우저 자동완성 드롭다운이 뜨는 원인이었음.

- **회원가입 비밀번호에 특수문자 허용**
  `accounts/views.py`의 `signup_view`에서 비밀번호를 영문+숫자로만 제한하던 정규식(`^[a-zA-Z0-9]+$`) 검증 제거. 영문+숫자 혼합 필수 조건은 유지. `accounts/templates/accounts/signup.html` 안내 문구에 "특수문자 사용 가능" 추가.

- **네비게이션 인사말을 이름 기반으로 변경**
  `templates/base.html`에서 로그인 시 "{아이디}님" 대신, 성/이름을 둘 다 입력한 경우 "{성}{이름}님"으로 표시. 둘 중 하나라도 비어 있으면 기존처럼 아이디로 표시.

- **대시보드 추천에서 사이드/음료 제외, 디저트는 별도 섹션으로 분리**
  `menus/services/recommender.py`의 `recommend()`가 이제 '메인' 코스 메뉴만 추천(사이드/음료/디저트 제외). 알러지 필터·최근 제외·meal_time 필터·선호도 가중치 파이프라인을 `_recommend_from_queryset()`으로 공통 추출하고, 같은 파이프라인을 쓰는 `recommend_dessert()`를 새로 추가('디저트' 코스 전용). `menus/views.py`의 `dashboard`가 두 함수를 모두 호출해 `recommendations`/`dessert_recommendations`로 전달. `menus/templates/menus/dashboard.html`에 "오늘의 점심/저녁 추천" 아래 "오늘의 디저트 추천" 섹션 추가, 더 이상 의미 없어진 "코스별" 체크박스 필터는 제거(국가별 필터만 남김). `menus/menu_list`(전체 메뉴 목록 페이지)는 건드리지 않아 그쪽은 여전히 사이드/음료/디저트를 포함한 전체 코스를 필터링해서 볼 수 있음.

- **전체 테마를 dongbangfood.com 참고해 크림+오렌지 미니멀 톤으로 조정 (1차, 텍스트 요약만 보고 진행)**
  `static/css/theme.css` 공통 테마 수정: 브랜드 컬러를 테라코타(`#E8623D`)에서 오렌지(`#F36235`)로, 본문 텍스트를 차콜(`#263238`)로, 배경을 옅은 크림으로 변경. 그림자를 더 옅게, `main.container` 여백을 넓힘. 네비게이션 바를 그라디언트에서 플랫 오렌지로 단순화.
  → 이후 실제 스크린샷을 보니 방향이 어긋나 있어서 아래 항목으로 다시 조정함.

- **테마 2차 조정 — 실제 스크린샷 기준으로 재보정 (다크 네비바 + 피치 배경 + 임팩트 폰트)**
  실제 dongbangfood.com 스크린샷을 보니 1차 작업(플랫 오렌지 네비바, 차콜 텍스트, 옅은 크림)이 실제 사이트 톤과 반대/미스매치였음이 드러남(네비바는 오렌지가 아니라 다크 에스프레소 브라운, 배경은 옅은 크림이 아니라 짙은 피치/살구, 텍스트는 차콜이 아니라 웜 브라운, 헤드라인은 굵은 임팩트 디스플레이 폰트). `static/css/theme.css` 재조정: `--ink`를 다크 에스프레소 브라운(`#2B1B12`)으로, `--cream`을 피치톤(`#F8DFC4`)으로, `--muted`를 웜 브라운 그레이로 되돌림. 네비게이션 바 배경을 오렌지 → `var(--ink)`(다크 브라운)로 변경. `templates/base.html`에 Google Fonts "Black Han Sans" 링크 추가, h1~h4에 `--display-font`로 적용해 굵은 임팩트 헤드라인 구현. 대시보드 추천 섹션 제목 위에 히어로 스타일 점선+라벨(`.eyebrow-label`) 장식 추가.
  - 폰트 링크(`base.html`)는 Django 템플릿이라 `DEBUG=False`에서 gunicorn이 컴파일된 템플릿을 워커 메모리에 캐싱해 재시작 전까진 반영 안 됨(반면 `theme.css` 자체는 nginx가 정적 파일로 직접 서빙해 즉시 반영됨) — 색상은 바로 보이는데 폰트만 안 바뀌는 것처럼 보일 수 있음.
