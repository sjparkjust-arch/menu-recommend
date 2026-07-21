from django.urls import path
from . import views

app_name = 'records'

urlpatterns = [
    path('history/', views.history_view, name='history'),
    path('stats/', views.food_stats_view, name='food_stats'),  # 음식 통계 전체보기
    path('check/', views.check_food, name='check_food'),  # 음식이름 근사매칭(AJAX)
    path('create/', views.create_record, name='create'),
    path('<int:pk>/delete/', views.delete_record, name='delete'),
]