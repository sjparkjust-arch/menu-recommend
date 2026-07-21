from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('', views.ReviewListView.as_view(), name='review_list'),
    path('recent/', views.recent_viewed, name='recent_viewed'),  # 최근 본 후기 전체보기
    # 1. 메뉴 번호 없이 게시판 전체에서 바로 글을 쓰는 경로 추가
    path('write/', views.ReviewCreateGeneralView.as_view(), name='review_create_general'),
    
    path('menu/<int:menu_pk>/write/', views.ReviewCreateView.as_view(), name='review_create'),
    path('<int:pk>/update/', views.ReviewUpdateView.as_view(), name='review_update'),
    path('<int:pk>/delete/', views.ReviewDeleteView.as_view(), name='review_delete'),
    path('<int:pk>/like/', views.like_toggle, name='like_toggle'),
]