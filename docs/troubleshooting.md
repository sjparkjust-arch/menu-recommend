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
