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
    # 게임 3종(돌림판/사다리타기/이상형월드컵) — 결과 저장 없는 순수 클라이언트 게임
    path('menus/games/', views.games_hub, name='games'),
    path('menus/games/roulette/', views.game_roulette, name='game_roulette'),
    path('menus/games/ladder/', views.game_ladder, name='game_ladder'),
    path('menus/games/worldcup/', views.game_worldcup, name='game_worldcup'),
]
