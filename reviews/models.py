from django.db import models
from django.conf import settings
from menus.models import Menu  # (주의) 실제 메뉴 모델 경로에 맞게 임포트하세요

class Review(models.Model):
    # 말머리(카테고리) 선택지 정의
    CATEGORY_CHOICES = (
        ('RESTAURANT', '맛집후기'),
        ('FOOD', '음식후기'),
    )
    
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name='reviews', verbose_name='메뉴')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='작성자')
    
    
    # 추가된 필드들 (제목, 말머리, 내용, 별점)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='FOOD', verbose_name='말머리')
    title = models.CharField(max_length=200, verbose_name='제목')
    content = models.TextField(verbose_name='내용')
    rating = models.IntegerField(default=5, verbose_name='별점')
    image = models.ImageField(upload_to='reviews/', blank=True, null=True, verbose_name='이미지')
    
    # 좋아요순 정렬을 위한 필드
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='liked_reviews', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}"