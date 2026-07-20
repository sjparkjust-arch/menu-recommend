from django.urls import path

from . import views

app_name = 'menus'

urlpatterns = [
    # 루트('')로 마운트된다. 메인 대시보드.
    path('', views.dashboard, name='dashboard'),
    path('menus/', views.menu_list, name='list'),
    path('menus/ranking/', views.ranking, name='ranking'),
    path('menus/<int:pk>/', views.menu_detail, name='detail'),
    path('menus/<int:pk>/like/', views.menu_like_toggle, name='like'),
]
