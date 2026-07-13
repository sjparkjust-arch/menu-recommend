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
