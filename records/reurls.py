from django.urls import path
from . import views

app_name = 'records'

urlpatterns = [
    path('history/', views.history_view, name='history'),
    path('check/', views.check_food, name='check_food'),  # 음식이름 근사매칭(AJAX)
    path('create/', views.create_record, name='create'),
    path('<int:pk>/delete/', views.delete_record, name='delete'),
]