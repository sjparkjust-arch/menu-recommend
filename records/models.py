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
    food_name = models.CharField(max_length=100)
    rating = models.IntegerField(default=5)  # 별점 또는 숟가락 개수 (1~5)
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)  # 기록한 날짜 시간 자동 저장

    class Meta:
        ordering = ['-created_at']  # 최근에 먹은 음식이 먼저 나오도록 정렬

    def __str__(self):
        return f"{self.user.username} - {self.get_meal_type_display()}: {self.food_name}"