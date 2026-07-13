# 프로젝트 규칙

## 개요
메뉴 추천 서비스. 2인 팀 포트폴리오.
1단계 온프레미스 -> 2단계 AWS 이전 -> 3단계 컨테이너 확장.

## 인프라 구성
- Server1 (192.168.32.74): Nginx + Gunicorn + Django
- Server2 (192.168.32.73): MariaDB + Redis

## 절대 원칙 (2·3단계를 위해 반드시 지킬 것)
1. 상태를 앱 프로세스에 저장하지 않는다. 세션은 Redis.
2. 업로드 파일 경로를 하드코딩하지 않는다. django-storages 사용.
3. 모든 설정값(DB, Redis, 시크릿)은 환경변수. settings.py에 하드코딩 금지.
4. 웹서버 / 앱 / DB 계층 분리 유지.
5. 알러지는 사용자가 끌 수 없는 하드 제외 조건. 필터 UI에 넣지 않는다.
6. 커스텀 User 모델(AbstractUser)을 첫 마이그레이션 전에 반드시 적용한다.

## 기술 스택
Ubuntu 24.04, Nginx, Gunicorn, Django, MariaDB, Redis, Python venv

## 코드 스타일
- 추천 로직은 menus/services/recommender.py 에 분리
- 뷰에 비즈니스 로직을 넣지 않는다
