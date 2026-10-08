# 밥픽(BobPick) · 메뉴 추천 웹 서비스

> 같은 Django 서비스를 **온프레미스 → AWS(Terraform) → Amazon EKS(GitOps)** 세 단계로 옮기며 인프라를 발전시킨 2인 팀 프로젝트입니다.
> 이 저장소에는 애플리케이션 코드, 컨테이너 이미지, 이미지 빌드 CI가 있습니다.

| 저장소 | 내용 | 단계 |
|---|---|---|
| **menu-recommend** (현재) | Django 앱, Dockerfile, 이미지 빌드 CI | 1·2·3차 |
| [bobpick-infra](https://github.com/sjparkjust-arch/bobpick-infra) | Terraform 인프라 코드 (`main`: 2차 EC2·ASG / `3rd/eks-han`: 3차 EKS) | 2·3차 |
| [bobpick-manifests](https://github.com/sjparkjust-arch/bobpick-manifests) | 쿠버네티스 매니페스트(Kustomize), Argo CD 배포 대상 | 3차 |

<br>

## 프로젝트 한눈에 보기

| 단계 | 기간 | 환경 | 핵심 |
|---|---|---|---|
| 1차 | 2026.07.13 ~ 08.19 | 온프레미스 (Ubuntu VM 2대) | Nginx·Gunicorn·Django / MariaDB·Redis 계층 분리, HTTPS |
| 2차 | 2026.08.20 ~ 09.15 | AWS EC2 + Auto Scaling | Terraform IaC, 2개 AZ, ALB·WAF·HTTPS, RDS Multi-AZ, 부하테스트 |
| 3차 | 2026.09.14 ~ 10.07 | Amazon EKS | 컨테이너화, GitOps(Argo CD), HPA + Cluster Autoscaler, 단계별 부하테스트 |

> 프로젝트 종료 후 AWS 리소스를 모두 삭제해, 서비스 도메인(bobpick.cloud)은 현재 접속되지 않습니다.

### 단계별로 바뀐 것

| | 1차 온프레미스 | 2차 AWS EC2 | 3차 EKS |
|---|---|---|---|
| 배포 | 서버에 접속해 수동 반영 | GitHub Actions → Bastion 경유 SSH, 서버마다 순차 배포 | Git 커밋 → Argo CD 롤링 업데이트 |
| 확장 | 불가 (서버 2대 고정) | 서버 2~4대, 증설에 4~6분 | 파드 2~10개(30~80초), 노드 8~12대 |
| DB 마이그레이션 | 수동 | 서버마다 실행 | Job으로 파드 수와 관계없이 1회 |
| 배포 자격 증명 | 없음 | 장기 액세스 키 | OIDC 임시 자격 증명 |
| 비밀 값 | 서버의 `.env` | 서버 이미지(AMI) 안의 `.env` | Secrets Manager + External Secrets Operator |

<br>

## 팀 구성과 역할

| 단계 | 박상준 ([@sjparkjust-arch](https://github.com/sjparkjust-arch)) | 최한빈 ([@cheobonggi](https://github.com/cheobonggi)) |
|---|---|---|
| 1차 | 추천 알고리즘, 시드 데이터 스크립트, UI, 서버 물리 분리(DB 이관) | 회원 인증, 후기 게시판, 식사 기록 |
| 2차 | **인프라**: VPC·NAT·보안 그룹, ALB·WAF·HTTPS, Terraform CI, 계정 이관, 부하테스트 | **앱 배포**: RDS·Redis·ASG, S3·CloudFront, 앱 배포 파이프라인 |
| 3차 | **컨테이너·배포 자동화**: Dockerfile, 매니페스트, 이미지 CI, Argo CD, HPA, 부하테스트 | **클라우드 인프라**: EKS, IRSA, ALB Controller, ESO, Cluster Autoscaler, 모니터링 |

1차의 서버 환경 구축과 장애 대응은 함께 했고, 2차와 3차는 인프라와 배포 역할을 서로 바꿔 맡았습니다.

<br>

## 3차 최종 구조

- **요청**: 사용자 → Route 53 → ALB(Ingress가 생성, HTTPS) → 앱 파드 2~10개(HPA) → RDS MySQL(Multi-AZ) · ElastiCache Redis
- **정적 파일**: CloudFront → S3 (migrate Job이 배포 시 업로드)
- **확장**: 파드가 들어갈 자리가 부족하면 Cluster Autoscaler가 노드를 8대에서 최대 12대까지 확장
- **비밀 값**: Secrets Manager → External Secrets Operator → 쿠버네티스 Secret
- **배포**: `main` push → GitHub Actions(OIDC) → ECR → bobpick-manifests 이미지 태그 커밋 → Argo CD 동기화 → 롤링 업데이트

<br>

## 이 저장소의 구성

```
menu-recommend/
├── accounts/ menus/ records/ reviews/   # Django 앱 (회원, 메뉴·추천, 식사 기록, 후기)
├── config/                              # 설정: DB·Redis·S3 값을 환경변수로 주입
├── deploy/                              # 1차 온프레미스 배포 설정 (Gunicorn systemd, Nginx)
├── docs/                                # 1차 구축 과정과 트러블슈팅 기록
├── Dockerfile                           # 3차 컨테이너 이미지
├── docker-compose.yml                   # 로컬 검증 (앱 + MariaDB 10.11 + Redis 7)
└── .github/workflows/deploy.yml         # 3차 이미지 빌드 → ECR → 매니페스트 태그 갱신
```

### 서비스 기능

- **오늘의 메뉴 추천**: 점심·저녁·오늘의 BEST·인기·취향 5개 카드를 서로 겹치지 않게 추천. 알러지와 최근 먹은 메뉴는 항상 제외하고, 취향 카드는 입맛이 비슷한 사용자의 평가를 반영 (`menus/services/recommender.py`)
- 메뉴 목록·상세·랭킹, 좋아요
- 후기 게시판(카테고리, 검색), 최근 본 후기
- 식사 기록 달력과 섭취 통계
- 메뉴 고르기 게임(월드컵, 룰렛, 사다리)

### 운영을 위해 앱에 넣은 것

| 항목 | 내용 |
|---|---|
| `/healthz/` | DB 연결만 확인하는 가벼운 헬스체크, 실패 시 503 반환. 쿠버네티스 프로브용 (3차) |
| `/metrics` | django-prometheus로 요청 수·응답 시간 지표 노출 (3차) |
| 환경변수 설정 | django-environ으로 DB·Redis·S3 값을 코드 밖에서 주입 |
| Redis 세션 | 세션을 Redis에 저장해, 서버가 여러 대여도 로그인 상태 유지 |
| S3 저장소 | 정적·미디어 파일을 S3(+CloudFront)로 분리해, 서버를 늘려도 파일이 한곳에 있게 함 |
| HTTPS 설정 | 프록시(Nginx·ALB) 뒤에서 HTTPS 인식, HSTS 헤더 |

<br>

## 컨테이너 이미지와 CI (3차)

**Dockerfile**
- `python:3.12-slim-bookworm` 기반, MySQL 클라이언트 포함
- 파드에 할당한 CPU 0.5코어에 맞춰 Gunicorn 워커 2개, 8000번 포트
- `collectstatic`은 이미지 빌드에서 빼고 클러스터의 migrate Job에서 실행해, 빌드 단계에 AWS 권한이 필요 없게 함

**`.github/workflows/deploy.yml`**
1. `main` 브랜치에 push
2. GitHub OIDC로 IAM 역할의 임시 자격 증명을 받음 (GitHub에 장기 액세스 키를 저장하지 않음)
3. 이미지를 빌드해 커밋 SHA 7자리 태그로 ECR에 푸시
4. `bobpick-manifests`의 이미지 태그를 `kustomize edit set image`로 바꿔 자동 커밋
5. Argo CD가 변경을 감지해 클러스터에 롤링 방식으로 반영

이미지 태그가 커밋 SHA라서, 클러스터에서 돌고 있는 버전이 어떤 코드인지 바로 찾을 수 있습니다. 태그 갱신 단계는 ECR 로그인 단계의 레지스트리 주소를 재사용해, 계정이 바뀌어도 고칠 곳을 줄였습니다.

이미지는 클러스터에 올리기 전에 `docker-compose.yml`로 앱·MariaDB 10.11·Redis 7을 함께 띄워 로컬에서 먼저 검증했습니다.

<br>

## 문서

| 문서 | 내용 |
|---|---|
| [docs/troubleshooting.md](docs/troubleshooting.md) | 1차 구축 중 겪은 문제 (증상 · 원인 · 해결) |
| [docs/data-migration-procedure.md](docs/data-migration-procedure.md) | DB 서버를 다른 머신으로 옮기는 절차 |
| [docs/deployment-walkthrough.md](docs/deployment-walkthrough.md) | runserver → Gunicorn → Nginx → HTTPS 단계별 기록 |
| [deploy/README.md](deploy/README.md) | 1차 Gunicorn·Nginx 설정 방법 |
| [bobpick-infra/docs](https://github.com/sjparkjust-arch/bobpick-infra/tree/main/docs) | 2차 계정 이관·부하테스트 기록 |
| [bobpick-manifests](https://github.com/sjparkjust-arch/bobpick-manifests) | 3차 매니페스트 설계와 부하테스트 결과 |
