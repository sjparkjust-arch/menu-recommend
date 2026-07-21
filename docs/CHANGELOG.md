# 변경 이력

기능/UI 변경 사항을 날짜별로 기록한다. 버그 원인 추적·해결 과정은 `docs/troubleshooting.md` 참고.

---

## 2026-07-21

- **대량 더미데이터 시드 추가 (`seed_dummy`)**
  사이트가 허전해 상호작용 데이터를 대량 생성하는 관리 명령 `menus/management/commands/seed_dummy.py` 신설. 협업추천 데모용 `seed_demo`(10명 클러스터)는 보존하고 그 위에 얹는다. 생성 규모(현재): 더미 회원 40명(+실유저/데모 포함 전체 비-admin 대상), 좋아요 1,215건, 후기 494건(음식/음식점≈7:3, 음식점 후기엔 가짜 상호명 title), 후기 좋아요 3,704건, 식사기록 1,613건, 선호도·알러지 다수.
  - **멱등성**: 선택을 전역 random이 아니라 **엔티티별 결정적 RNG**(`random.Random(user.id …)`, `random.Random(review.id …)`)로 해 재실행해도 같은 조합을 뽑는다 → `get_or_create`가 전부 기존 처리(2회차 신규 0). 식사기록은 자연키가 없어 '기록 0인 유저만' 게이트.
  - 날짜 분산: 좋아요 일부는 최근 6시간(실시간 인기 순위 반영), 후기는 최근 30일 분산 + 음식후기 일부를 오늘·최근7일에 배치(대시보드 음식후기 일간/주간 카드가 둘 다 채워지게), 식사기록은 최근 90일에 흩뿌려 달력이 꽉 차게.
  - 알러지는 신규 더미 유저 ~30%에만 부여(기존 실유저 추천 동작을 바꾸지 않기 위해). 검증: 유제품 알러지 유저 추천에서 유제품 메뉴 제외 확인. 후기 달린 메뉴 180/199, 좋아요 달린 메뉴 199/199, 전 페이지 200.

- **메뉴 목록/상세 좋아요 수가 0으로 뜨던 버그 수정**
  `catalog.menu_list_queryset`·`get_menu_with_stats`가 `like_count`를 비어 있는 자동 M2M(`Count('likes')`)로 집계하고 있었다 → 실제 좋아요가 있는 `MenuLike` 역참조(`Count('menu_likes')`)로 교정. 목록의 "N명이 좋아합니다"와 상세 좋아요 수가 실제 값으로 표시된다. (예전 좋아요 토글 카운트 버그와 동일 원인의 잔재 두 곳.)

- **페이지네이션을 10개 단위 그룹으로 변경**
  메뉴 목록·후기 목록에서 페이지 번호를 한 번에 10개까지만 노출하고, "다음"을 누르면 다음 그룹(11페이지~), "이전"은 이전 그룹으로 점프한다. 공용 헬퍼 `menus/pagination.py`의 `page_window(page_obj, per_group=10)`를 두 뷰가 공유(그룹 내 이동은 페이지 번호 클릭). 전체 페이지 번호를 다 뿌리던 방식을 대체.

- **랭킹 '오늘' 탭 데이터 채움**
  더미 후기가 최근 30일에 분산돼 '오늘' 작성분이 0이라 오늘 랭킹이 비어 있었다. `seed_dummy`의 후기 날짜 로직을 오늘 20%/최근7일 35%/최근30일 45% 버킷으로 바꿔(새 환경에서도 오늘 랭킹이 채워지게), 현재 DB에는 후기 60건을 오늘 날짜로 이동. 오늘/이번주/이번달/전체 랭킹 모두 10개 노출 확인.

- **MY밥픽 카드 개편 (개인 요약)**
  대시보드 우측 MY밥픽에 미니 통계(♥ 좋아요 · 🍽 기록 · ✍ 후기 수)와 선호 요리종류 배지(선호도 상위 3), "🎲 이 중에 랜덤으로 골라줌" 버튼을 추가. 랜덤 버튼은 찜한 메뉴(`my_bobpick`)를 `json_script`로 임베드해 클라이언트에서 하나를 뽑아 "오늘은 ○○ 어때요? →"로 인라인 표시(상세 링크). 기존 찜한 메뉴 리스트와 '많이 먹은 음식' 차트는 유지. `menus/views.py` dashboard에 `my_likes_count`/`my_records_count`/`my_reviews_count`/`my_top_cuisines`/`my_bobpick_json` 컨텍스트 추가.

- **추천 3개 동시 새로고침 버튼**
  국가별 필터 바 오른쪽에 "🔄 전체 새로고침" 버튼 추가 → 오늘의 추천·또 다른 추천·당신의 취향 3개 카드를 한 번에 재추첨. 기존 리롤 스크립트를 `reroll(box)` 함수로 리팩터해 개별 카드 새로고침과 공유(신규 엔드포인트 없이 `menus:reroll`을 3슬롯에 재사용), 현재 국가별 필터를 유지한 채 AJAX로 카드만 교체(화면 상단으로 안 튐). 비로그인도 동작.

- **마이페이지 확장: 찜한 메뉴 섹션 + 음식 통계 전체보기 페이지 + 식사 히스토리 페이지네이션**
  - **전체 새로고침 버튼을 필터 바 맨 오른쪽으로** 이동(`ms-auto`를 적용 버튼에서 전체 새로고침 버튼으로 옮김).
  - **찜한 메뉴**: 마이페이지(`profile.html`)에 좋아요한 메뉴 전체를 보는 `#liked-menus` 섹션 신설(뷰에 `catalog.liked_menus` 컨텍스트 추가). 대시보드 MY밥픽의 "찜한 메뉴"에 "전체보기 >" 링크를 달아 그 섹션(`accounts:profile#liked-menus`)으로 이동.
  - **음식 통계 전체보기**: 마이페이지 음식 통계 섹션에 "전체보기 >" 버튼 추가 → 전용 페이지 `records:food_stats`(`records/food_stats.html`, 전체 `food_count_stats` 막대그래프). 마이페이지는 top 5만, 전체 페이지는 전 음식 종.
  - **식사 히스토리 페이지네이션**: `records:history`를 15개씩 페이지네이션(`Paginator` + 공용 `page_window`), 페이지 번호 10개 그룹 방식으로 넘기며 열람.

- **마이페이지 섹션 미리보기(5개)화 + 전체보기 페이지 신설**
  마이페이지 각 섹션을 미리보기 5개만 노출하고, 각기 전체보기 페이지로 넘긴다.
  - **찜한 메뉴**: 프로필은 5개만, "전체보기 >" → `menus:liked`(`menus/liked_menus.html`, 12개씩 페이지네이션) 신설.
  - **음식 통계**: 프로필은 top 5만(기존 전체 나열 → 5개), "전체보기 >"는 기존 `records:food_stats`.
  - **최근 본 후기**: 프로필은 5개, "전체보기 >" → `reviews:recent_viewed`(`reviews/recent_viewed.html`, 최근 조회 최대 30개를 10개씩 페이지네이션) 신설.
  - **호불호(선호도)에 평점 수치 표시**: 별점(★★★★☆) 옆에 "N점" 숫자를 함께 표기.

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

- **로고 워드마크를 "BOBPICK" + 문경감홍사과체로 교체**
  `static/fonts/MungyeongGamhongApple.woff2` 추가(눈누 배포 CDN에서 다운로드해 직접 호스팅 — 외부 CDN 의존 없음). `static/css/theme.css`에 `@font-face` 등록, `.navbar-brand`에 적용. `templates/base.html`의 로고 텍스트를 "🍽️ 오늘 뭐 먹지" → "BOBPICK"으로 변경, 접시 이모지 제거, `fw-bold` 클래스 제거(Bootstrap 유틸리티가 폰트 자체 굵기를 덮어써서 볼드로 보였던 것), 폰트 크기 확대, border/outline 제거.

- **네비게이션 레이아웃 분리 + 메뉴 랭킹 페이지 추가**
  사용자 영역(이름/마이페이지/로그아웃, 비로그인 시 로그인/회원가입)을 로고 박스 밖으로 빼서 우측 상단 별도 줄로, 로고(BOBPICK)+메뉴 링크만 고동색 알약형(`border-radius: 999px`) 박스에 남김. 메뉴 링크를 "메뉴 목록/후기" 2개에서 "메뉴/후기/랭킹" 3개로 확장, 각 링크를 영문(위)+한글(아래) 2단 표기로 바꾸고 세로 구분선으로 칸을 나눔(`.nav-cells`/`.nav-cell`). 새로 추가한 "랭킹"은 실제 기능으로 구현: `menus/services/catalog.py`에 `ranking_queryset()`(후기 평점 desc → 후기 수 desc, 후기 1개 이상인 메뉴만 대상) 추가, `menus/views.py`에 `ranking` 뷰, `menus/urls.py`에 `menus:ranking` 라우트, `menus/templates/menus/ranking.html` 신설(순위 배지, 평점, 후기 수 표시).

- **네비 박스 내부 밸런스 재조정**
  로고를 왼쪽에, 메뉴 칸들을 `ms-auto`로 오른쪽 끝에 붙였더니 가운데가 텅 비어 양쪽 끝으로 쏠려 보이는 문제. `templates/base.html`에서 `ms-auto` 제거하고 로고+메뉴 칸을 한 덩어리로 묶어 박스 안에서 `justify-content: center`로 가운데 배치(`.nav-pill-inner`). 로고 오른쪽 여백(`margin-right`)을 1.5rem → 2.5rem으로, 각 메뉴 칸 좌우 패딩(`.nav-cell`)을 1.4rem → 2.2rem으로 넓혀 칸 자체도 더 여유 있게 키움.

- **동방푸드 스크린샷 재확인 후 밸런스 다시 조정 + 무료 폰트 3종 추가 + 박스 모양 변경**
  실제 참고 스크린샷을 보니 로고+메뉴가 가운데로 뭉쳐있지 않고, 로고 왼쪽에 여유를 주고 메뉴 칸이 로고 바로 뒤부터 시작하는 구조였음. `justify-content: center` → `flex-start`로 변경, 로고 오른쪽 여백 6rem, 메뉴 칸 사이 `gap: 3rem !important`(Bootstrap `.navbar-nav .nav-link`의 `padding:0` 강제를 이기기 위해 `!important` 사용)로 확대. 고동색 박스 모양을 타원(pill, `border-radius: 999px`) → 둥근 사각형(`border-radius: 1.5rem`)으로 변경. 무료 폰트 3종을 눈누/공식 배포처에서 다운받아 `static/fonts/`에 자가 호스팅:
  - 영문 라벨(MENU/REVIEW/RANKING): 카페24 모야모야(`Cafe24Moyamoya-Regular.woff2`)
  - 한글 라벨(메뉴/후기/랭킹): 처음엔 리아체(`RiaSans-ExtraBold.woff2`)로 했다가, 유일하게 배포되는 굵기가 ExtraBold라 너무 두꺼워 보여서 낭만있구미체(구미시 배포, `RomanticGumi.woff2`)로 교체. `letter-spacing: .15em` 추가로 자간도 넓힘.
  - 우측 상단 사용자 영역(이름/마이페이지/로그아웃 등): 가물치 무료고딕(`gamwulchi.associates` 공식 배포, `GamwulchiFreeGothic.woff2`) — 눈누에 없어서 원본 배포처에서 zip 받아 woff2만 추출.

- **우측 상단 사용자 영역을 텍스트 링크로, 이름/링크 구분, 여백 대칭화**
  마이페이지/로그아웃(비로그인 시 로그인/회원가입) 버튼 스타일(`btn btn-outline-primary`)을 없애고 그냥 텍스트로, 호버 시 색만 바뀌게 변경(`.user-area-link`). 이름 옆에 "님, 환영합니다" 추가. 이름(`.user-area-name`)은 클릭 안 되는 라벨이라 무채색(`--muted`)으로, 실제 클릭되는 링크만 브랜드 오렌지 볼드로 구분해서 뭐가 눌리는 건지 명확하게 함. 사용자 영역과 고동색 박스 사이 위/아래 여백을 대칭으로 맞춤 — margin은 부모(`.container`)와 collapse되어 위/아래가 다르게 보이는 문제가 있어서, 위쪽은 `.page-header { padding-top: 1.25rem }`(패딩, collapse 안 됨)로, 아래쪽은 `.user-area { margin-bottom: 1.25rem }`으로 동일하게 맞춤.

- **후기 목록에 검색 추가**
  `reviews/services.py`의 `review_queryset()`에 `search` 파라미터 추가(메뉴 이름 또는 후기 내용에 검색어 포함 여부, `Q(content__icontains=...) | Q(menu__name__icontains=...)`). `reviews/views.py`의 `ReviewListView`가 `q` GET 파라미터를 파싱해 정렬(`sort`)과 함께 유지. `reviews/templates/reviews/review_list.html`에 검색창 추가, 정렬/페이지네이션 링크에 검색어 유지, "후기 자체가 없음"과 "검색 결과 없음" 메시지 구분.

- **메뉴 좋아요 기능 추가**
  `menus/models.py`에 `MenuLike`(User↔Menu M:N, 리뷰 좋아요와 동일한 패턴) 추가, 마이그레이션 생성 및 적용. `menus/services/catalog.py`에 `like_count` annotate + `liked_menu_ids()` 헬퍼 추가. `menus/views.py`에 `menu_like_toggle`(로그인 필수, AJAX 토글) 추가, `menus/urls.py`에 `menus:like` 라우트. `menu_detail.html`/`menu_list.html`에 하트 버튼 추가(비로그인 시 로그인 페이지로 이동). 기존 `reviews/_like_script.html`이 `.like-btn` 클래스로 동작하는 범용 스크립트라 그대로 재사용, 새 JS 중복 작성 안 함. `menus/admin.py`에 `MenuLikeAdmin` 등록.

- **MY밥픽 — 좋아요한 메뉴 모아보기**
  메뉴 좋아요는 단순 카운트용이 아니라 나중에 마이페이지/대시보드에서 모아보게 할 목적이었음. `menus/services/catalog.py`에 `liked_menus(user, limit)` 추가(최근 좋아요 순). `menus/views.py`의 `dashboard`에 `my_bobpick` 컨텍스트 추가(로그인 사용자만). 대시보드 우측 칸, "최근 먹은 음식" 카드 아래에 "🧡 MY밥픽" 카드 신설 — 좋아요한 메뉴 이름(상세 링크)+요리종류 배지 표시, 비어있으면 안내 문구, 비로그인이면 로그인 유도.

- **마이페이지/대시보드 확장 5종 한 번에 진행**
  1. **마이페이지에 알러지/호불호 표시**: `accounts/views.py`의 `profile`(중복 정의된 두 번째 함수가 실제 사용되는 것 확인 후 그쪽에 반영)에 `my_allergies`/`my_preferences` 컨텍스트 추가. `profile.html`에 "🧡 MY밥픽 - 알러지 · 호불호" 카드 신설(이미 있던 `accounts.Allergy`/`accounts.UserPreference` 데이터를 보여주기만 함, 새 입력 UI는 아님).
  2. **최근 본 후기**: `reviews/models.py`에 `ReviewView`(User↔Review, `viewed_at` auto_now, unique) 추가·마이그레이션 적용. `reviews/services.py`에 `record_reviews_viewed()`(본인 후기는 제외)/`recently_viewed_reviews()` 추가. 후기 목록(`ReviewListView`)과 메뉴 상세(`menu_detail`)에서 실제로 화면에 보여준 후기를 기록. `profile.html`에 "👀 최근 본 후기" 카드 신설(`reviews/_review_item.html` 재사용) — 단, `profile.html`은 Bootstrap을 안 불러오고 있어서 이 카드가 스타일 깨질 상황이라 Bootstrap CDN 링크를 `<head>`에 추가함.
  3. **랭킹 기간 탭 + 대시보드 미리보기**: `catalog.ranking_queryset()`에 `period`(`today`/`week`/`month`/전체) 파라미터 추가 — `Avg`/`Count`에 `filter=Q(...)`를 걸어 해당 기간 후기만 집계(다른 메뉴 데이터엔 영향 없음). `/menus/ranking/`에 기간 탭 UI 추가. 대시보드 우측 칸에 "🏆 이번주 인기 메뉴" TOP3 미리보기 카드 신설(전체 랭킹 페이지 링크 포함).
  4. **음식 섭취 통계**: `records/services.py` 신설, `food_count_stats(user, limit)`(음식 이름별 횟수 집계). 대시보드 "최근 먹은 음식" 카드 하단에 간략히(TOP3 한 줄), 마이페이지에 "📊 음식 통계" 카드로 전체 목록 상세 표시.
  5. **최근 먹은 음식 달력형으로 변경**: `records/services.py`에 `meal_calendar(user, year, month)` 추가(Python `calendar` 모듈로 일요일 시작 주 단위 그리드 생성, 그 달 식사 기록을 날짜별로 매핑). 대시보드 우측 칸의 "최근 먹은 음식" 리스트를 달력 표로 교체, `?cal_year=&cal_month=`로 이전/다음 달 이동, 오늘 날짜는 강조 표시. `static/css/theme.css`에 `.meal-calendar` 스타일 추가(좁은 우측 칸에 맞춰 아주 작은 폰트로 압축).

- **홈페이지(대시보드)에서 알러지 관련 UI 제거**
  상단 "알러지 자동 제외 안내" 배너 삭제(비로그인 시 로그인 유도 문구만 간단히 남김), 추천/디저트 결과 없음 안내 문구에서 "알러지·" 언급 제거, 뷰의 `allergies` 컨텍스트도 정리. **하드 제외 로직(`recommender.py`)은 CLAUDE.md 절대원칙 5에 따라 그대로 유지** — 화면 표시만 없앤 것이고 실제 필터링은 그대로 동작함. 마이페이지 알러지 표시, 메뉴 목록/상세의 알러지 경고는 "홈페이지"가 아니라서 유지.

- **대시보드 추천 카드에서 "무관" 배지 제거**
  "오늘의 점심/저녁 추천" 카드에 `meal_time` 배지가 "무관"으로 뜨면 제목과 모순돼 보여서 혼란스러움 → `menu.meal_time != 'any'`일 때만 배지 표시하도록 변경(점심/저녁처럼 특정 끼니인 메뉴는 그대로 표시). 메뉴 목록/상세 페이지는 그대로 둠(전체 메뉴를 훑어보는 페이지라 "무관" 정보가 의미 있음).

- **디저트 추천 제거, 점심/저녁 추천 동시 표시로 변경**
  대시보드의 점심/저녁 토글 방식(둘 중 하나만 보임) + 별도 디저트 섹션 구조를 없애고, "☀️ 점심 추천"/"🌙 저녁 추천" 두 섹션을 항상 같이 보여주는 구조로 변경. `menus/views.py`의 `dashboard`가 `recommend()`를 점심/저녁 각각 호출해 `lunch_recommendations`/`dinner_recommendations`로 전달, 필터 폼에서 끼니 토글 버튼 제거(국가별 필터 + 다시 추천받기만 남김). `menus/services/recommender.py`의 `recommend_dessert()`/`DESSERT_COURSE_NAME`는 더 이상 쓰이지 않아 삭제.

- **국가별 필터 제거, 추천 개수 1개로 축소, 새로고침 버튼 단순화**
  대시보드에서 국가별(cuisine) 체크박스 필터 폼을 완전히 제거(`menus/views.py`에서 관련 파싱/컨텍스트도 정리). `RECOMMEND_LIMIT`을 3 → 1로 낮춰 점심/저녁 각각 1개씩만 추천. 필터 폼 전체를 "🔄 다시 추천받기" 버튼 하나(대시보드로의 단순 링크)로 교체.

- **점심/저녁 추천을 가로 2단 커스텀 카드로 재디자인**
  기존 Bootstrap 표준 카드 그리드(`row-cols-md-3`) 대신 전용 CSS(`.meal-pick-card` 등)로 새로 디자인. `col-md-6` 두 칸에 점심/저녁 카드를 나란히 배치, 헤더에 그라디언트(점심: 오렌지/옐로, 저녁: 다크브라운/퍼플), 메뉴 이름은 `--display-font`(Black Han Sans)로 크게 강조, 카드 전체가 상세 페이지로 가는 링크. 추천이 없을 때는 카드 안에서 중앙 정렬된 안내 문구 표시.

- **개인화(협업 필터링) 추천 알고리즘 도입 + 대시보드 추천 영역 재구축**
  `menus/services/recommender.py`의 기존 `recommend()`/`_recommend_from_queryset()`를 걷어내고 하이브리드 `recommend_personalized(user, meal_time=None, limit)`로 교체. 파이프라인: (하드 제외) 알러지 포함 메뉴(절대원칙 5)·최근 7일 먹은 메뉴·이미 좋아요한 메뉴 제외 → (점수화) 세 신호의 가중합 `W_COLLAB*협업 + W_PREF*요리종류선호 + W_POP*인기도`. 협업 신호 = 내가 좋아요/후기/먹은 메뉴와 겹치는 다른 사용자(피어)들이 좋아요·고평점(≥4)한 메뉴. 최종 점수를 가중치로 `_weighted_sample`(A-Res) 확률 추출해 "다시 추천받기"마다 변주. 각 메뉴에 추천 이유(`rec_reason`: "취향이 비슷한 분들의 픽" / "○○ 좋아하는 당신께" / "지금 인기 있는 메뉴") 부착. 비로그인·데이터 없음이면 협업·선호가 0이 되어 인기도+랜덤 폴백으로 자연 동작.
  - `menus/views.py` `dashboard`: 점심/저녁 각 1개(`recommend_personalized(meal_time=..., limit=1)`) + "당신을 위한 추천" 그리드(`for_you_recommendations`, `limit=6`) 컨텍스트 추가.
  - `menus/templates/menus/dashboard.html`: 점심/저녁 카드에 추천 이유 라벨 추가, 그 아래 "🎯 당신을 위한 추천" 그리드 신설(추천 이유 라벨 포함). `static/css/theme.css`에 `.rec-reason`/`.for-you-card` 스타일 추가.
  - 참고: `MealRecord`는 `Menu` FK가 없어 먹은 메뉴 신호는 `food_name`↔`Menu.name` 이름매칭으로 근사(기존 코드와 동일한 lossy 방식).

- **협업 추천 데모용 샘플 데이터 시드 추가**
  `menus/management/commands/seed_demo.py` 신설. 취향 클러스터(한식/일식/양식)별로 좋아요가 일부 겹치고 일부 다른 가짜 사용자 6명(비번 `bobpick123!`) + 좋아요/후기/식사기록/선호도를 `get_or_create`(idempotent)로 생성. 마스터 데이터 `seed_data`는 건드리지 않음. `demo_hansik1` 등으로 로그인하면 같은 취향 사용자가 좋아한 '내가 아직 안 누른' 메뉴가 "취향이 비슷한 분들의 픽"으로 추천되는 걸 바로 확인 가능.

- **메뉴 목록에서 사이드/디저트/음료 제외 (메인 코스만)**
  `menus/services/catalog.py`의 `menu_list_queryset()`에 `main_only` 옵션 추가(True면 `course__name='메인'`), 더 이상 쓰이지 않는 `course_ids` 파라미터 제거. `menus/views.py`의 `menu_list`가 `main_only=True`로 호출하고 course 관련 파싱/컨텍스트 정리. `menus/templates/menus/menu_list.html`에서 무의미해진 "코스별" 체크박스 필터와 카드의 상수 "메인" 코스 배지 제거(국가별 필터만 남김). 메뉴 목록은 이제 메인 30개만 노출.

- **랭킹에서도 사이드/디저트/음료 제외 (메인 코스만)**
  `menus/services/catalog.py`의 `ranking_queryset()`에 `course__name='메인'` 필터 추가. 랭킹 페이지(`/menus/ranking/`)와 대시보드 "이번주 인기 메뉴" 미리보기가 같은 함수를 써서 둘 다 메인 코스만 노출. 전 기간(전체/오늘/이번주/이번달) 모두 적용.

- **메뉴 추천을 알고리즘 3종 × 점심/저녁 구조로 재설계**
  기존 하이브리드 단일 함수(`recommend_personalized`)를 걷어내고, `menus/services/recommender.py`에 `recommend_meal(user, meal_time)`을 새로 작성 — 한 끼니에 대해 **서로 다른 알고리즘 3개로 각 1개씩**, 중복 없이 추천:
  1. **취향이 비슷한 분들의 픽** (user-based 협업): 내 좋아요/후기/먹은 메뉴와 겹치는 다른 사용자들이 좋아요·고평점(≥4)한 메뉴.
  2. **○○ 좋아하는 당신께** (item-based 협업): 내 좋아요 목록에서 음식 ○○을 랜덤으로 고르고(새로고침마다 바뀜), ○○을 좋아하는 사람들이 함께 좋아하는 다른 메뉴를 추천. 라벨에 실제 음식명 + 을/를 조사(`_eul_reul`, 받침 판정)를 자동 삽입("삼겹살을", "불고기를").
  3. **지금 인기 있는 메뉴** (인기도): 좋아요 수 + 평균 평점.
  하드 제외(알러지 절대원칙5·최근 7일 먹은 메뉴·이미 좋아요)는 항상 적용, '메인' 코스만. 비로그인/데이터 없음이면 1·2번이 결과를 못 내 인기도 폴백으로 채움.
  - `menus/views.py` `dashboard`: `lunch_picks`/`dinner_picks`(각 3개) 컨텍스트. `menus/templates/menus/dashboard.html`: "☀️ 점심 추천"/"🌙 저녁 추천" 각각 3열 카드 그리드로 교체(기존 meal-pick 2단 카드 + '당신을 위한 추천' 그리드 제거), 각 카드에 추천 이유 라벨. `static/css/theme.css`: 안 쓰는 `.meal-pick-*`/`.for-you-card` 제거, `.rec-card` 추가.

- **협업 추천 데모 시드 확대 (가상 회원 10명)**
  `menus/management/commands/seed_demo.py`의 가짜 사용자를 6명 → 10명(한식4·일식3·양식3)으로 늘리고 클러스터 내 좋아요를 더 촘촘히 겹치게, 저녁 전용 메뉴(삼겹살/스테이크)도 여러 명이 좋아요하도록 설계 → user-based·item-based 협업이 점심/저녁 양쪽에서 결과를 낸다. `python manage.py seed_demo`로 재실행(idempotent). `demo_hansik1`(비번 `bobpick123!`) 등으로 로그인하면 세 알고리즘 카드가 각각 다르게 뜨는 걸 확인 가능.

- **추천 영역을 5개 카드 구성으로 재설계 (item-based 폐기)**
  "○○ 좋아하는 당신께"(item-based) 방식이 실사용에서 별로여서 제거하고, `recommend_meal`을 `recommend_dashboard(user)`로 교체. 대시보드에 5개 카드를 서로 다른 방식으로 각 1개씩(중복 없이):
  - 위: **☀️ 점심 랜덤** / **🌙 저녁 랜덤** (해당 끼니 후보 중 무작위)
  - 아래: **🏆 오늘의 BEST 메뉴**(평균 평점 가중) / **🔥 지금 인기 있는 메뉴**(좋아요 수 가중) / **🎯 당신의 취향을 담은**(협업 피어 + 요리종류 선호도)
  하드 제외(알러지·최근 먹은·이미 좋아요)·'메인' 코스 한정은 유지. `menus/views.py`는 `recs` 딕셔너리 하나로 전달, `menus/templates/menus/_rec_card.html` 파티셜 신설(제목 헤더+메뉴 1개, variant별 헤더 색상), `dashboard.html`은 include로 5장 배치. `static/css/theme.css`의 `.rec-card`/`.rec-reason` 제거하고 `.rec-box*` 추가(카드별 그라디언트 헤더).

- **오늘의 BEST / 지금 인기 카드를 결정적(실시간 데이터 반영)으로 변경**
  두 카드가 확률 추출이라 새로고침마다 바뀌던 문제 수정. `menus/services/recommender.py`에서 `_pick_best`는 평균 평점 1위(동점이면 후기 수→이름 순)로 **결정적 선택**(하루 종일 고정, 후기 쌓이면 반영), `_pick_popular`는 **최근 `POPULAR_HOURS`(6시간) 내 좋아요 최다**(실시간, 그 시간창에 없으면 전체 좋아요로 폴백)로 변경. 두 카드를 먼저 확정하고 랜덤/취향 카드가 이들을 피해 뽑도록 순서 조정(중복 방지 + 진짜 1위 보장). 점심/저녁 랜덤·당신의 취향은 계속 새로고침마다 변주. `_avg_ratings`를 (평균,후기수) 반환하는 `_rating_stats`로 대체.

- **대시보드 달력 날짜 클릭 → 그날 상세 + 많이 먹은 음식 막대 그래프(MY밥픽)**
  `records/services.py`의 `meal_calendar()`가 날짜별 상세 기록(`records_by_day` = {일: [{food, meal, rating}]})과 그 달 총 기록 수(`total`)도 반환하도록 확장. `dashboard.html`: 기록 있는 날 셀을 클릭 가능한 버튼(오렌지 점+개수)으로, `{{ ...|json_script:"cal-records" }}`로 그 달 데이터를 심고, `#dayDetailModal` + `extra_js` 인라인 스크립트로 클릭 시 그날 음식/끼니/별점을 Bootstrap 모달에 표시. 달력 하단에 "이번 달 총 N끼 기록" 요약 추가. 카드 하단의 텍스트형 "많이 먹은 음식"을 없애고, **MY밥픽 카드 안**에 가로 막대 그래프(top 5)로 이동 — 단일 시리즈 magnitude라 범례 없이 브랜드 오렌지 단색, 막대 폭 ∝ 횟수/최댓값(`{% widthratio %}`), 막대 끝에 횟수 직접 라벨(순수 CSS, 외부 라이브러리 없음). `menus/views.py`는 `food_stats`(top5)+`food_stats_max` 전달. `static/css/theme.css`에 `.cal-clickable`/`.cal-dot`/`.food-bar*` 추가.
  - 지난 날짜에 "기록 추가"는 미지원(`MealRecord.created_at`이 `auto_now_add`라 과거 날짜 지정 불가 — 모델 변경 필요). 이번엔 조회 상세만.

- **(버그 수정) 달력이 항상 비어 보이던 문제 — `created_at__month` 시간대 이슈**
  `records/services.meal_calendar()`가 `created_at__year=…, __month=…`로 필터했는데, MariaDB 시간대 테이블 미적재 상태에서 `__month`가 `CONVERT_TZ` NULL로 0건을 반환해 달력이 늘 비어 있었음. 로컬 기준 한 달 datetime 범위(`created_at__gte/__lt`, 단순 비교)로 교체해 해결. 자세한 원인/추적은 `docs/troubleshooting.md` 참고.

## 2026-07-20

- **추천 영역: 국가별 필터 + 카드별 다시추천 + 새로고침 유지 + 하단 실시간 인기 순위**
  대시보드 "오늘의 메뉴"에 국가별(한/중/일/양) 체크박스 필터 추가(점심/저녁/취향에만 적용). 점심/저녁/취향 카드에 각각 "🔄 다시 추천받기" 버튼(헤더). **추천이 새로고침해도 안 바뀌고, 버튼(또는 필터 변경) 눌러야만 바뀌게** — 확률적 슬롯(lunch/dinner/taste)을 세션(Redis)에 고정(핀). `recommend_dashboard(user, cuisine_ids, pinned, reroll)`로 확장(핀 유효하면 유지, reroll 슬롯/필터변경 시 재추첨), `_pick_meal`/`_pick_taste`에 `preferred_id`·cuisine 인자. BEST/지금인기는 이미 결정적이라 그대로. 픽 순서를 핀 슬롯 먼저 → BEST/인기 나중으로 바꿔 핀 안정성 보장. 5카드 아래 "🔥 실시간 인기 순위" 리스트 추가 — `catalog.recent_popular_menus()`(최근 6시간 좋아요 우선 정렬, 부족하면 전체 인기로 채워 top5 유지, 총 좋아요 수 표시). `menus/views.py` dashboard가 세션 핀 읽기/쓰기 + cuisine/reroll 파싱. `_rec_card.html`에 `reroll_url` 인자, `theme.css`에 리롤 버튼 스타일.

- **메뉴 목록: 좋아요를 사진 위로, 별점은 상세에만**
  `menu_list.html`에서 좋아요 버튼을 카드 이미지 우측 상단(`position-absolute top-0 end-0`, `like-btn-float` z-index로 stretched-link 위에)으로 이동해 목록에서 바로 클릭. 기존 별점/좋아요 flex row 제거하고 카드 하단에 "❤️ N명이 좋아합니다" 텍스트. 별점(⭐)은 목록에서 빼고 상세 페이지에만 유지(상세는 기존대로). 좋아요 토글 JS/엔드포인트는 그대로(클래스/속성 유지).

- **후기 분류: 음식 후기 / 음식점 후기**
  `Review.review_type` CharField(choices food/place, default food) 추가 + 마이그레이션 `0003`(기존 후기는 '음식 후기'로). `ReviewForm`에 라디오, `services.review_queryset(..., review_type)` 필터, `ReviewListView`가 `?type=` 파싱(정렬·검색과 함께 유지), `review_list.html`에 탭(전체/음식/음식점), `review_form.html`에 종류 선택, `_review_item.html`에 종류 배지.

- **(분업 메모)** 이번 작업은 `feature/template-update-sang`. 캘린더(우측 달력 카드·JS) 및 상단 네비 게임 셀은 미변경(캘린더=팀원 담당, 게임=다음 세션 `menus:games`로 돌림판/사다리/음식 이상형 월드컵 예정).

- **대시보드/목록/후기 UI 다듬기 (같은 날 후속)**
  실시간 인기 순위를 TOP 3로 줄이고 추천 영역 최상단(필터 위)으로 이동. "오늘의 메뉴"·"실시간" 점선 라벨(eyebrow) 제거, 우측 "이번주 인기 메뉴" 카드 제거(하단 순위와 중복). 메뉴 목록 좋아요 하트를 분홍색(#EC4899)으로(미좋아요=흰 배경+분홍 하트, 좋아요=분홍 배경), "N명이 좋아합니다" 텍스트도 하트색에 맞춤. 여러 줄 `{# #}` 주석이 그대로 렌더되던 문제(`_rec_card.html`·`_review_item.html`)를 `{% comment %}`로 교체. 세로로 겹쳐 보이던 메뉴/후기 검색폼을 Bootstrap `input-group`으로 바꿔 가로 정렬 고정.

- **리롤 후 새로고침 재추첨 버그 수정 + 순위 표시 정리**
  "다시 추천받기"를 누르면 URL에 `?reroll=<slot>`이 남아 새로고침마다 계속 재추첨되던 문제를 PRG(리롤 처리 후 세션 저장 → 필터만 남긴 깨끗한 URL로 302 리다이렉트)로 수정 — 이제 리롤은 1회성, 이후 새로고침은 고정. 실시간 인기 순위에서 우측 ❤️ 좋아요 수 표시를 제거하고, 순위 숫자(1·2·3) 아래로 줄바꿈되던 메뉴 이름을 `d-flex` 한 줄 배치로 숫자 오른쪽에 붙임.

- **실시간 인기 순위 옆 대표 후기 + 후기 탭 상호전환 버그 수정**
  실시간 인기 순위의 각 메뉴 옆에 그 메뉴의 대표 후기(좋아요 top3 중 랜덤 1개, 내용 없으면 별점)를 표시. `reviews/services.sample_reviews_for_menus(menu_ids, pool=3)` 추가, `dashboard` 뷰가 순위 메뉴에 `sample_review` 부착, 템플릿에 💬 후기 노출(후기 없으면 생략). 후기 탭에서 음식↔음식점 전환이 안 되던 버그 수정 — 탭 링크에 `type` 파라미터가 중복으로 붙어(`?type=place&...&type=food`) Django가 마지막 값을 읽던 문제(이전 페이지네이션 일괄치환이 탭 링크까지 건드린 부작용)를 제거.

- **식사 기록 음식이름 표기 통일(자동완성) + 기록 날짜 시간대 정리**
  "오늘 먹은 음식 기록하기" 음식이름 입력칸에 `<datalist>` 자동완성 추가 — 기존 메뉴 이름 + 지금까지 기록된 `food_name`을 후보로 제안해 '돈까스/돈가스'처럼 사용자마다 다르게 적는 걸 줄임(`records/services.food_name_suggestions()`, 대시보드/히스토리 모달 양쪽). 날짜 지정 기록 시 `created_at`을 `timezone.make_aware(...12시)`로 저장해 naive datetime 경고 제거.

- **캘린더 날짜 상세 모달: 한줄평 표시 + 히스토리 전체보기 버튼**
  달력 날짜 클릭 시 뜨는 모달에서 음식이름·별점 아래에 한줄평(comment)을 인용구로 표시(`meal_calendar`의 `records_by_day`에 `comment` 추가, 모달 JS에 HTML escape 헬퍼 추가해 XSS 방지). 모달 하단에 "📋 식사 히스토리 전체보기" 버튼(→ `records:history`).

- **'식사 히스토리' 명칭 통일 + 후기 목록 작성 버튼**
  마이페이지의 "🕒 최근 먹은 메뉴 & 추천 내역" → "🕒 식사 히스토리"로 통일. 후기 목록 상단 헤더 우측에 "✏️ 후기 작성하기" 버튼(→ `reviews:review_create_general`, 로그인 시). (검색 폼 안에 중첩돼 깨져 있던 버튼 마크업 정리.)

- **추천 카드 새로고침: 카드 우측 하단 텍스트 버튼 + AJAX(스크롤 튐 방지)**
  점심/저녁/취향 카드의 재추첨 버튼을 카드 헤더의 🔄 아이콘에서 **카드 우측 하단 "새로고침" 텍스트 버튼**으로 이동(가독성). 클릭 시 링크 이동 대신 `menus:reroll`(JSON) 엔드포인트로 해당 카드만 교체 → 페이지가 상단으로 튀지 않음. JS 꺼져 있으면 `?reroll=<slot>` href 폴백(기존 PRG). `_resolve_recs()`로 세션 핀 로직을 dashboard/reroll이 공유.

- **'지금 인기' 카드 제거 → 취향 카드 이동 → 음식 후기 카드(일간/주간) 신설**
  하단 3카드를 [오늘의 BEST][당신의 취향(재추첨)][음식 후기]로 재배치. '지금 인기 있는 메뉴' 카드를 없애고 그 자리에 음식 후기 카드 신설 — 우상단 일간/주간 탭(클라이언트 토글)으로 최근 음식 후기(일간=오늘, 주간=최근 7일)를 메뉴명·별점·내용 요약으로 노출(`reviews/services.recent_food_reviews()`).

- **음식점 후기 제목 필드(조건부)**
  후기 작성 시 후기 종류가 "음식점 후기"일 때만 제목 입력칸 노출(JS 토글) + 저장(음식 후기면 제목 버림, 음식점 후기면 제목 필수 검증). `Review.title` 사용, `ReviewForm`에 `title` 추가 및 `clean()` 검증, `review_form.html` 토글/`_review_item.html` 제목 표시. 더불어 게시판 글쓰기 폼(`ReviewCreateGeneralView`) 정리 — 렌더 안 되던 메뉴 선택 필드 노출, 빈 '말머리' 블록 제거, 동적 `menu` 필드가 저장되도록 `form_valid`에서 명시 세팅.

- **음식이름 표기 통일 재설계: 검색형 콤보박스 + 카탈로그 연결(Menu FK)**
  기존 `<datalist>` 수동 제안(강제성 없음)을 걷어내고, 식사 기록 음식이름 입력을 **검색형 콤보박스**로 교체. 입력하면 후보(카탈로그 메뉴 전체 + 내 과거 기록·빈도)가 필터돼 목록으로 뜨고, 골라야 확정된다(없으면 새 이름으로 기록). 제출 시 자유입력이면 서버 근사매칭(`difflib`)으로 "혹시 ‘돈카츠’?"를 되물어(모달 내 인라인, 페이지 리로드 없음) 표기를 맞추게 유도. `records/templates/records/_food_combobox.html`(신규, input+hidden menu_id+드롭다운+JS) 하나로 대시보드·히스토리 두 모달 공용, `theme.css`에 드롭다운 스타일.
  - `MealRecord.menu` FK(nullable, `SET_NULL`) 추가 — 카탈로그 음식은 실제 `Menu`로 연결해 표기 100% 고정, 카탈로그 밖 음식(집밥·라면 등)은 FK 없이 `food_name` 스냅샷만 저장. 마이그레이션 `records.0002`에서 기존 기록 중 `food_name`이 `Menu.name`과 정확일치하는 것(예: `돈카츠`)을 백필 연결(표기 다른 `돈가스`·카탈로그 밖 `샐러드`는 미연결로 남겨 이후 콤보박스로 정규화).
  - `records/services.py`에 `food_name_candidates(user)`(후보 풀)·`similar_food_name()`(difflib 근사) 추가. `create_record`가 `menu_id` 수용 + 서버측 최종 정규화(입력이 `Menu.name` 정확일치면 자동 링크). `records:check_food` JSON 뷰 신설.
  - **추천 정확도 복구**: `recommender.py`의 "최근 먹은 것 제외"·취향 매칭을 `menu_id` 우선(레거시/카탈로그 밖은 기존 이름 근사 폴백)으로 바꿔, `돈가스≠돈카츠`로 조용히 깨지던 이름매칭 문제를 해소.

- **메뉴 카탈로그 대폭 확장(≈200) + 디저트·음료 제거 + 식사기록 초기화**
  팀원이 준 확장 메뉴 시드(한/중/일/양 + 치킨/아시안/멕시칸/인도/패스트푸드)를 `seed_data`에 반영. 51개 → **199개**로 확장(신규 157, 기존 메뉴 설명 백필 36). `get_or_create(name=...)` 기반이라 기존 메뉴의 좋아요·리뷰는 그대로 보존(id 유지, UPDATE/DELETE 없음). `CUISINES`/`COURSES`는 실제 쓰인 값만 산출해 빈 필터를 없애고, 리스트 내부 중복 이름(마라샹궈 등)은 제거.
  - **디저트·음료 전면 제거**: 시드에서 제외(메인/사이드만) + 기존 디저트 6·음료 3 메뉴 삭제(후기 2건〔붕어빵〕·조회/좋아요 로그 CASCADE 동반 삭제) + `디저트`/`음료` Course 행 삭제. 새 환경(AWS)에서도 안 생김. 관련 주석(`Course` docstring, `menu_list`/`catalog` 코스 설명) 정리.
  - **식사기록(MealRecord) 전체 삭제**(58건, 초기화 — 나중에 다시 기록). 좋아요/리뷰는 유지되며, 기존 참여 메뉴(김치찌개·돈카츠·라멘 등)의 좋아요·리뷰 수는 삭제 전과 동일함을 확인.

- **대시보드 추천에서 점심/저녁 구분 제거**
  상단 "☀️ 점심 추천 / 🌙 저녁 추천" 두 카드를 "🍽️ 오늘의 추천 / 🎲 또 다른 추천"으로 변경(레이아웃·새로고침 유지). `recommender.recommend_dashboard`에서 두 슬롯의 `meal_time` 필터를 제거해 이제 둘 다 **전체 '메인' 메뉴에서 무작위**(서로 중복 없음)로 뽑는다. `menus/views.py`의 `SLOT_META` 헤더와 reroll(AJAX) 카드 헤더도 새 라벨로. `Menu.meal_time` 필드 자체는 그대로 두되(향후 사용 여지) 추천에서 더는 참조하지 않음.
