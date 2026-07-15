from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class User(AbstractUser):
    """커스텀 User 모델.

    첫 마이그레이션 전에 AUTH_USER_MODEL로 등록해야 한다(CLAUDE.md 절대원칙 6).
    알러지/선호도는 아래 연결 모델을 통해 접근한다.
    """

    # 편의 접근자. 실제 행은 UserAllergy through 모델이 관리한다.
    allergies = models.ManyToManyField(
        'Allergy',
        through='UserAllergy',
        related_name='users',
        blank=True,
    )


class Allergy(models.Model):
    """알러지 유발 재료 마스터 (갑각류, 견과류, 유제품, 계란, 밀, 대두 등).

    알러지는 사용자가 끌 수 없는 하드 제외 조건이다(CLAUDE.md 절대원칙 5).
    """

    name = models.CharField('알러지명', max_length=50, unique=True)

    class Meta:
        verbose_name = '알러지'
        verbose_name_plural = '알러지'
        ordering = ['name']

    def __str__(self):
        return self.name


class UserAllergy(models.Model):
    """User ↔ Allergy (M:N). 사용자가 가진 알러지."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_allergies',
    )
    allergy = models.ForeignKey(
        Allergy,
        on_delete=models.CASCADE,
        related_name='allergy_users',
    )

    class Meta:
        verbose_name = '사용자 알러지'
        verbose_name_plural = '사용자 알러지'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'allergy'],
                name='uniq_user_allergy',
            ),
        ]

    def __str__(self):
        return f'{self.user} - {self.allergy}'


class UserPreference(models.Model):
    """User ↔ Cuisine, 선호도 점수(1~5). 가입 시 선호도 조사 결과."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preferences',
    )
    cuisine = models.ForeignKey(
        'menus.Cuisine',
        on_delete=models.CASCADE,
        related_name='user_preferences',
    )
    score = models.PositiveSmallIntegerField(
        '선호도',
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )

    class Meta:
        verbose_name = '사용자 선호도'
        verbose_name_plural = '사용자 선호도'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'cuisine'],
                name='uniq_user_cuisine',
            ),
        ]

    def __str__(self):
        return f'{self.user} - {self.cuisine}: {self.score}'
