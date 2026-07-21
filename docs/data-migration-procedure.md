# 데이터 이전(DB 마이그레이션) 절차

> DB 서버를 다른 머신으로 옮길 때의 **재현 가능한 절차**. 2026-07-21 서버 물리 분리(Server2 `.73 → .78`)에서 실제 수행한 순서를 그대로 남긴다.
> **2단계 AWS 이전(RDS)에서 같은 절차를 재사용**할 수 있게 각 명령의 이유까지 적는다.
> 관련 사고 기록: `docs/troubleshooting.md` 2026-07-21 세 항목(마이그레이션 이력 불일치 / IP 변경 연쇄 / GRANT 1133).

---

## 전제

- 기준 DB: **실제 데이터가 쌓여 있던 기존 DB**(이번엔 옛 Server2). 데이터가 없는 쪽을 기준으로 삼지 않는다.
- 대상 DB: 새 DB 서버(이번엔 팀원 PC, `192.168.32.78`).
- 접속 계정: `menuuser`. **MariaDB 계정은 (아이디 + 접속 출발지 host) 한 세트**라, 웹서버(Server1 `.74`)에서 붙을 수 있게 `menuuser@192.168.32.74`가 대상 DB에 있어야 한다.

---

## 절차

### 1) 백업 — Server1에서 옛 DB에 원격 접속해 덤프
```bash
mysqldump -h [옛DB IP] -u menuuser -p \
  --single-transaction \
  --default-character-set=utf8mb4 \
  menudb > ~/menudb_backup.sql
```
- `--single-transaction` — 덤프 시작 시점의 **일관된 스냅샷**을 트랜잭션으로 확보한다. 테이블을 잠그지 않으므로 **덤프 중에도 서비스 중단이 없다**(InnoDB 기준). 이게 없으면 덤프 도중 바뀐 데이터가 섞여 시점이 흐트러질 수 있다.
- `--default-character-set=utf8mb4` — 덤프 과정의 문자셋을 utf8mb4로 고정해 **한글·이모지 깨짐을 방지**한다. 후기 내용·음식 이름 등에 한글/이모지가 있어 필수.

### 2) 대상 DB 초기화 — 새 DB 서버(팀원 PC)에서
```sql
DROP DATABASE menudb;
CREATE DATABASE menudb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON menudb.* TO 'menuuser'@'192.168.32.74';
FLUSH PRIVILEGES;
```
- **DROP 후 CREATE** — 대상에 옛 스키마·부분 데이터가 남아 있으면 복원과 충돌하므로 **깨끗한 상태에서 복원**한다.
- `CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci` **명시** — DB 기본 문자셋이 latin1 등으로 잡히면 복원 시 한글이 깨진다. 덤프(utf8mb4)와 대상 DB 문자셋을 **맞춰야** 안전하다.
- `GRANT ... TO 'menuuser'@'192.168.32.74'` — 웹서버(`.74`)에서 붙을 계정 권한. **계정이 없으면 먼저 `CREATE USER`**(GRANT는 계정을 자동 생성하지 않음 → 없으면 `ERROR 1133`, troubleshooting 참고).

### 3) 복원 — Server1에서 새 DB로
```bash
mysql -h 192.168.32.78 -u menuuser -p menudb < ~/menudb_backup.sql
```

### 4) 검증 (반드시 순서대로)
```sql
SHOW TABLES;                          -- → 23개
SELECT COUNT(*) FROM menus_menu;      -- → 199
SELECT COUNT(*) FROM accounts_user;   -- → 59
```
```bash
python manage.py showmigrations       # 이력 일치 확인
```
- 마지막으로 **브라우저에서 실제 화면**(로그인·메뉴·후기·좋아요)까지 확인한다.
- 검증 순서: **[데이터 무결성(건수/테이블) → 스키마 → 마이그레이션 이력 → 실제 화면]**. 이 순서로 좁혀 들어가야 문제가 어느 계층인지 빨리 갈린다.
- ⚠️ `showmigrations`가 미적용으로 보여도 **스키마가 이미 맞으면 `--fake`로 기록만 맞춘다.** 단, `SHOW COLUMNS`로 컬럼 일치를 **먼저 확인한 뒤에만** 쓴다(무작정 `--fake`는 더 찾기 어려운 드리프트를 만든다 → troubleshooting 2026-07-21 항목1).

---

## 보존 원칙

- **백업 파일(`menudb_backup.sql`)과 원본 VM은 검증이 완전히 끝날 때까지 보존한다.** 복원·검증 중 문제가 생기면 되돌릴 수 있어야 한다.
- 검증 완료 전에는 원본을 삭제·초기화하지 않는다.

---

## 2단계: AWS RDS로 옮길 때 재사용

같은 절차를 거의 그대로 쓰되, 온프레미스 고유 부분만 바꾼다.

| 온프레미스(이번) | AWS RDS 대응 |
|---|---|
| `-h 192.168.32.78` (사설 IP) | `-h <RDS 엔드포인트>` (IP가 아니라 고정 엔드포인트) |
| `menuuser@192.168.32.74` (host=클라이언트 IP) | RDS는 host 대신 **보안 그룹(Security Group)** 으로 접근 허용 |
| ufw로 3306 허용 | RDS **보안 그룹 인바운드 규칙**으로 3306 허용 |
| 대상 DB에서 DROP/CREATE | RDS 인스턴스 생성 후 동일 문자셋으로 DB 생성 |

- **핵심 이점**: RDS는 **엔드포인트(고정 주소)** 로 접근하므로, 이번처럼 IP가 바뀔 때마다 5개 계층을 다시 만지는 문제가 사라진다(troubleshooting 2026-07-21 항목2가 AWS 이전의 명분).
- 덤프 옵션(`--single-transaction`, `--default-character-set=utf8mb4`)과 검증 순서·보존 원칙은 **그대로** 적용한다.
