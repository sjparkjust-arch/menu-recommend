from django.urls import path

from . import views

app_name = 'menus'

urlpatterns = [
    # 루트('')로 마운트된다. 메인 대시보드.
    path('', views.dashboard, name='dashboard'),
    path('reroll/', views.reroll_slot, name='reroll'),  # 추천 카드 1개 재추첨(AJAX)
    path('menus/', views.menu_list, name='list'),
    path('menus/liked/', views.liked_menus_view, name='liked'),  # 찜한 메뉴 전체보기
    path('menus/ranking/', views.ranking, name='ranking'),
    path('menus/<int:pk>/', views.menu_detail, name='detail'),
    path('menus/<int:pk>/like/', views.menu_like_toggle, name='like'),
]
