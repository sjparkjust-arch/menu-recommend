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
- `server_name 192.168.32.74;` → 접속할 서버 IP(또는 도메인)
- `location /static/`, `/media/`의 `alias` 경로 → 실제 `STATIC_ROOT`, `MEDIA_ROOT` 경로 (끝 슬래시 유지)

> `.env`는 이 저장소에 없다(시크릿). `.env.example`을 복사해 채우고, **프로덕션은 반드시 `DEBUG=False`** + `ALLOWED_HOSTS`에 서버 IP 포함.

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

## 3. Nginx

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

## 4. 검증

```bash
# Gunicorn 살아있는지
sudo systemctl status gunicorn --no-pager

# 소켓이 tester:www-data, 0770 (srwxrwx---) 인지 — 502의 핵심
ls -l /run/gunicorn/gunicorn.sock

# Nginx 문법
sudo nginx -t

# 실제 응답 (비로그인은 302 → /accounts/login/ 이 정상)
curl -I http://192.168.32.74/

# 정적 파일이 Nginx로 직접 나오는지 (200 + Content-Type: text/css 등)
curl -I http://192.168.32.74/static/admin/css/base.css
```

로그:
```bash
sudo journalctl -u gunicorn -n 50 --no-pager   # 앱 에러/트레이스백
sudo tail -f /var/log/nginx/error.log          # 프록시/정적 서빙 에러
```

---

## 5. 자주 나는 에러와 원인

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
