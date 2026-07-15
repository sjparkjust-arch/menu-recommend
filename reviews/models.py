from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    """메뉴 리뷰."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    menu = models.ForeignKey(
        'menus.Menu',
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    rating = models.PositiveSmallIntegerField(
        '평점',
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    content = models.TextField('내용', blank=True)
    # 저장 백엔드는 django-storages가 담당한다(CLAUDE.md 절대원칙 2). 경로 하드코딩 금지.
    image = models.ImageField('이미지', upload_to='reviews/', blank=True)
    created_at = models.DateTimeField('작성일', auto_now_add=True)
    # 편의 접근자. 실제 행은 ReviewLike through 모델이 관리한다.
    liked_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='ReviewLike',
        related_name='liked_reviews',
        blank=True,
    )

    class Meta:
        verbose_name = '리뷰'
        verbose_name_plural = '리뷰'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} · {self.menu} · {self.rating}점'


class ReviewLike(models.Model):
    """User ↔ Review (M:N). 리뷰 좋아요."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_likes',
    )
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='likes',
    )

    class Meta:
        verbose_name = '리뷰 좋아요'
        verbose_name_plural = '리뷰 좋아요'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'review'],
                name='uniq_user_review_like',
            ),
        ]

    def __str__(self):
        return f'{self.user} ♥ {self.review_id}'
