from django.conf import settings
from django.db import models
from django.conf import settings


class Cuisine(models.Model):
    """요리 종류 (한식, 중식, 일식, 양식 …). 테이블로 관리해 확장 가능."""

    name = models.CharField('종류', max_length=50, unique=True)

    class Meta:
        verbose_name = '요리 종류'
        verbose_name_plural = '요리 종류'
        ordering = ['name']

    def __str__(self):
        return self.name


class Course(models.Model):
    """코스 구분 (메인, 사이드). 디저트·음료는 서비스에서 제외."""

    name = models.CharField('코스', max_length=50, unique=True)

    class Meta:
        verbose_name = '코스'
        verbose_name_plural = '코스'
        ordering = ['name']

    def __str__(self):
        return self.name


class Menu(models.Model):
    """메뉴."""

    class MealTime(models.TextChoices):
        LUNCH = 'lunch', '점심'
        DINNER = 'dinner', '저녁'
        ANY = 'any', '무관'

    name = models.CharField('이름', max_length=100)
    cuisine = models.ForeignKey(
        Cuisine,
        on_delete=models.PROTECT,
        related_name='menus',
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name='menus',
    )
    # 저장 백엔드는 django-storages가 담당한다(CLAUDE.md 절대원칙 2). 경로 하드코딩 금지.
    image = models.ImageField('이미지', upload_to='menus/', blank=True)
    description = models.TextField('설명', blank=True)
    meal_time = models.CharField(
        '식사 시간',
        max_length=10,
        choices=MealTime.choices,
        default=MealTime.ANY,
    )
    # 편의 접근자. 실제 행은 MenuAllergy through 모델이 관리한다.
    allergens = models.ManyToManyField(
        'accounts.Allergy',
        through='MenuAllergy',
        related_name='menus',
        blank=True,
    )

    # ── [새로 추가된 좋아요 필드] ──
    # 유저 한 명이 여러 메뉴에 좋아요를 누를 수 있고, 메뉴 하나도 여러 유저로부터 좋아요를 받을 수 있으므로 ManyToMany로 선언합니다.
    likes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='liked_menus',
        blank=True,
        verbose_name='좋아요 한 사용자들'
    )

    class Meta:
        verbose_name = '메뉴'
        verbose_name_plural = '메뉴'
        ordering = ['name']

    def __str__(self):
        return self.name


class MenuAllergy(models.Model):
    """Menu ↔ Allergy (M:N). 이 메뉴가 포함하는 알러지 유발 재료."""

    menu = models.ForeignKey(
        Menu,
        on_delete=models.CASCADE,
        related_name='menu_allergies',
    )
    allergy = models.ForeignKey(
        'accounts.Allergy',
        on_delete=models.CASCADE,
        related_name='allergy_menus',
    )

    class Meta:
        verbose_name = '메뉴 알러지'
        verbose_name_plural = '메뉴 알러지'
        constraints = [
            models.UniqueConstraint(
                fields=['menu', 'allergy'],
                name='uniq_menu_allergy',
            ),
        ]

    def __str__(self):
        return f'{self.menu} - {self.allergy}'


class MenuLike(models.Model):
    """User ↔ Menu (M:N). 사용자가 좋아요한 메뉴."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='menu_likes',
    )
    menu = models.ForeignKey(
        Menu,
        on_delete=models.CASCADE,
        related_name='menu_likes',
    )
    created_at = models.DateTimeField('좋아요한 시각', auto_now_add=True)

    class Meta:
        verbose_name = '메뉴 좋아요'
        verbose_name_plural = '메뉴 좋아요'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'menu'],
                name='uniq_user_menu_like',
            ),
        ]

    def __str__(self):
        return f'{self.user} ♥ {self.menu}'
