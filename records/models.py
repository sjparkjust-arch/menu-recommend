from django.db import models
from django.conf import settings

class MealRecord(models.Model):
    MEAL_CHOICES = [
        ('BREAKFAST', '아침'),
        ('LUNCH', '점심'),
        ('DINNER', '저녁'),
        ('SNACK', '간식'),
    ]

    # settings.AUTH_USER_MODEL을 사용하여 커스텀 유저와 완벽히 매핑
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='meal_records')
    meal_type = models.CharField(max_length=10, choices=MEAL_CHOICES, default='LUNCH')
    # 카탈로그 메뉴로 고른 경우 실제 Menu와 연결(표기 통일 + 추천 이름매칭 정확도).
    # 카탈로그 밖 음식(집밥·라면 등)은 menu=None, food_name 자유 문자열만 저장.
    # 메뉴가 지워져도 기록은 남기고 food_name 스냅샷으로 표시하므로 SET_NULL.
    menu = models.ForeignKey(
        'menus.Menu',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meal_records',
    )
    # 표시/집계용 스냅샷 문자열. menu가 있으면 menu.name과 같게 저장한다.
    food_name = models.CharField(max_length=100)
    rating = models.IntegerField(default=5)  # 별점 또는 숟가락 개수 (1~5)
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)  # 기록한 날짜 시간 자동 저장

    class Meta:
        ordering = ['-created_at']  # 최근에 먹은 음식이 먼저 나오도록 정렬

    def __str__(self):
        return f"{self.user.username} - {self.get_meal_type_display()}: {self.food_name}"