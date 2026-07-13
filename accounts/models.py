from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """커스텀 User 모델.

    첫 마이그레이션 전에 AUTH_USER_MODEL로 등록해야 한다(CLAUDE.md 절대원칙 6).
    지금은 AbstractUser를 그대로 상속만 해두고, 이후 프로필/알러지 등
    도메인 필드를 이 모델(또는 연결 모델)에 확장한다.
    """

    pass
