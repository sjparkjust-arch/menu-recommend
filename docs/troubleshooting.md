# 트러블슈팅 기록

온프레미스(1단계) 구축 중 실제로 겪은 문제들. 각 항목은 **증상 / 시도한 것 / 원인 / 해결 / 배운 것** 구조로 기록한다. 같은 삽질을 두 번 하지 않기 위한 문서.

---

## 1. Nginx가 안 뜸 — `nginx -t`는 통과하는데 `systemctl start`가 실패

**증상**
- 사이트 설정을 다 끝내고 `sudo systemctl reload nginx` 를 하려는데 반영이 안 됨. `sudo nginx -t` 는 `syntax is ok / test is successful` (문법은 정상).
- `systemctl status nginx` 를 보니 **애초에 떠 있지도 않았다** — `Active: inactive (dead)`, reload가 "not active"로 실패.
- 실제 로그(`sudo journalctl -u nginx` / `/var/log/nginx/error.log`):
  ```
  nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)
  nginx: [emerg] bind() to [::]:80 failed (98: Address already in use)
  nginx: [emerg] still could not bind()
  systemd: nginx.service: Control process exited, code=exited, status=1/FAILURE
  ```

**시도한 것 (원인 추적 과정)**
1. `nginx -t`는 통과하는데 reload가 안 먹는다 → 문법이 아니라 **프로세스가 안 떠 있는 것**을 의심.
   `systemctl status nginx` → `inactive (dead)` 확인.
2. 기동 로그 확인 → `[emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)`.
   **80 포트를 누가 이미 쓰고 있다.**
3. **`/var/log/nginx/error.log`를 과거로 더 올려봤더니 `11:42:14`에도 똑같은 emerg 에러가 있었다.**
   그 시각은 `apt install nginx` 를 한 시점 — 즉 **패키지 설치 직후 자동 start부터 이미 bind에 실패**하고 있었고,
   nginx를 실제로 쓸 일이 없던 설정 작업 내내 죽은 채로 방치돼 있었다. 설정을 끝내고 reload를 시도할 때가 되어서야 "not active"로 표면화된 것.
4. 누가 점유 중인지 확인:
   ```bash
   sudo ss -ltnp | grep :80        # LISTEN 중인 프로세스 + PID
   ```
   → `apache2` 가 80 포트를 잡고 있었다.

**원인**
- 이미 설치돼 있던 **Apache2가 80 포트를 선점**하고 있었다.
- nginx는 `apt install` 직후 자동 start부터 계속 bind 실패로 못 떴지만, **아무도 그 시점엔 nginx에 접속하지 않아서** 조용히 죽어 있었다. (설치 성공 ≠ 기동 성공)
- `nginx -t`는 **설정 문법만** 검사하지 포트 점유 여부는 보지 않는다. 그래서 문법은 OK인데 실제 bind에서 실패.

**해결**
```bash
sudo systemctl stop apache2
sudo systemctl disable apache2      # 재부팅 후 다시 뜨지 않게
sudo systemctl start nginx
sudo ss -ltnp | grep :80            # 이제 nginx가 잡고 있는지 확인
```

**배운 것**
- `nginx -t` 통과 = "문법 OK"일 뿐, "뜬다"가 아니다. **기동 실패는 항상 `journalctl -u nginx`부터.**
- 포트 충돌이 의심되면 `ss -ltnp`(또는 `lsof -i :80`)로 점유 프로세스를 먼저 확인.
- 한 서버에 웹서버가 둘(apache2 + nginx) 깔려 있으면 80을 두고 싸운다. 안 쓰는 쪽은 `disable`.
- **데몬은 "방금 실패"가 아니라 "설치 때부터 조용히 실패"하고 있을 수 있다.** 로그 타임스탬프를 **과거로 훑어** 언제부터 깨졌는지 확인하면 진짜 시작점(여기선 `apt install` 시점)이 보인다.
- 새 서비스는 설치 직후 `systemctl status <svc>` 로 **실제 떴는지 즉시 확인**하는 습관. deb 패키지는 설치하며 자동 start를 시도하지만, 그 성공 여부는 따로 봐야 안다.

---

## 2. `TemplateDoesNotExist` — 파일은 분명히 있는데 Django가 못 찾음

**증상**
- 브라우저에서 `http://192.168.32.74:8000/` 접속 시 `TemplateDoesNotExist: menus/dashboard.html` (500).
- 그런데 파일은 `menus/templates/menus/dashboard.html` 에 **실제로 존재**하고, `TEMPLATES['DIRS']`, `APP_DIRS=True` 설정도 정상.
- 심지어 별도로 돌린 검증에서는 200이 나왔었다.

**시도한 것 (원인 추적 과정)**
1. 파일이 진짜 있는지부터 확인:
   ```bash
   find . -name dashboard.html -not -path '*/venv/*'   # → 존재
   grep -n DIRS config/settings.py                      # → BASE_DIR/'templates' 정상
   ```
2. 설정과 파일이 다 맞는데 왜? → **지금 프로세스가 실제로 템플릿을 찾는지** 직접 확인:
   ```bash
   python manage.py shell -c "from django.template.loader import get_template; print(get_template('menus/dashboard.html').origin.name)"
   ```
   → **새 프로세스에서는 정상 로드됨.** 즉 코드/설정이 아니라 "실행 중인 그 프로세스"의 문제.
3. Django가 앱 템플릿 디렉토리 목록을 어떻게 구하는지 추적:
   ```bash
   python -c "import django.template.utils, inspect; print(inspect.getsource(django.template.utils.get_app_template_dirs))"
   ```
   → 함수에 `@functools.lru_cache` 가 붙어 있고, **프로세스 시작 시점에 `.is_dir()`로 존재하는** 앱 템플릿 디렉토리만 담아 영구 캐시한다.
4. 프로세스 시작 시각 vs 템플릿 생성 시각 대조:
   ```bash
   ps -eo pid,lstart,args | grep runserver     # worker 시작: 12:51:51
   ls -l templates/base.html                    # 템플릿 생성: 12:52
   ```
   → **worker가 뜬 뒤에 `menus/templates/` 디렉토리를 만들었다.** 그래서 그 프로세스의 캐시에는 이 디렉토리가 없다.

**원인**
- `get_app_template_dirs()`가 **`lru_cache`** 라서, 프로세스가 시작될 때 없던 앱 템플릿 디렉토리(`menus/templates/`)는 이후 만들어도 그 프로세스에서는 **영원히 안 보인다.**
- runserver 오토리로드는 `.py` 변경엔 반응하지만 **새 템플릿 디렉토리 생성엔 반응하지 않아서** worker가 재시작되지 않았다.
- `base.html`은 `DIRS` 기반 filesystem 로더(캐시 방식이 다름)라 영향이 없었고, app-dir 템플릿(`dashboard.html`, `login.html`)만 깨졌다.

**해결**
```bash
# 프로세스를 새로 띄우면 lru_cache가 비워지고 디렉토리를 다시 스캔한다
touch config/settings.py           # (dev) 오토리로드 트리거
# 또는
sudo systemctl restart gunicorn    # (prod) 프로세스 재시작
```

**배운 것**
- **새 앱/템플릿 디렉토리를 추가하면 서버 프로세스를 재시작**한다. 파일만 놔서는 살아있는 프로세스가 못 본다.
- 검증은 `manage.py shell` 테스트 클라이언트(매번 새 프로세스)가 아니라 **실행 중인 그 프로세스에 직접 요청**(curl)해서 해야 한다. 새 프로세스에서 200이 나온다고 배포된 서버가 200인 건 아니다.
- "파일 있는데 못 찾음" 류는 경로/설정을 세 번 보기 전에 **"이 프로세스가 언제 떴나"**를 의심하라.

---

## 3. Redis 기동 실패 — `requirepass` 한 줄에 인자가 2개

**증상**
- `redis.conf`에 비밀번호를 설정한 뒤 `sudo systemctl start redis-server` 가 실패(바로 죽음).
- 로그(`sudo journalctl -u redis-server` / `/var/log/redis/redis-server.log`)에 남은 실제 메시지:
  ```
  *** FATAL CONFIG FILE ERROR (Redis 7.0.15) ***
  Reading the configuration file, at line 1036
  >>> 'requirepass foobared 1234'
  wrong number of arguments
  ```
- 앱에서 Redis 접속도 당연히 안 됨.

**시도한 것 (원인 추적 과정)**
1. 기동 실패니까 로그부터:
   ```bash
   sudo journalctl -u redis-server -n 30 --no-pager
   # 또는
   sudo tail -n 30 /var/log/redis/redis-server.log
   ```
   → `FATAL CONFIG FILE ERROR ... at line 1036 >>> 'requirepass foobared 1234' wrong number of arguments`.
   에러가 **문제 줄 번호(1036)와 그 줄 내용을 그대로 찍어줘서** 원인이 바로 드러났다.
2. `redis.conf` 1036번째 줄 확인:
   ```conf
   requirepass foobared 1234
   ```

**원인**
- `redis.conf`의 샘플 줄은 원래 `# requirepass foobared` (주석 + 예시 비밀번호 `foobared`).
- 주석만 풀고 **`foobared`를 지우지 않은 채 뒤에 실제 비밀번호(`1234`)를 덧붙여서**, `requirepass`에 인자가 **2개**(`foobared`, `1234`)가 됐다. `requirepass`는 인자 1개만 받는다 → 파싱 실패 → 기동 실패.

**해결**
```conf
# 잘못 (line 1036)
requirepass foobared 1234
# 올바름 (예시 값 foobared 제거, 실제 비밀번호 하나만)
requirepass 1234
```
```bash
sudo systemctl restart redis-server
redis-cli -a '1234' ping        # PONG 확인
```
- 이후 비밀번호는 `1234` → `menu2026pw` 로 강화했고(포트폴리오 공개를 고려한 조치), 앱 쪽 `.env`의 `REDIS_URL`도 같은 값으로 맞췄다:
  `redis://:menu2026pw@192.168.32.73:6379/0`
- `redis.conf`의 `requirepass` 와 `.env`의 `REDIS_URL` 비밀번호는 **항상 같이 바꿔야** 접속이 유지된다.

**배운 것**
- 설정 파일의 **주석 예시 값(`foobared`)을 지우지 않고 덧붙이는 실수**를 조심. 특히 인자 1개짜리 지시어는 공백이 곧 인자 구분.
- 데몬 기동 실패는 예외 없이 **로그(journalctl/서비스 로그)부터.** "왜 안 되지"를 추측하지 말고 파서가 뱉은 줄을 읽는다.

---

## 4. CLAUDE.md의 IP와 실제 VM IP 불일치

**증상**
- 프로젝트 규칙(CLAUDE.md)에는 `Server2 (192.168.121.129): MariaDB + Redis`로 적혀 있는데,
  실제로 지시받은/동작하는 DB·Redis 호스트는 `192.168.32.73` 이었다.

**시도한 것 (원인 추적 과정)**
1. `.env`에 DB/Redis 호스트를 넣던 중 CLAUDE.md의 인프라 표와 값이 다른 것을 발견.
2. 어느 쪽이 진짜인지 확인 겸 마이그레이션 히스토리 체크를 돌렸더니:
   ```
   (1045, "Access denied for user 'menuuser'@'192.168.32.74' ...")
   ```
   → 앱이 붙는 주체는 Server1(`192.168.32.74`)이 맞고, 접속 대상 IP는 `192.168.32.73`쪽으로 잡혀 있었다(거부는 비밀번호 placeholder 때문). 즉 실제 구성은 `.32.73`.
3. 사용자에게 확인 → `192.168.32.73`이 맞고, Server1은 `192.168.32.74`.

**원인**
- 문서(CLAUDE.md)가 초기 계획값으로 적혀 있었고, **실제 VM에 할당된 IP와 동기화되지 않았다.** 문서와 현실의 드리프트.

**해결**
- CLAUDE.md의 인프라 표를 실제 값으로 수정:
  ```
  - Server1 (192.168.32.74): Nginx + Gunicorn + Django
  - Server2 (192.168.32.73): MariaDB + Redis
  ```
- 접속 정보의 **단일 출처는 `.env`**(환경변수, CLAUDE.md 절대원칙 3). CLAUDE.md는 사람이 읽는 참고용이므로 실제와 맞게 유지.

**배운 것**
- 인프라 IP 같은 값은 **어디가 진실의 출처(source of truth)인지** 하나로 정한다. 우리는 `.env`.
- 문서와 실제가 다르면 **추측하지 말고 실측**(에러 로그의 호스트, `ip a`, 실제 접속)으로 확인한 뒤, 문서를 현실에 맞춘다.
- 값이 두 군데(문서 + 설정)에 있으면 반드시 언젠가 어긋난다. 발견 즉시 맞춰 둔다.

---

## 5. HTTPS 전환 후 로그인이 깨짐 — CSRF 403 (`Origin checking failed`)

**증상**
- HTTP일 땐 잘 되던 로그인이, HTTPS(443)로 바꾸고 `DEBUG=False` 상태에서 **로그인 폼 제출 시 403 Forbidden**.
- 화면/로그 메시지: `Forbidden (403) CSRF verification failed. ... Origin checking failed - https://192.168.32.74 does not match any trusted origins.`
- GET 페이지(대시보드 등)는 멀쩡한데 **POST(로그인/폼)만** 깨진다.

**시도한 것 (원인 추적 과정)**
1. GET은 되는데 POST만 403 → 인증/프록시가 아니라 **CSRF** 문제로 좁힘.
2. 에러 문구가 `Origin checking failed ... does not match any trusted origins` 를 그대로 알려줌 → Django가 https 요청의 `Origin` 헤더를 신뢰 목록과 대조하는데 목록이 비어 있다.
3. Django 4+ 동작 확인: **https 요청의 POST는 `Origin`/`Referer` 를 `CSRF_TRUSTED_ORIGINS` 와 대조**한다. http일 땐 이 검사가 느슨해 그냥 통과했던 것.

**원인**
- Django 4.0부터 https 요청의 CSRF 검사는 `CSRF_TRUSTED_ORIGINS`(scheme 포함)에 오리진이 있어야 통과한다.
- 이 값을 비워둔 채 HTTPS로 올려서, `https://192.168.32.74` 오리진이 신뢰 목록에 없어 전부 거부.

**해결**
```bash
# .env (scheme 포함, 콤마 구분)
CSRF_TRUSTED_ORIGINS=https://192.168.32.74
```
```python
# settings.py
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])
```
```bash
sudo systemctl restart gunicorn   # .env 변경 반영
```
- 함께 필요: Nginx가 `proxy_set_header X-Forwarded-Proto $scheme;` 를 넘기고, settings에
  `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` 가 있어야 Django가 요청을 https로 인식한다.

**배운 것**
- **HTTPS로 바꾸면 `CSRF_TRUSTED_ORIGINS` 를 반드시 채운다**(scheme 포함). 빠뜨리면 모든 폼 POST가 403.
- CSRF 에러 문구는 원인을 친절히 적어준다 — "trusted origins" 라는 단어가 보이면 이 설정을 의심.
- `http://`(dev)에서 잘 되던 게 `https://`(prod)에서 깨지는 전형적 함정. dev/prod 스킴 차이를 항상 염두.

---

## 6. 자체 서명 인증서 — 브라우저가 거부 (`ERR_CERT_COMMON_NAME_INVALID`)

**증상**
- 내부망이라 자체 서명 인증서를 만들어 붙였는데, `https://192.168.32.74` 접속 시 브라우저가 연결 자체를 거부.
- 단순 "안전하지 않음" 경고(신뢰 예외로 진행 가능)가 아니라 `NET::ERR_CERT_COMMON_NAME_INVALID` 로 **진행 옵션조차 애매**하게 막힘.

**시도한 것 (원인 추적 과정)**
1. 처음엔 `-subj "/CN=192.168.32.74"` 로만 인증서를 만들었다(CN에 IP).
2. 그래도 `COMMON_NAME_INVALID` → 요즘 브라우저(Chrome 등)는 **CN을 호스트 검증에 안 쓰고 SAN(subjectAltName)만 본다**는 것을 확인.
3. 인증서에 SAN이 들어갔는지 검사:
   ```bash
   openssl x509 -noout -text -in /etc/ssl/certs/menu-recommend.crt | grep -A1 "Subject Alternative Name"
   ```
   → SAN 항목이 아예 없었다.

**원인**
- 최신 브라우저는 **CN이 아니라 SAN으로 호스트/IP를 매칭**한다. CN에만 IP를 넣고 SAN을 빠뜨리면 매칭 실패 → `COMMON_NAME_INVALID`.

**해결**
```bash
# 재발급 시 SAN에 IP를 명시 (openssl 1.1.1+ 는 -addext 로 한 줄에 가능)
sudo openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout /etc/ssl/private/menu-recommend.key \
  -out    /etc/ssl/certs/menu-recommend.crt \
  -subj   "/C=KR/ST=Seoul/L=Seoul/O=MenuRecommend/CN=192.168.32.74" \
  -addext "subjectAltName=IP:192.168.32.74"
```
- 도메인이면 `subjectAltName=DNS:example.internal`, IP면 `IP:...`. 여러 개면 콤마로.
- 발급 후 SAN 재확인: 위 `openssl x509 ... grep "Subject Alternative Name"`.
- 그래도 남는 `ERR_CERT_AUTHORITY_INVALID` 경고는 **자체 서명이라 정상** — 신뢰 예외로 진행하거나
  각 클라이언트에 `.crt` 를 신뢰 루트로 설치하면 사라진다. (CN_INVALID 와는 다른 문제)

**배운 것**
- 자체 서명 인증서는 **SAN이 필수**. CN만으로는 최신 브라우저를 통과 못 한다. IP 접속이면 `IP:`, 도메인이면 `DNS:`.
- 인증서 문제는 두 종류를 구분: **CN/SAN 불일치(ERR_CERT_COMMON_NAME_INVALID → 재발급 필요)** vs **신뢰 체인 없음(ERR_CERT_AUTHORITY_INVALID → 자체 서명이라 당연, 예외 처리)**.
- **IP가 바뀌면 인증서도 다시 만들어야** 한다(SAN이 특정 IP에 묶여 있으므로).

---

## 7. HTTPS인데 무한 리다이렉트 (`ERR_TOO_MANY_REDIRECTS`) — 프록시 뒤 스킴 인식 실패

**증상**
- 80→443 리다이렉트를 걸었더니, https로 접속해도 **계속 리다이렉트가 돌며** `ERR_TOO_MANY_REDIRECTS`.

**시도한 것 (원인 추적 과정)**
1. Nginx는 443을 정상 수신하는데 왜 또 리다이렉트? → **Django가 요청을 여전히 http로 인식**하고 다시 https로 보내는 루프를 의심.
2. Nginx가 실제 스킴을 앱에 알려주는지 확인 → `proxy_set_header X-Forwarded-Proto $scheme;` 존재 여부.
3. Django가 그 헤더를 신뢰하도록 `SECURE_PROXY_SSL_HEADER` 가 설정됐는지 확인.

**원인**
- TLS는 **Nginx에서 종료**되고 Django에는 소켓으로 평문이 전달된다. 그래서 Django의 `request.is_secure()` 는 기본적으로 False.
- `SECURE_PROXY_SSL_HEADER` 없이 앱단에서 https 강제 리다이렉트(예: `SECURE_SSL_REDIRECT`)를 켜면, 앱이 매번 "http네? → https로" 리다이렉트를 반복 → 루프.

**해결**
```python
# settings.py — Nginx가 넘기는 X-Forwarded-Proto 로 원 스킴을 판별
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```
```nginx
# nginx.conf — 반드시 함께
proxy_set_header X-Forwarded-Proto $scheme;
```
- 우리 구성은 리다이렉트를 **Nginx(80 server 블록)에서** 처리하므로 앱단 `SECURE_SSL_REDIRECT` 는 켜지 않는다(중복이면 루프 위험).

**배운 것**
- 리버스 프록시 뒤에서 TLS를 종료하면 **앱은 스킴을 모른다.** `X-Forwarded-Proto` + `SECURE_PROXY_SSL_HEADER` 짝이 반드시 필요.
- https 리다이렉트는 **한 곳에서만**(우리는 Nginx). 프록시와 앱 양쪽에서 걸면 무한 루프가 나기 쉽다.

---

> 아래부터는 CLAUDE.md의 트러블슈팅 기록 규칙 형식 `[날짜 | 제목]` 을 따른다.

## [2026-07-14 | 메뉴 목록 페이지네이션 EmptyPage 500]

**증상**
- `/menus/` 접속 시 500. 그런데 `/menus/?q=김치`(결과 2건)는 200으로 멀쩡.
- `/menus/?cuisine=1`(한식 16건)처럼 결과가 여러 페이지인 경우도 500.

**시도한 것 (원인 추적 과정)**
1. 200 나는 요청(`?q=김치`, 2건)과 500 나는 요청(전체 51건, `?cuisine=1` 16건)의 차이를 봄
   → **결과가 한 페이지면 200, 여러 페이지면 500.** 즉 페이지네이션 블록이 그려질 때만 터진다.
2. `?q=김치`는 결과가 1페이지라 `{% if page_obj.has_other_pages %}` 가 False → 페이지네이션 블록 자체가 렌더되지 않아 우연히 통과했던 것.
3. 템플릿 페이지네이션 블록을 보니 1페이지에서도 `{{ page_obj.previous_page_number }}` 를 호출.
   이 값은 속성이 아니라 **메서드**라 템플릿이 호출하는데, 1페이지엔 이전 페이지가 없어 예외를 던진다.
4. 실제 예외 확인:
   ```python
   Paginator(list(range(51)), 12).get_page(1).previous_page_number()
   # django.core.paginator.EmptyPage: 페이지 번호가 1보다 작습니다.
   ```
   `EmptyPage` 는 템플릿에서 silence 되지 않아 그대로 500.

**원인**
- 페이지네이션 "이전" 링크를 `has_previous` 가드 없이 `page_obj.previous_page_number` 로 렌더 → 1페이지에서 `EmptyPage: 페이지 번호가 1보다 작습니다.` 발생.
- 처음에 못 잡은 이유: 하필 첫 확인을 결과 2건(단일 페이지) 요청으로 해서 블록이 안 그려졌다. **테스트 데이터가 우연히 버그를 가렸다.**

**해결**
- `previous_page_number`/`next_page_number` 호출을 각각 `{% if page_obj.has_previous %}` / `{% if page_obj.has_next %}` 로 감싸고, 없을 땐 비활성(`<span>`) 렌더:
  ```django
  {% if page_obj.has_previous %}
    <a href="?page={{ page_obj.previous_page_number }}...">이전</a>
  {% else %}
    <li class="page-item disabled"><span class="page-link">이전</span></li>
  {% endif %}
  ```
- 재검증: 전체/필터/검색/2페이지 모두 200. (이후 reviews 목록에도 같은 가드를 처음부터 적용)

**배운 것**
- 템플릿의 `previous_page_number`/`next_page_number` 는 **메서드라 호출되고, 경계에서 `EmptyPage` 예외**를 던진다. 반드시 `has_previous`/`has_next` 가드로 감싼다. (CLAUDE.md 코드 규칙으로 승격)
- **경계 조건은 경계 데이터로 확인한다.** "여러 페이지"가 나오는 입력으로 테스트해야 페이지네이션 버그가 드러난다. 단건/단일 페이지 결과로는 못 잡는다.

## [2026-07-14 | 전날 열어둔 탭을 새로고침 없이 접속하니 500]

**증상**
- 전날 켜둔 웹사이트 탭을 새로고침하지 않은 상태로 다시 조작하니 500. 새로 접속/새로고침하면 정상.

**시도한 것 (원인 추적 과정)**
- 처음엔 "재부팅 후 서버 문제"로 의심했으나, 확인 결과 서버가 아니라 **브라우저의 오래된 탭 상태**가 원인이었다.

**원인**
- **미확보.** 어제 상황이라 해당 500 응답 원문/로그를 확보하지 못했다. 추정 원인은 규칙(추측 재구성 금지)에 따라 적지 않는다.

**해결**
- 페이지 **새로고침(재접속)** 으로 해소.

**배운 것**
- 오래 열어둔 탭은 서버 재시작·토큰 만료 등으로 상태가 어긋날 수 있다. "서버 500"으로 단정하기 전에 **새로고침부터** 해본다.
- 원문을 확보 못 하면 원인 칸은 비워두고 **증상/해소만** 기록한다(이 항목이 그 사례). 정확한 재현·원문이 나오면 그때 원인을 채운다.

---

## [2026-07-15 | 팀원과 수동 병합 후 500 — `ModuleNotFoundError: accounts.urls`]

**증상**
- 팀원(accounts, records)과 내(menus, reviews) 코드를 수동으로 병합한 뒤 `https://192.168.32.74/` 접속 시 500.

**시도한 것 (원인 추적 과정)**
1. `journalctl -u gunicorn`으로 실제 에러 원문 확인:
   ```
   ModuleNotFoundError: No module named 'accounts.urls'
   File "config/urls.py", line 15, in <module>
       path('accounts/', include('accounts.urls')),
   ```
2. 실제 파일명은 `accounts/acurls.py`, `records/reurls.py` (팀원이 관례와 다르게 지음). `config/urls.py`가 옛 이름(`accounts.urls`, `records.urls`)을 그대로 `include`하고 있었다.
3. 작업 트리엔 이미 `accounts.acurls`로 고친 상태였는데도 재현된 이유: **그 수정이 커밋되지 않고 워킹 트리에만 있었다.** gunicorn은 항상 디스크의 마지막 커밋 상태가 아니라 그 시점 워킹 트리 파일을 읽고 부팅하는데, 그 사이 다른 원인으로 워커가 재시작되며 옛 커밋 시점 파일을 다시 읽은 정황.

**원인**
- `config/urls.py`의 `include()` 경로가 실제 파일명(`acurls.py`, `reurls.py`)과 다른 이름(`urls.py`)을 참조. 게다가 그 수정본이 커밋되지 않아 배포 상태와 워킹 트리가 어긋나 있었다.

**해결**
- `config/urls.py`를 `accounts.acurls`, `records.reurls`로 수정 후 커밋.

**배운 것**
- **앱 URL 모듈명이 관례(`urls.py`)와 다르면 `config/urls.py`의 `include()` 경로부터 의심한다.**
- **"워킹 트리에서 고쳤다" ≠ "배포됐다".** gunicorn 재시작 전/후, 그리고 커밋 여부를 항상 같이 확인한다. `git status`로 미커밋 수정이 실제 운영 서버가 읽는 파일과 다른지 늘 체크.

---

## [2026-07-15 | 로그인 성공 후 500 — `NoReverseMatch: Reverse for 'index' not found`]

**증상**
- 로그인 페이지(GET)는 정상 렌더링되는데, 아이디/비밀번호를 넣고 로그인(POST)하면 500.

**시도한 것 (원인 추적 과정)**
1. DEBUG=False라 gunicorn 로그에 트레이스백이 안 남음(Django 기본 로깅은 `django.request`를 `mail_admins`로만 보냄, 콘솔에 안 찍힘).
2. `python manage.py shell`에서 `django.test.Client(raise_request_exception=True)`로 실제 요청을 재현해 트레이스백을 직접 확보:
   ```
   File "accounts/views.py", line 67, in login_view
       response = redirect(reverse('accounts:index'))
   django.urls.exceptions.NoReverseMatch: Reverse for 'index' not found. 'index' is not a valid view function or pattern name.
   ```
3. `accounts/acurls.py`를 보니 `path('', views.index, name='index')` 줄이 주석 처리돼 `index` 라우트 자체가 없어져 있었음. `views.index` 함수는 그대로 존재.

**원인**
- `accounts/acurls.py`에서 `index` 라우트가 (원인 불명, 병합 과정 추정) 주석 처리되어 사라짐. `login_view`는 로그인 성공 시 여전히 그 이름을 `reverse()`로 찾음.

**해결**
- `path('', views.index, name='index')` 주석 해제로 라우트 복구.
- DEBUG=False 환경에서 500 원인을 못 볼 때는 `Client(raise_request_exception=True)`로 로컬 재현 → 진짜 트레이스백 확보 후 기록한다(추측 금지 원칙 준수).

**배운 것**
- **GET이 되는 페이지도 POST/성공 경로까지 실제로 눌러봐야 한다.** 폼이 뜬다고 그 폼의 성공 경로가 동작하는 건 아니다.
- DEBUG=False 프로덕션에서 500의 실제 원인을 보려면 `manage.py shell` + 테스트 `Client(raise_request_exception=True)`로 같은 요청을 재현하는 게 유일한 방법 중 하나.

---

## [2026-07-15 | 대시보드만 500 — 팀원의 `records` 스키마와 내 코드의 필드 가정이 어긋남]

**증상**
- `/`(대시보드)만 500, `/menus/`·`/accounts/`·`/reviews/`는 정상.

**시도한 것 (원인 추적 과정)**
1. `manage.py shell`에서 직접 쿼리 실행해 원문 확보:
   ```
   django.core.exceptions.FieldError: Cannot resolve keyword 'date' into field.
   Choices are: comment, created_at, food_name, id, meal_type, rating, user, user_id
   ```
2. `menus/views.py`의 대시보드가 `request.user.meal_records.select_related('menu').order_by('-date')`를 호출하는데, 실제 `records.MealRecord`엔 `menu` FK도 `date` 필드도 없음(`food_name`, `created_at`, `meal_type`로 팀원이 설계).
3. 필드명만 고쳐서(`-created_at`) 재실행하니 이번엔 DB 레벨 에러:
   ```
   django.db.utils.OperationalError: (1054, "Unknown column 'records_mealrecord.food_name' in 'SELECT'")
   ```
4. `python manage.py dbshell` → `DESCRIBE records_mealrecord;`로 실제 테이블 컬럼 확인 → `date, meal, menu_id` (구 스키마). `django_migrations` 테이블엔 `records.0001_initial` 적용됨으로 기록돼 있었지만, 그 마이그레이션 **파일 내용은 이미 신 스키마로 교체**돼 있었음. Django는 마이그레이션을 파일 내용이 아니라 이름으로만 추적하므로 재실행되지 않고 계속 어긋난 상태였다.
5. `menus/services/recommender.py`의 "최근 7일 먹은 메뉴 제외" 로직도 `meal_records.filter(date__gte=...).values_list('menu_id', ...)`를 썼는데, `records`엔 애초에 `menu` FK가 없어(팀원이 자유 텍스트 `food_name`으로 설계) 이름 변경만으론 해결 불가.

**원인**
- 세 가지가 겹침: (1) 뷰 코드가 옛 필드명(`date`/`menu`)을 가정, (2) 실제 DB 테이블이 옛 스키마로 남아 있는데 마이그레이션 파일은 이름 재사용 없이 새 스키마로 덮어써져 다시 적용되지 않음, (3) 추천 로직이 `records`↔`menus` 간 FK 연결을 전제했으나 팀원 설계엔 그 연결이 없음(자유 텍스트).

**해결**
- 테이블 데이터 0건 확인 후 `python manage.py migrate records zero` → `python manage.py migrate records`로 테이블을 현재 모델 스키마로 재생성.
- `menus/views.py`, `menus/templates/menus/dashboard.html`을 `food_name`/`created_at`/`meal_type`에 맞게 수정.
- `recommender.py`의 "최근 제외" 로직은 `Menu.name == food_name` 이름 매칭으로 근사 대체(정확한 FK가 없으므로).

**배운 것**
- **Django는 마이그레이션을 파일 이름으로만 추적한다.** 이미 적용된 마이그레이션 파일의 내용을 나중에 바꿔치기하면, 실제 DB는 안 바뀌는데 `makemigrations --check`는 "변경 없음"이라고 속인다. 스키마를 바꾸려면 반드시 새 마이그레이션(또는 `migrate zero` 후 재적용)을 거쳐야 한다.
- **다른 사람이 만든 앱과 연동하는 코드는 그 앱의 실제 모델 필드를 먼저 확인하고 짠다.** 이름만 그럴듯하게 맞춰 짜면(`menu_id`, `date`) 나중에 실제 스키마와 어긋난다.
- `manage.py check`/`makemigrations --check`가 통과해도 **실제 DB 컬럼과 일치한다는 보장은 없다** — `dbshell`로 실제 테이블 구조를 직접 봐야 확신할 수 있다.

---

## [2026-07-15 | theme.css를 아무리 collectstatic해도 사이트에 반영이 안 됨]

**증상**
- `static/css/theme.css`를 수정하고 `collectstatic` → gunicorn 재시작까지 했는데도 실제 사이트 색상이 안 바뀜.

**시도한 것 (원인 추적 과정)**
1. `staticfiles/css/theme.css`가 실제로 있는지 확인 → **아예 없었다.** `find staticfiles -maxdepth 2`로 보니 `staticfiles/accounts/`, `staticfiles/records/`, `staticfiles/admin/`만 있고 `staticfiles/css/`가 없음.
2. 실 서버에 직접 확인:
   ```
   curl -sk https://192.168.32.74/static/css/theme.css → 404
   ```
3. `config/settings.py`에서 `STATICFILES_DIRS`를 검색 → **아예 정의돼 있지 않았다.** `STATIC_URL`/`STATIC_ROOT`만 있음.

**원인**
- Django의 `collectstatic`은 (1) 각 앱 자체의 `<app>/static/` 폴더(`AppDirectoriesFinder`, 자동 인식)와 (2) `STATICFILES_DIRS`에 등록된 경로(`FileSystemFinder`)만 수집한다.
- `accounts/static/`, `records/static/`은 앱 폴더라 자동으로 수집됐지만, 프로젝트 루트의 공용 `static/`(theme.css가 있는 곳)은 `STATICFILES_DIRS`에 등록된 적이 없어서 **`collectstatic`이 존재 자체를 몰랐다.** 즉 `collectstatic`을 몇 번을 다시 돌려도 절대 복사될 수 없는 상태였다 — theme.css는 만들어진 시점부터 이번에 고치기 전까지 실제 서버에 한 번도 반영된 적이 없었다.

**해결**
```python
# config/settings.py
STATICFILES_DIRS = [BASE_DIR / 'static']
```
추가 후 `python manage.py collectstatic --noinput` → `staticfiles/css/theme.css` 생성 확인, `curl`로 실제 200 + 새 색상 값까지 확인.

**배운 것**
- **`collectstatic`이 "성공"(에러 없이 끝남)해도 원하는 파일이 실제로 복사됐는지는 보장하지 않는다.** 앱 폴더 밖(`static/` 프로젝트 루트)에 정적 파일을 두려면 `STATICFILES_DIRS`를 반드시 등록해야 하고, 등록 안 해도 `collectstatic`은 조용히 그 파일을 건너뛸 뿐 에러를 내지 않는다.
- CSS/정적 파일이 "안 바뀐다"는 증상이 나오면 브라우저 캐시부터 의심하기 쉽지만, **`staticfiles/`에 파일이 실제로 존재하는지, `curl`로 실제 200이 오는지부터 먼저 확인**한다(이번처럼 애초에 파일 자체가 없는 경우가 있다).

## [2026-07-16 | 달력이 항상 비어 보임 — created_at__month 필터가 0건 반환]

**증상**
- 대시보드 "최근 먹은 음식" 달력에 식사 기록이 하나도 안 뜸. 분명히 이번 달(2026-07)에 기록이 있는데 달력은 비어 있음.

**시도한 것 (원인 추적 과정)**
1. `records.services.meal_calendar()`가 `total: 0`, `records_by_day: {}`를 반환하는 걸 shell에서 확인.
2. 기록 자체는 있나 확인 → `MealRecord.objects.filter(user=u)` 2건 존재, `created_at`는 `2026-07-16 06:53 UTC`(localtime `2026-07-16 15:53 KST`). 이번 달 맞음.
3. 필터를 쪼개서 확인:
   ```
   filter(created_at__year=2026)            → 2건
   filter(created_at__month=7)              → 0건   ← 여기!
   filter(created_at__year=2026, __month=7) → 0건
   filter(created_at__date='2026-07-16')    → 0건
   ```
   `__year`는 되는데 `__month`/`__date`만 0건.

**원인**
- `USE_TZ=True`, `TIME_ZONE='Asia/Seoul'`일 때 Django의 `__month`/`__day`/`__date` 룩업은 컬럼을 `CONVERT_TZ(created_at, 'UTC', 'Asia/Seoul')`로 감싼다. **MariaDB에 시간대(timezone) 테이블이 적재돼 있지 않으면 `CONVERT_TZ`가 NULL을 반환**해서 조건이 아무것도 매칭하지 않는다. 반면 `__year`는 내부적으로 파이썬에서 계산한 연 시작~끝 BETWEEN 범위 비교라 `CONVERT_TZ`를 안 써서 정상 동작한다. (`created_at__gte=since` 같은 범위 비교도 안전.)

**해결**
- `meal_calendar()`에서 `created_at__year`/`__month` 대신 로컬 기준 한 달 구간을 datetime 범위로 필터:
  ```python
  month_start = timezone.make_aware(datetime(year, month, 1))
  month_end   = timezone.make_aware(datetime(next_year, next_month, 1))
  MealRecord.objects.filter(created_at__gte=month_start, created_at__lt=month_end)
  ```
  범위 비교라 `CONVERT_TZ` 없이 동작 → 시간대 테이블 적재 여부와 무관하게 안전.
- (근본 해결책은 MariaDB에 `mysql_tzinfo_to_sql`로 시간대 테이블을 적재하는 것이지만, DB 서버 관리 작업이라 코드 쪽에서 범위 필터로 우회.)

**배운 것**
- `USE_TZ=True` + MySQL/MariaDB에서 **`__month`/`__day`/`__date`/`__week_day` 룩업은 시간대 테이블이 없으면 조용히 0건**을 낸다(에러도 없음). 날짜 부분 추출 대신 **datetime 범위 비교(`__gte`/`__lt`)로 쓰는 게 안전**하다.
- "필터가 0건"일 때 `__year`만 따로 떼서 되는지 보면 시간대 변환 문제인지 금방 갈린다.

---

## [2026-07-20 | 식사 기록 완료·대시보드 500 — `reviews_review.title` 컬럼 없음 (또 마이그레이션↔DB 드리프트)]

**증상**
- 캘린더에서 "오늘 먹은 음식 기록하기" → "기록 완료"를 누르면 500. 기록 자체는 `records`에 저장되는데, 저장 후 대시보드(`/`)로 리다이렉트되는 지점에서 터졌다.
- `/`(대시보드)를 직접 열어도 500.

**시도한 것 (원인 추적 과정)**
1. `manage.py shell` + `Client(raise_request_exception=True)`로 `sjpark1999`로 로그인해 `/` 재현 → 트레이스백 원문 확보:
   ```
   django.db.utils.OperationalError: (1054, "Unknown column 'reviews_review.title' in 'SELECT'")
     File "menus/views.py", line 63, in dashboard
       review_samples = review_services.sample_reviews_for_menus([m.id for m in popular_ranking])
   ```
   → 대시보드가 실시간 인기 순위 옆 대표 후기를 뽑느라 `reviews_review`를 SELECT하는데 `title` 컬럼이 없다.
2. `reviews/models.py`엔 `title = CharField(max_length=100, null=True, blank=True)`, `category = CharField(max_length=50, null=True, blank=True)`가 이미 정의돼 있음(팀원 추가분).
3. `showmigrations reviews` → `[X] 0001_initial` 하나뿐. `makemigrations reviews --dry-run` → **"No changes detected"**. 즉 모델 == 마이그레이션 상태(둘 다 title/category 있음)라 새 마이그레이션이 안 생긴다.
4. 실제 DB 컬럼 확인(`SHOW COLUMNS FROM reviews_review`):
   ```
   id, rating, content, image, created_at, menu_id, user_id, review_type
   ```
   → `title`, `category`가 **DB에만 없음**. `0001_initial.py`(오늘 04:23 재생성됨)는 두 컬럼을 포함하지만, 테이블은 그 이전 버전으로 만들어져 있었고 마이그레이션은 이미 `[X]`라 재적용 안 됨.

**원인**
- 07-15 records 사건과 **동일한 마이그레이션↔DB 드리프트**. `0001_initial` 파일 내용이 나중에 (title/category 추가된 채로) 재생성됐는데, 그 마이그레이션은 이미 적용됨으로 기록돼 있어 실제 테이블엔 컬럼이 추가되지 않았다. Django는 마이그레이션을 이름으로만 추적하므로 `makemigrations`는 "변경 없음"이라고 속인다.

**해결**
- 테이블을 마이그레이션(0001_initial)에 맞춰 두 컬럼만 보정:
  ```sql
  ALTER TABLE reviews_review
    ADD COLUMN title varchar(100) NULL,
    ADD COLUMN category varchar(50) NULL;
  ```
- 재검증: 대시보드/히스토리 200, 식사 기록 완료(POST→대시보드 리다이렉트) 302. (새로 배포하는 환경/AWS는 0001_initial이 처음부터 두 컬럼을 만들므로, 드리프트가 난 이 기존 DB만 보정하면 됨.)

**배운 것**
- "**기록 완료 눌렀더니 500**"이 반드시 그 기록(records) 쪽 버그는 아니다 — POST 성공 후 **리다이렉트 대상 페이지(대시보드)**가 터진 것이었다. 저장은 됐는데 도착지가 500이면 착시가 생긴다. 리다이렉트 체인의 끝까지 재현해봐야 한다.
- 마이그레이션↔DB 드리프트는 이 프로젝트에서 재발한다(records 07-15, reviews 07-20). `showmigrations`가 `[X]`여도, `makemigrations`가 "변경 없음"이어도 **실제 컬럼(`SHOW COLUMNS`)과 대조하기 전엔 스키마 일치를 믿지 않는다.** 특히 병합 후 첫 실행에서.

---

## [2026-07-20 | 후기 목록 500 — partial이 자기 자신을 include (`RecursionError`)]

**증상**
- `/reviews/`(후기 목록) 전부 500. `?type=food`/`?type=place`도 동일.

**시도한 것 (원인 추적 과정)**
1. `Client(raise_request_exception=True)`로 `/reviews/` 재현 → 트레이스백 원문:
   ```
   RecursionError: maximum recursion depth exceeded
   ```
   앱 프레임이 안 보이고 `render_annotated`/`render`가 수백 번 반복됨 → **템플릿 렌더링 무한재귀**로 판단.
2. include/extends 순환 의심 → `grep -rn "extends|include"`:
   ```
   review_list.html:59:  {% include "reviews/_review_item.html" %}
   _review_item.html:1:  {% extends "base.html" %}
   _review_item.html:58: {% include "reviews/_review_item.html" %}   ← 자기 자신을 include
   ```
   `_review_item.html`(후기 카드 partial)이 `review_list.html`의 복사본으로 덮어써져 있었다 — base.html을 extends하고 자기 자신을 include.
3. `git log -- _review_item.html` → 팀원 커밋 `19675ce`에서 깨짐(self-include=1). 직전 `a8c4e08`(내 커밋)엔 정상(자기참조 없는 67줄 partial).

**원인**
- partial(`_review_item.html`)이 목록 템플릿 내용으로 통째 덮어써져, 목록이 그 partial을 include→partial이 또 자기를 include→무한재귀. 병합/편집 중 파일을 잘못 복사한 것으로 추정.

**해결**
- `a8c4e08`의 정상 partial로 복구하되, 그새 바뀐 URL 이름에 맞춰 수정: `reviews:like`→`like_toggle`, `reviews:edit`→`review_update`, `reviews:delete`→`review_delete`. (옛 이름 그대로 복구했으면 이번엔 `NoReverseMatch`가 났을 것.)
- 재검증: `/reviews/`, `?type=food`, `?type=place`, `/reviews/write/` 모두 200.

**배운 것**
- **`{% include %}` 대상이 자기 자신이면 즉사(RecursionError).** partial 파일이 통째로 다른 내용으로 바뀌지 않았는지, 특히 병합 직후엔 `grep`으로 self-include를 먼저 확인한다.
- 트레이스백에 앱 코드 프레임이 안 보이고 `render_annotated`만 수백 줄 반복되면 **템플릿 재귀**다. include/extends 그래프부터 본다.
- **파일을 git에서 복구할 땐 그 사이 바뀐 참조(URL 이름 등)를 반드시 재확인**한다. 옛 버전 그대로 되살리면 다른 에러로 옮겨갈 뿐이다.

---

## [2026-07-20 | 후기 게시판 글쓰기 저장 실패 — `Column 'menu_id' cannot be null` (동적 폼 필드가 인스턴스에 반영 안 됨)]

**증상**
- 후기 목록의 "✏️ 후기 작성하기"(게시판에서 바로 쓰기, `/reviews/write/`)에서 메뉴를 골라 제출하면 500. 메뉴를 분명히 선택했는데도 저장이 안 됨.

**시도한 것 (원인 추적 과정)**
1. `Client`로 `menu`, `review_type`, `rating`, `content`를 채워 POST 재현 → 원문:
   ```
   django.db.utils.IntegrityError: (1048, "Column 'menu_id' cannot be null")
     File "reviews/views.py", line 142, in form_valid  → super().form_valid(form) → form.save()
   ```
2. `ReviewCreateGeneralView.get_form()`이 `form.fields['menu'] = forms.ModelChoiceField(...)`로 **런타임에 menu 필드를 추가**하는 구조. 그런데 `ReviewForm.Meta.fields`엔 `menu`가 없다.
3. Django `construct_instance()`(ModelForm.save 내부)는 **`form._meta.fields`에 있는 모델 필드만** 인스턴스에 세팅한다. 동적으로 붙인 `menu`는 `Meta.fields` 밖이라 `cleaned_data`엔 있어도 `instance.menu`에 반영되지 않는다 → 저장 시 null.

**원인**
- 폼 `Meta.fields`에 없는 필드를 `get_form()`에서 동적으로 추가하면, 유효성 검사는 되지만 `ModelForm.save()`가 그 값을 인스턴스에 넣지 않는다. `menu`가 세팅되지 않은 채 저장돼 NOT NULL 위반.

**해결**
- `ReviewCreateGeneralView.form_valid()`에서 명시적으로 세팅:
  ```python
  form.instance.menu = form.cleaned_data['menu']
  ```
- 재검증: `/reviews/write/`로 음식/음식점 후기 저장 시 302 + `menu_id` 정상 기록.

**배운 것**
- **`Meta.fields`에 없는 필드를 폼에 동적 추가하면 `ModelForm.save()`가 그 값을 저장하지 않는다.** `cleaned_data`엔 들어오므로 검증은 통과해 더 헷갈린다. 동적 필드는 `form_valid`(또는 `save(commit=False)` 후)에서 직접 `instance`에 세팅하거나, 아예 `Meta.fields`에 포함한 전용 폼을 쓴다.

---

## [2026-07-20 | 메뉴 목록 500 — `Table 'menudb.menus_menu_likes' doesn't exist` (또 마이그레이션↔DB 드리프트 + 좋아요 필드 중복)]

**증상**
- `/menus/`(메뉴 목록) 500. `/`(대시보드), `/reviews/` 등은 정상. 좋아요 토글 응답의 개수도 실제와 안 맞을 소지.

**시도한 것 (원인 추적 과정)**
1. `Client`로 `/menus/` 재현 → 원문:
   ```
   django.db.utils.ProgrammingError: (1146, "Table 'menudb.menus_menu_likes' doesn't exist")
   ```
2. `menus/models.py`를 보니 `Menu`에 좋아요가 **두 개** 공존:
   - `MenuLike`(명시적 through 모델 → 테이블 `menus_menulike`, 존재함) — 토글·추천·통계 등 앱 전반이 이걸 씀.
   - 팀원이 새로 추가한 `likes = ManyToManyField(User)` (through 없음 → Django 자동 조인테이블 `menus_menu_likes` 필요).
3. `SHOW TABLES LIKE 'menus_%'` → `menus_menulike`는 있고 `menus_menu_likes`는 **없음**.
4. `showmigrations menus` → `[X] 0001_initial`, `makemigrations menus --dry-run` → "No changes detected". 즉 `0001_initial`이 `likes` M2M(자동 테이블)을 이미 정의하는데 실제 DB엔 그 테이블만 안 만들어진 드리프트(reviews.title 건과 동일 패턴).
5. `.likes`를 실제로 읽는 곳은 `menus/views.py`의 `menu.likes.count()` 딱 한 곳. 나머지는 전부 `MenuLike`/`menu_likes` 역참조 사용(catalog엔 이미 `# 수정됨: likes -> menu_likes` 흔적).

**원인**
- 좋아요 소스가 이원화됨(중복 필드). 토글은 `MenuLike`에 쓰는데, 목록/토글 응답 카운트는 자동 M2M(`menu.likes`)을 읽어 (a) 테이블이 없어 500, (b) 있었어도 토글이 안 쓰는 테이블이라 항상 0이 나올 구조.

**해결**
- 카운트를 authoritative한 through 역참조로: `menu.likes.count()` → `menu.menu_likes.count()` (토글이 실제 쓰는 `MenuLike` 기준).
- 드리프트 정합: 커밋된 `0001_initial`이 요구하는 자동 조인테이블을 스키마 에디터로 생성(신규/AWS 배포는 0001이 처음부터 만들므로 이 드리프트 DB만 보정):
  ```python
  through = Menu._meta.get_field('likes').remote_field.through
  with connection.schema_editor() as se:
      se.create_model(through)   # menus_menu_likes 생성
  ```
- 재검증: `/menus/` 전체/필터/검색/2페이지 200, 좋아요 토글 2→1 정합.

**배운 것**
- **같은 관계를 through 모델 + 자동 M2M 둘로 만들면** 읽는 쪽/쓰는 쪽이 갈려 카운트가 어긋나거나 없는 테이블을 참조한다. 하나로 통일한다(가능하면 `likes`도 `through='MenuLike'`로). 지금은 팀원 소유 모델이라 최소 수정(카운트 소스 교정 + 누락 테이블 보정)으로 막고, 필드 일원화는 후속 과제로 남김.
- 드리프트는 컬럼뿐 아니라 **M2M 자동 조인테이블 단위로도** 난다. `SHOW TABLES`로 실제 테이블 목록까지 대조한다. (이번 세션에서만 reviews.title, menus_menu_likes 두 번.)

---

## [2026-07-21 | 서버 물리 분리 작업 — 공통 배경]

아래 세 항목(마이그레이션 이력 불일치 / NAT→브리지 IP 변경 연쇄 / GRANT 1133)은 모두 오늘 **DB 서버를 별도 머신으로 분리**하는 인프라 작업에서 나왔고, 뿌리는 초기 구성 선택에 있다. 세 항목 앞에 배경을 한 번만 정리한다.

**처음에 선택했던 구성과 그 한계**
- 비전공자로 시작해 초기에는 "웹서버 + DB서버 한 세트"를 **각자의 PC에 똑같이 복제**해 작업했다. 팀원 A의 PC에도 Server1(웹)+Server2(DB), 팀원 B의 PC에도 Server1(웹)+Server2(DB)가 있는 형태. 각자 자기 환경에서 개발하고 코드를 GitHub에 올려 병합했다.
- 당시엔 "각자 독립적으로 개발하니 편하다"고 봤지만, 실제로는 하나의 서비스가 아니라 **서로 다른 두 개의 서비스를 각자 운영**하는 상태였다.
- 문제는 병합 시점에 드러났다:
  - Git으로 합쳐지는 건 **코드뿐**이고, DB의 데이터·스키마 상태는 합쳐지지 않는다. 각자의 DB는 각자의 시점·이력을 그대로 유지했다.
  - 각자 `makemigrations`를 돌려 **마이그레이션 파일 계보가 갈라졌고**, 충돌을 넘기려 파일을 지우고 재생성하는 일이 반복돼 "코드의 마이그레이션 파일"과 "DB의 적용 이력"이 어긋났다.
  - `.env`도 각자의 IP·계정 기준이라 병합 후 어느 값이 맞는지 판단하기 어려웠다.
  - 결과적으로 코드는 하나로 합쳐졌지만 그 코드가 바라보는 **DB는 두 개였고 서로 상태가 달랐다**.
- 짚어둘 점: 개발 환경을 각자 갖는 것 자체가 잘못은 아니다. 문제는 그 환경이 개발용에 머물지 않고 **각자의 운영 환경처럼 굳으면서 기준이 되는 단일 데이터 계층이 없었다**는 데 있다.

**정상화 방향과 실제 작업**
- 목표: 웹 계층과 데이터 계층이 각각 하나씩만 존재하고 **두 사람이 같은 DB를 바라보는 단일 3계층** → 웹서버(Server1)는 내 PC, DB 서버(Server2)는 팀원 PC에 두고 네트워크로 연결.
- 네트워크: VMware 어댑터를 **NAT → 브리지**로 전환. 기존 NAT의 `192.168.32.x`는 VMware가 호스트 내부에 만든 가상 네트워크라 같은 공유기의 다른 PC에서 도달 불가. 브리지 후 각 VM이 공유기에서 직접 IP를 받으며 **Server2 주소가 192.168.32.73 → 192.168.32.78** 로 변경(Server1 = 192.168.32.74).
- 데이터: 실제 데이터가 쌓여 있던 **기존 DB를 기준**으로 `mysqldump` 덤프를 떠 팀원 PC의 DB로 이전(메뉴 199건, 사용자 59건 등).
- 이 과정에서 아래 세 문제가 발생·해결됐고, 셋 다 "각자 독립 환경에서 작업 후 나중에 합치려 했다"는 초기 선택에서 파생됐다.

**이 경험에서 정리한 원칙**
- 팀 개발에서 **코드는 Git으로 합쳐도 데이터·스키마 이력은 합쳐지지 않는다.** 개발 환경은 각자 두더라도 **기준 DB는 하나**여야 한다.
- **마이그레이션은 한 사람이 생성하고 나머지는 적용만** 하는 원칙이 필요하다.
- 설정은 하드코딩하지 않고 **환경변수로 분리**해야 각자 다른 IP·계정을 쓰면서 같은 코드를 공유할 수 있다.

---

## [2026-07-21 | DB 복원 후 migrate 실패 — Duplicate column 'cuisine_id' (1060), 마이그레이션 이력 불일치]

> 발표·포트폴리오 강조 사례. 진단 과정 위주로 상세히 남긴다.

**증상**
- DB 복원 후 Server1에서 `python manage.py migrate` 실행 시 실패:
  ```
  django.db.utils.OperationalError: (1060, "Duplicate column name 'cuisine_id'")
  ```

**시도한 것 (진단 과정 — 가설 → 검증 → 다음 가설)**

1. **데이터 유실부터 배제.** 복원이 덜 됐는지부터 확인.
   ```sql
   SELECT COUNT(*) FROM menus_menu;      -- → 199
   SELECT COUNT(*) FROM accounts_user;   -- → 59
   SHOW TABLES;                          -- → 23개 테이블 전부 존재
   ```
   → 복원 자체는 성공. **데이터 문제가 아니다.**

2. **Django가 인식하는 적용 이력 확인.** migrate가 무엇을 "안 됐다"고 보는지.
   ```sql
   SELECT app, name FROM django_migrations
    WHERE app IN ('accounts','menus','records','reviews');
   ```
   결과:
   ```
   accounts 0001_initial
   accounts 0002_allergy_userpreference_userallergy_user_allergies
   accounts 0003_userpreference_cuisine_userpreference_user_and_more
   menus    0001_initial / 0002_menulike
   records  0001_initial / 0002_mealrecord_menu
   reviews  0001_initial / 0002_reviewview / 0003_review_review_type
   ```

3. **코드에 있는 마이그레이션 파일과 대조.**
   ```bash
   ls accounts/migrations/ menus/migrations/ records/migrations/ reviews/migrations/
   ```
   결과:
   ```
   accounts: 0001_initial, 0002_initial 뿐
   menus:    0001_initial 뿐
   reviews:  0001_initial 뿐
   ```
   → **DB 기록과 코드 파일의 이름 계보가 서로 다르다.** 특히 accounts는 DB엔 `0002_allergy_...`인데 코드엔 `0002_initial`로 **이름 자체가 다르다.**

4. **"코드가 옛 버전인가?" 가설 검증.**
   ```bash
   git status             # 브랜치 origin과 일치, 작업 폴더 깨끗
   git log --oneline -5   # 최신 커밋 전부 존재
   ```
   → 코드는 최신. **`git pull`로 해결되는 문제가 아니다.**

5. **"그럼 스키마는 어느 쪽이 맞나?" 를 컬럼 단위로 확인.**
   ```sql
   SHOW COLUMNS FROM accounts_userpreference;   -- → cuisine_id 존재
   SHOW COLUMNS FROM reviews_review;            -- → review_type, title, category 모두 존재
   ```
   → **DB 스키마는 이미 최신 코드가 기대하는 상태.** Django만 "미적용"으로 판단하고 있었다.

**원인**
- 각자 환경에서 `makemigrations`를 돌리고, 충돌 날 때마다 마이그레이션 파일을 **삭제·재생성**하면서 파일명 계보가 **이미 배포된 DB의 `django_migrations` 기록과 갈라졌다.**
- 스키마는 이미 반영돼 있는데 Django는 미적용으로 인식해 다시 실행하려다 **컬럼 중복(1060)** 이 발생.

**해결**
- 스키마가 이미 일치함을 컬럼 단위로 확인(5단계)한 뒤, **SQL은 실행하지 않고 적용 기록만** 남김:
  ```bash
  python manage.py migrate accounts --fake
  python manage.py showmigrations     # 전부 [X] 확인
  sudo systemctl restart gunicorn
  ```
- 이후 브라우저에서 로그인·메뉴·후기·좋아요 등 **실제 화면으로 최종 검증.**

**배운 것**
- `--fake`는 **"스키마가 이미 그 상태임을 확인한 뒤에만"** 쓸 수 있다. 확인 없이 먼저 쓰면 Django는 적용됐다고 믿는데 실제 DB엔 컬럼이 없는, **훨씬 찾기 어려운 상태**가 된다. 그래서 `SHOW COLUMNS` 확인을 먼저 했다.
- 에러 메시지(Duplicate column)만 보면 DB가 잘못된 것 같지만, 실제 원인은 DB가 아니라 **코드와 DB의 마이그레이션 이력 불일치**였다. **증상이 난 계층과 원인이 있는 계층이 다를 수 있다.**
- 팀 프로젝트에서 마이그레이션 파일은 **삭제·재생성하지 않는다.** 로컬에선 멀쩡해도 이미 배포된 DB와 계보가 갈라진다.
- 데이터 이전 후 검증은 **[데이터 무결성 → 스키마 → 마이그레이션 이력]** 순으로 좁혀 들어가는 것이 안전하다.

---

## [2026-07-21 | NAT→브리지 전환에 따른 IP 변경 연쇄 재설정]

**증상 / 상황**
- DB 서버를 팀원 PC로 분리하려 했으나 기존 **NAT 모드에서는 팀원 PC가 Server1에 접근할 수 없었다.** `192.168.32.x`는 VMware가 호스트 안에 만든 가상 네트워크라 같은 공유기의 다른 PC에서 도달 불가.

**해결 과정**
- VMware Network Adapter를 **NAT → Bridged**로 전환(양쪽 VM 모두).
- 브리지 후 VM이 공유기에서 직접 IP를 받음 → **Server2가 .73 → .78로 변경.**
- `ping`으로 상호 도달 확인.

**IP 변경으로 연쇄적으로 깨진 것들** (핵심)

| 대상 | 무엇이 깨졌나 | 조치 |
|---|---|---|
| MariaDB 계정 | `'menuuser'@'옛IP'`로 등록돼 새 IP에서 접속 거부 | 새 IP로 `CREATE USER` + `GRANT` |
| ufw 방화벽 | 3306/6379 허용 규칙이 옛 IP를 가리킴 | 새 IP로 `allow` 규칙 추가 |
| .env | `DB_HOST`, `ALLOWED_HOSTS`, `REDIS_URL`, `CSRF_TRUSTED_ORIGINS` 전부 옛 IP | 새 IP로 수정 |
| Nginx | `server_name`이 옛 IP | 새 IP로 수정 후 `nginx -t` / `reload` |
| SSL 인증서 | CN·subjectAltName에 옛 IP가 박혀 브라우저 경고 심화 | `openssl`로 새 IP 기준 재발급 |

**배운 것**
- 온프레미스 구성은 **IP에 강하게 결합**돼 있다. IP 하나가 바뀌면 DB 권한·방화벽·앱 설정·웹서버 설정·TLS 인증서까지 **5개 계층을 전부** 다시 만져야 한다.
- 공유기가 바뀌면(집 ↔ 학원) 이 작업을 통째로 반복해야 한다. **발표 장소에서는 사전 재설정·검증이 필요하다.**
- **DHCP 환경에서는 재부팅만으로도 재발**할 수 있어 고정 IP 설정이 필요하다.
- 이 경험이 **2단계 AWS 이전의 직접적 명분**이 된다(엔드포인트 기반 접근, 관리형 DB, 인증서 관리 위임).

---

## [2026-07-21 | GRANT 실행 시 ERROR 1133 (28000) — 계정(user+host) 미존재]

**증상**
- 팀원 PC의 MariaDB에서 새 IP에 권한을 주려고 실행:
  ```sql
  GRANT ALL PRIVILEGES ON menudb.* TO 'menuuser'@'192.168.32.74';
  -- → ERROR 1133 (28000)
  ```

**원인**
- `GRANT`는 **이미 존재하는 계정에만** 권한을 부여한다. 해당 host의 계정이 없었다.
- 과거 MySQL은 GRANT가 계정을 자동 생성했지만 **현재는 그렇지 않다.**
- MariaDB에서 계정은 **"아이디 + 접속 출발지 host"가 한 세트**이며, `menuuser@옛IP`와 `menuuser@새IP`는 이름만 같을 뿐 **서로 다른 계정**이다.

**해결**
```sql
CREATE USER 'menuuser'@'192.168.32.74' IDENTIFIED BY '***';
GRANT ALL PRIVILEGES ON menudb.* TO 'menuuser'@'192.168.32.74';
FLUSH PRIVILEGES;
SELECT user, host FROM mysql.user WHERE user='menuuser';   -- 확인
```

**배운 것**
- DB 접속 실패 시 가장 먼저 볼 것은 **비밀번호가 아니라** `SELECT user, host FROM mysql.user`로 **"그 출발지의 계정이 존재하는가"** 이다.
- 계정 단위가 아니라 **(계정 + host) 단위**라는 점이 IP 변경 시 장애의 원인이 된다.
