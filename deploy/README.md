# 배포 설정 (Gunicorn + Nginx)

Server1(웹/앱 계층)에 Django 앱을 **Gunicorn(유닉스 소켓) + Nginx(리버스 프록시)** 로 올리기 위한 설정 파일 모음.

| 파일 | 복사 위치 |
|------|-----------|
| `gunicorn.service` | `/etc/systemd/system/gunicorn.service` |
| `menu-recommend.nginx.conf` | `/etc/nginx/sites-available/menu-recommend` |

구성: 클라이언트 → **Nginx :80** → (`/static/`, `/media/`는 직접 서빙) → 그 외는 **유닉스 소켓** → **Gunicorn(worker 3) → Django**

---

## 0. 각자 환경에 맞게 고쳐야 할 부분 ⚠️

파일 안 경로/계정/IP가 **Server1(tester, 192.168.32.74) 기준으로 하드코딩**돼 있다. 다른 환경이면 복사 후 아래를 수정할 것.

### `gunicorn.service`
- `User=tester` → 앱을 돌릴 리눅스 계정
- `Group=www-data` → Nginx 실행 그룹(우분투 기본 `www-data`). 소켓을 Nginx가 읽으려면 이 그룹이어야 함
- `WorkingDirectory=` / `ExecStart=`의 `/home/tester/apps/menu-recommend` → 실제 프로젝트 경로
- `ExecStart=`의 `venv/bin/gunicorn` → 실제 가상환경 경로

### `menu-recommend.nginx.conf`
- `server_name 192.168.32.74;` → 접속할 서버 IP(또는 도메인). **80/443 두 server 블록 모두** 바꿀 것.
- `location /static/`, `/media/`의 `alias` 경로 → 실제 `STATIC_ROOT`, `MEDIA_ROOT` 경로 (끝 슬래시 유지)
- `ssl_certificate` / `ssl_certificate_key` → 실제 인증서/키 경로 (아래 3. HTTPS 참고)

> `.env`는 이 저장소에 없다(시크릿). `.env.example`을 복사해 채우고, **프로덕션은 반드시 `DEBUG=False`** + `ALLOWED_HOSTS`에 서버 IP 포함 + (HTTPS면) `CSRF_TRUSTED_ORIGINS=https://<IP>`.

---

## 1. 사전 준비 (앱 계정, sudo 불필요)

```bash
cd /home/tester/apps/menu-recommend
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput   # STATIC_ROOT 채우기 (CSS 깨짐 방지)
```

## 2. Gunicorn (systemd)

```bash
sudo cp deploy/gunicorn.service /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn
```

## 3. HTTPS 인증서 (자체 서명, 내부망)

내부망이라 Let's Encrypt(공인 CA)를 못 쓰므로 **자체 서명 인증서**를 만든다.
파일은 저장소가 아니라 `/etc/ssl` 에 둔다. **Nginx(4단계)가 이 파일을 참조하므로 반드시 먼저 생성**해야 `nginx -t` 가 통과한다.

```bash
# 키(/etc/ssl/private) + 인증서(/etc/ssl/certs) 를 한 번에 생성. 유효기간 825일.
# IP로 접속하므로 CN만이 아니라 반드시 SAN(subjectAltName)에 IP를 넣어야 최신 브라우저가 인정한다.
sudo openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout /etc/ssl/private/menu-recommend.key \
  -out    /etc/ssl/certs/menu-recommend.crt \
  -subj   "/C=KR/ST=Seoul/L=Seoul/O=MenuRecommend/CN=192.168.32.74" \
  -addext "subjectAltName=IP:192.168.32.74"

# 개인키 권한 잠그기 (소유자만 읽기)
sudo chmod 600 /etc/ssl/private/menu-recommend.key
```

주의사항:
- **SAN 필수**: `-addext "subjectAltName=IP:192.168.32.74"` 없이 CN만 넣으면 브라우저가
  `NET::ERR_CERT_COMMON_NAME_INVALID` 를 낸다. IP가 바뀌면 인증서도 다시 만든다.
- **브라우저 경고 정상**: 자체 서명이라 첫 접속 시 "안전하지 않음" 경고가 뜬다. 신뢰 예외로 진행하거나,
  각 클라이언트에 `.crt` 를 신뢰 루트로 설치하면 사라진다.
- **개인키는 절대 커밋/공유 금지.** `/etc/ssl/private/` + `chmod 600`. 저장소엔 `*.key`/`*.crt` 가
  `.gitignore` 되어 있지만, 애초에 repo에 두지 않는다.
- **만료 관리**: `-days 825` 경과 후 재발급 필요.
  만료일 확인 → `openssl x509 -enddate -noout -in /etc/ssl/certs/menu-recommend.crt`
- 앱/프록시 쪽 대응은 이미 코드에 반영됨:
  - `nginx.conf`: 80→443 리다이렉트, 443 `ssl`, `X-Forwarded-Proto $scheme` 전달
  - `settings.py`: `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')`
  - `.env`: `CSRF_TRUSTED_ORIGINS=https://192.168.32.74` (없으면 https 로그인 POST가 CSRF 403)

## 4. Nginx

> 3단계 인증서를 먼저 만든 뒤 진행할 것 (없으면 `nginx -t` 가 `cannot load certificate` 로 실패).

```bash
sudo cp deploy/menu-recommend.nginx.conf /etc/nginx/sites-available/menu-recommend
sudo ln -s /etc/nginx/sites-available/menu-recommend /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default   # 기본 사이트 비활성화
sudo nginx -t                                  # 문법 검사 (OK 확인 후에만 reload)
sudo systemctl reload nginx
```

설정을 바꾼 뒤에는:
- 코드/`.env` 변경 → `sudo systemctl restart gunicorn`
- Nginx 설정 변경 → `sudo nginx -t && sudo systemctl reload nginx`

---

## 5. 검증

```bash
# Gunicorn 살아있는지
sudo systemctl status gunicorn --no-pager

# 소켓이 tester:www-data, 0770 (srwxrwx---) 인지 — 502의 핵심
ls -l /run/gunicorn/gunicorn.sock

# Nginx 문법
sudo nginx -t

# HTTP → HTTPS 리다이렉트 확인 (301, Location: https://...)
curl -I http://192.168.32.74/

# HTTPS 응답 (자체 서명이라 -k 로 인증서 검증 건너뜀. 비로그인은 302 → /accounts/login/ 정상)
curl -kI https://192.168.32.74/

# 정적 파일이 Nginx로 직접 나오는지 (200 + Content-Type: text/css 등)
curl -kI https://192.168.32.74/static/admin/css/base.css

# 인증서 SAN 에 IP가 들어갔는지
openssl x509 -noout -text -in /etc/ssl/certs/menu-recommend.crt | grep -A1 "Subject Alternative Name"
```

로그:
```bash
sudo journalctl -u gunicorn -n 50 --no-pager   # 앱 에러/트레이스백
sudo tail -f /var/log/nginx/error.log          # 프록시/정적 서빙 에러
```

---

## 6. 자주 나는 에러와 원인

### 502 Bad Gateway → 대개 **소켓 권한** 또는 Gunicorn 다운
- `ls -l /run/gunicorn/gunicorn.sock` 이 `srwxrwx--- tester www-data` 여야 함.
  - 그룹이 `www-data`가 아니면 → 유닛의 `Group=www-data`, `UMask=007` 확인 후 `daemon-reload` + `restart`.
- 소켓 파일이 아예 없으면 Gunicorn이 안 뜬 것 → `journalctl -u gunicorn` 확인
  (흔한 원인: `.env` 누락/오타, `DB_*`·`REDIS_URL` 접속 실패, venv 경로 오타).
- `nginx error.log`에 `connect() to unix:/run/... failed (13: Permission denied)` → 소켓 그룹/권한 문제.
- `(2: No such file or directory)` → 소켓 경로 불일치(유닛의 `--bind`와 nginx `proxy_pass` 경로가 같아야 함).

### CSS/JS 깨짐 (스타일 없는 맨 HTML) → **정적 파일 서빙 문제**
- `collectstatic`을 안 돌렸다 → `python manage.py collectstatic --noinput`.
- nginx `alias` 경로가 실제 `STATIC_ROOT`와 다르다 → 경로/끝 슬래시 확인.
- Nginx(www-data)가 경로를 못 읽는다 → 홈부터 프로젝트까지 디렉토리에 `o+x`(traverse) 권한 필요.
  `namei -l /home/tester/apps/menu-recommend/staticfiles` 로 각 단계 권한 확인.
- `curl -I .../static/...` 가 502/404면 프록시로 새는 것 → `location /static/` 블록 위치/오타 확인.

### 400 Bad Request → **ALLOWED_HOSTS**
- `.env`의 `ALLOWED_HOSTS`에 접속 IP/도메인이 없음. `DEBUG=False`면 필수.

### TemplateDoesNotExist (앱 템플릿) → **재시작 안 함**
- 새 앱/템플릿 디렉토리를 추가하면 프로세스 시작 시점의 앱 템플릿 목록이 캐시된다.
  `sudo systemctl restart gunicorn` 으로 프로세스를 새로 띄울 것.

### 업로드 이미지가 413 → **본문 크기 제한**
- nginx `client_max_body_size 10M;` 확인(이 설정에 이미 포함).

### CSRF 403 (`Origin checking failed`) → **HTTPS 신뢰 오리진 누락**
- `DEBUG=False` + https 에서 폼 POST(로그인 등)가 막힌다.
- `.env`에 `CSRF_TRUSTED_ORIGINS=https://192.168.32.74`(scheme 포함) 추가 후 `restart gunicorn`.
- 함께 확인: nginx가 `X-Forwarded-Proto $scheme` 를 넘기고, settings에 `SECURE_PROXY_SSL_HEADER` 가 있어야 Django가 https로 인식.

### 무한 리다이렉트(`ERR_TOO_MANY_REDIRECTS`) → **프록시 헤더 누락**
- Django가 원 요청을 http로 오인해 계속 https로 리다이렉트. `X-Forwarded-Proto` 전달 +
  `SECURE_PROXY_SSL_HEADER` 설정을 확인.

### `nginx -t` 실패: `cannot load certificate ... No such file` → **인증서 먼저**
- 3단계(인증서 생성)를 건너뛰고 4단계를 했다. `openssl` 로 `.crt`/`.key` 를 먼저 만들 것.

### 브라우저 `NET::ERR_CERT_*` 경고 → **자체 서명이라 정상**
- `ERR_CERT_AUTHORITY_INVALID`: 자체 서명이라 당연. 신뢰 예외로 진행하거나 `.crt`를 클라이언트에 신뢰 설치.
- `ERR_CERT_COMMON_NAME_INVALID`: SAN에 IP가 없음 → `-addext "subjectAltName=IP:<IP>"` 로 재발급.
