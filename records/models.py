from django.conf import settings
from django.db import models


class MealRecord(models.Model):
    """사용자가 특정 날짜/끼니에 먹은 메뉴 기록."""

    class Meal(models.TextChoices):
        LUNCH = 'lunch', '점심'
        DINNER = 'dinner', '저녁'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='meal_records',
    )
    menu = models.ForeignKey(
        'menus.Menu',
        on_delete=models.PROTECT,
        related_name='meal_records',
    )
    date = models.DateField('날짜')
    meal = models.CharField('끼니', max_length=10, choices=Meal.choices)

    class Meta:
        verbose_name = '식사 기록'
        verbose_name_plural = '식사 기록'
        ordering = ['-date']

    def __str__(self):
        return f'{self.user} · {self.date} {self.get_meal_display()} · {self.menu}'
