# 웹사이트를 인터넷에 올리기까지 — 단계별 상세

> "그냥 로컬에서 돌던 사이트"가 `https://192.168.32.74` 로 열리기까지 **무엇을, 왜, 어떤 순서로** 했는지 초보 눈높이로 풀어 쓴 문서.
> 특히 **Gunicorn·Nginx가 뭔지 / 포트 번호(:8000)가 URL에서 사라진 과정 / HTTP→HTTPS 전환**을 자세히 다룬다.
> 상위 개요는 `docs/deployment-infra-guide.md`, 실제 장애 원문은 `docs/troubleshooting.md`.

---

## 0. 큰 그림 — 4단계로 "포트가 사라지고 https가 붙는다"

```
1단계  개발용        http://127.0.0.1:8000     ← Django runserver (내 PC에서만)
2단계  앱서버 도입    (소켓)                    ← Gunicorn 이 Django 를 실행
3단계  웹서버 도입    http://192.168.32.74      ← Nginx 가 앞에서 받음 (:80, 포트 사라짐)
4단계  암호화        https://192.168.32.74     ← Nginx 에 인증서(:443) + 80→443
```

핵심만 먼저:
- **Gunicorn** = 파이썬 앱(Django)을 실제로 돌리는 **앱서버**. (그 "하나 또 뭐야 그거"가 이거다.)
- **Nginx** = 그 앞에 서서 요청을 받아주는 **웹서버(리버스 프록시)**.
- **포트가 사라진 이유** = 브라우저는 http면 80, https면 443을 **기본값으로 자동 사용**해서 URL에 안 쓴다. 우리가 Nginx를 80/443에 세웠기 때문에 `:8000`을 더 안 붙인다.

---

## 1단계 — 개발용 서버 (`runserver`, 포트 8000)

처음엔 이렇게 띄웠다:
```bash
python manage.py runserver 0.0.0.0:8000
# → http://127.0.0.1:8000 또는 http://192.168.32.74:8000
```
- `runserver`는 Django에 내장된 **개발 전용** 서버다.
- **왜 이걸로 운영하면 안 되나?**
  1. 한 번에 요청을 거의 하나씩만 처리(동시 접속에 약함).
  2. 성능·보안이 운영 기준 미달(공식 문서도 "운영에 쓰지 말라"고 명시).
  3. 정적파일(CSS/이미지)도 비효율적으로 처리.
  4. 터미널을 닫으면 서버도 꺼짐.
- 그리고 주소에 **`:8000`이 붙는다** — 사용자가 포트를 외워 쳐야 하니 안 예쁘고 불편하다.

> 그래서 "운영용 앱서버(Gunicorn)"와 "앞단 웹서버(Nginx)"를 도입한다.

---

## 2단계 — 앱서버 Gunicorn 도입

### Gunicorn이 뭔데?
- **G**reen **Unicorn. 파이썬 웹앱을 여러 프로세스로 안정적으로 돌리는 WSGI 앱서버**.
- **WSGI**: 파이썬 웹앱과 서버 사이의 표준 약속. 우리 앱의 진입점은 `config/wsgi.py`의 `application`. 그래서 Gunicorn을 `config.wsgi:application`으로 실행한다.
- runserver와 차이: Gunicorn은 **워커(프로세스)를 여러 개** 띄워 동시 요청을 나눠 처리하고, 운영에 맞게 안정적이다.

### 직접 한번 실행
```bash
cd /home/tester/apps/menu-recommend
venv/bin/gunicorn --workers 3 config.wsgi:application
# 기본은 http://127.0.0.1:8000 로 뜬다
```
- `--workers 3`: 프로세스 3개. 통상 권장 `2 × CPU코어 + 1`.

### 그런데 포트(TCP) 대신 "유닉스 소켓"을 쓴다
같은 서버 안에서 Nginx ↔ Gunicorn이 통신할 거라, TCP 포트 대신 **소켓 파일**로 연결하면 더 빠르고 외부에 포트가 안 열린다:
```bash
venv/bin/gunicorn --workers 3 \
  --bind unix:/run/gunicorn/gunicorn.sock \
  config.wsgi:application
```
- `/run/gunicorn/gunicorn.sock` 이라는 **파일**이 창구가 된다. 밖(인터넷)에서는 이 소켓에 직접 못 붙는다 → Nginx만 통한다.

### 터미널 닫아도 계속 돌게 — systemd 서비스 등록
매번 손으로 켜고 터미널 닫으면 꺼지니까, **리눅스 서비스**로 등록해 자동 실행·자동 재시작하게 만든다. 우리 유닛 파일은 `deploy/gunicorn.service`:
```ini
[Service]
User=tester
Group=www-data
UMask=007
WorkingDirectory=/home/tester/apps/menu-recommend
RuntimeDirectory=gunicorn                      # /run/gunicorn 을 만들고 권한 관리
ExecStart=/home/tester/apps/menu-recommend/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/run/gunicorn/gunicorn.sock \
    --access-logfile - --error-logfile - \
    config.wsgi:application
Restart=on-failure                             # 죽으면 자동 재시작
[Install]
WantedBy=multi-user.target                     # 부팅 시 자동 실행
```
등록·기동:
```bash
sudo cp deploy/gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn     # 지금 켜고 + 부팅 시 자동
sudo systemctl status gunicorn           # 잘 떴나 확인
ls -l /run/gunicorn/gunicorn.sock        # 소켓 파일 생겼나
```
- `User=tester, Group=www-data, UMask=007`: 소켓 파일을 Nginx(=`www-data` 사용자)가 **읽을 수 있게** 권한을 맞추는 부분. (여기 어긋나면 Nginx가 502를 낸다.)

> 지금 상태: Gunicorn이 소켓으로 Django를 돌리고 있다. 하지만 **소켓은 브라우저가 못 붙는다.** 그래서 앞에 Nginx가 필요하다.

---

## 3단계 — 웹서버 Nginx 도입 (여기서 포트 `:8000`이 URL에서 사라진다)

### Nginx가 뭔데? 왜 앞에 둬?
- **Nginx** = 고성능 **웹서버 / 리버스 프록시**. "리버스 프록시"는 **사용자 대신 요청을 받아 뒤의 Gunicorn에 넘겨주는 중계자**.
- 왜 앞에 두나:
  1. **정적파일(CSS/이미지)을 Nginx가 직접** 빠르게 응답(파이썬 안 거침).
  2. **HTTPS(암호화)를 Nginx가 담당** (다음 단계).
  3. 동시 접속·보안 처리에 강하다.
  4. **80 포트**로 받기 때문에 사용자는 `:8000` 없이 깔끔한 주소를 쓴다.

### 왜 URL에서 포트가 사라지나 (★질문한 부분)
- 브라우저는 **`http://`면 자동으로 80번, `https://`면 자동으로 443번** 포트에 접속한다. 그래서 이 두 경우엔 포트를 URL에 안 쓴다.
- 1단계에서 `:8000`을 쓴 이유는 runserver/Gunicorn이 **8000번**이라는 "비표준" 포트에 있었기 때문. 표준이 아니면 브라우저가 자동으로 못 찾아 **직접 써줘야** 했다.
- 이제 **Nginx를 80번(그리고 443번)에 세우면**, 브라우저가 알아서 그 포트로 가므로 `http://192.168.32.74` (포트 없이!)로 접속된다. 내부적으로 Nginx가 그 요청을 Gunicorn 소켓으로 넘긴다.
- 정리: **포트를 "지운" 게 아니라, 표준 포트(80/443)에 서버를 놓아서 브라우저가 자동으로 채워 넣게 만든 것.**

### Nginx 사이트 설정 (HTTP 버전)
`/etc/nginx/sites-available/menu-recommend` (요지):
```nginx
server {
    listen 80;                          # ← 표준 http 포트. 그래서 URL에 :8000 안 씀
    server_name 192.168.32.74;

    location /static/ {                 # 정적파일은 Nginx가 직접
        alias /home/tester/apps/menu-recommend/staticfiles/;
    }
    location / {                        # 나머지는 Gunicorn 소켓으로 전달
        proxy_pass http://unix:/run/gunicorn/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;   # 원 스킴(http/https) 전달 — 4단계에서 중요
    }
}
```
활성화·반영:
```bash
sudo ln -s /etc/nginx/sites-available/menu-recommend /etc/nginx/sites-enabled/
sudo nginx -t                     # ★ 문법 검사(반드시 먼저)
sudo systemctl reload nginx       # 설정 반영
```
- 정적파일이 실제로 있어야 하므로 그 전에:
```bash
venv/bin/python manage.py collectstatic --noinput   # staticfiles/ 로 모음
```
- Django 쪽에도 `ALLOWED_HOSTS=192.168.32.74` 를 넣어야 그 호스트로 들어온 요청을 허용한다.

> 우리가 실제로 겪은 함정: `apt install nginx` 하면 Nginx가 자동 기동돼 **80번을 이미 점유** → 뒤늦게 `bind() to 0.0.0.0:80 failed (Address already in use)`. (troubleshooting.md 1번) 그리고 공용 `static/`을 `STATICFILES_DIRS`에 안 넣어 **CSS가 안 반영**된 것도 이때 겪었다.

지금 상태: **`http://192.168.32.74`** (포트 없이) 로 사이트가 열린다. 남은 건 암호화(https).

---

## 4단계 — HTTP → HTTPS 전환 (암호화 붙이기)

### 왜 HTTPS?
- http는 평문이라 중간에서 훔쳐볼 수 있다. https는 **TLS로 암호화**해 안전하다. 로그인·개인정보가 있으면 사실상 필수.
- 구조상 **암호화는 Nginx가 담당(TLS 종료)** 한다. 즉 브라우저↔Nginx 구간만 암호화하고, Nginx↔Gunicorn(같은 서버 내부)은 평문으로 둔다.

### (a) 인증서 만들기 — 내부망이라 "자체 서명(self-signed)"
공인 도메인이 아니라 사설 IP라, 직접 서명한 인증서를 만들었다. **중요: 최신 브라우저는 CN이 아니라 SAN(subjectAltName)으로 검사**하므로 SAN에 IP를 꼭 넣는다:
```bash
sudo openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout /etc/ssl/private/menu-recommend.key \
  -out    /etc/ssl/certs/menu-recommend.crt \
  -subj   "/C=KR/ST=Seoul/L=Seoul/O=MenuRecommend/CN=192.168.32.74" \
  -addext "subjectAltName=IP:192.168.32.74"     # ★ 이게 없으면 ERR_CERT_COMMON_NAME_INVALID
# 확인:
openssl x509 -noout -text -in /etc/ssl/certs/menu-recommend.crt | grep -A1 "Subject Alternative Name"
```
- 우리가 겪은 것: 처음에 SAN 없이 CN만 넣었다가 `NET::ERR_CERT_COMMON_NAME_INVALID` 로 아예 막힘 → SAN 추가로 해결. (troubleshooting.md 6번)
- 남는 `ERR_CERT_AUTHORITY_INVALID`(신뢰 안 된 발급자) 경고는 **자체 서명이라 정상** — 예외 진행하거나 각 PC에 `.crt`를 신뢰 루트로 설치하면 사라진다.

### (b) Nginx에 443(SSL) 블록 + 80→443 리다이렉트
```nginx
server {                                 # 80으로 오면 무조건 https로 보냄
    listen 80;
    server_name 192.168.32.74;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl;                      # ← 표준 https 포트(그래서 URL에 포트 안 씀)
    server_name 192.168.32.74;
    ssl_certificate     /etc/ssl/certs/menu-recommend.crt;
    ssl_certificate_key /etc/ssl/private/menu-recommend.key;

    location /static/ { alias /home/tester/apps/menu-recommend/staticfiles/; }
    location / {
        proxy_pass http://unix:/run/gunicorn/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;   # ★ "원래 https였다" 를 앱에 알림
    }
}
```
```bash
sudo nginx -t && sudo systemctl reload nginx
```

### (c) Django 쪽 짝맞춤 설정 — 안 하면 두 가지 사고
TLS를 Nginx에서 풀면 Django는 요청을 http로 착각한다. 그래서 두 설정이 필수다(우리 `config/settings.py`에 있음):
```python
# Nginx가 넘긴 X-Forwarded-Proto 로 "이 요청은 https" 라고 인식
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# https 폼 POST(로그인 등)의 CSRF 통과에 필요 (scheme 포함)
CSRF_TRUSTED_ORIGINS = ['https://192.168.32.74']   # 실제로는 .env 로 주입
```
```bash
# .env
CSRF_TRUSTED_ORIGINS=https://192.168.32.74
ALLOWED_HOSTS=192.168.32.74
DEBUG=False
```
```bash
sudo systemctl restart gunicorn   # .env/settings 반영
```

**실제로 여기서 터진 2가지 (발표에 좋은 사례):**
1. **무한 리다이렉트 `ERR_TOO_MANY_REDIRECTS`** — `SECURE_PROXY_SSL_HEADER`가 없으니 Django가 "http네? → https로" 리다이렉트를 무한 반복. 헤더 인식 설정으로 해결. (리다이렉트는 **Nginx 한 곳에서만**, 앱단 `SECURE_SSL_REDIRECT`는 켜지 않는다.) (troubleshooting.md 7번)
2. **로그인 403 `Origin checking failed`** — https 전환 후 `CSRF_TRUSTED_ORIGINS`가 비어 폼 POST가 전부 거부. 신뢰 오리진 추가로 해결. GET은 되는데 POST만 깨지면 이걸 의심. (troubleshooting.md 5번)

> 지금 상태: **`https://192.168.32.74`** (포트 없이, 자물쇠). 끝.

---

## 5. 최종 요청 흐름 한 줄

```
브라우저  https://192.168.32.74
   │  (443, TLS 암호화)
   ▼
Nginx  ── 정적파일이면 여기서 응답
   │  (여기서 암호화 풀림 = TLS 종료, X-Forwarded-Proto 로 'https였음' 표시)
   │  유닉스 소켓
   ▼
Gunicorn (워커 3) ── config.wsgi:application ──▶ Django
   │
   ▼  (사설망 TCP)
MariaDB(3306) · Redis(6379)   ← Server2
```

## 6. "왜 포트가 사라졌나" 3줄 정리 (질문 답)
1. 브라우저는 http=80, https=443을 **자동으로** 붙인다 → 이 포트면 URL에 안 쓴다.
2. 개발 때 `:8000`을 쓴 건 Gunicorn/runserver가 비표준 포트라 **직접 써줘야** 했기 때문.
3. **Nginx를 80/443(표준)에 세우니** 브라우저가 알아서 찾아가고, Nginx가 내부적으로 Gunicorn 소켓에 넘겨 → 사용자는 포트 없는 주소만 본다.

## 7. 순서 체크리스트 (처음 올릴 때)
```
[ ] venv + pip install -r requirements.txt
[ ] .env 작성 (SECRET_KEY, DEBUG=False, ALLOWED_HOSTS, DB_*, REDIS_URL, CSRF_TRUSTED_ORIGINS)
[ ] python manage.py migrate           (커스텀 User는 첫 migrate 전에!)
[ ] python manage.py collectstatic
[ ] gunicorn.service 등록 → systemctl enable --now gunicorn → 소켓 확인
[ ] Nginx 80 설정 → nginx -t → reload → http 로 접속 확인
[ ] openssl 로 자체서명 인증서(SAN=IP) 발급
[ ] Nginx 443 + 80→443 리다이렉트 → nginx -t → reload
[ ] settings: SECURE_PROXY_SSL_HEADER + CSRF_TRUSTED_ORIGINS → restart gunicorn
[ ] https 로 접속 + 로그인(POST)까지 확인
```

---

### 자주 쓰는 점검 명령
```bash
sudo systemctl status gunicorn        # 앱 상태
sudo systemctl restart gunicorn       # 코드/.env 반영
sudo nginx -t && sudo systemctl reload nginx   # Nginx 설정 반영
sudo journalctl -u gunicorn -f        # Django 에러 로그
sudo tail -f /var/log/nginx/error.log # Nginx 에러 로그
sudo ss -ltnp | grep -E ':(80|443)'   # 포트 점유 확인
```
