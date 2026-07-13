from django.urls import path

from . import views

app_name = 'menus'

urlpatterns = [
    # 루트('')로 마운트된다. 메인 대시보드.
    path('', views.dashboard, name='dashboard'),
]
