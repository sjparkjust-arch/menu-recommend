from django.urls import path

from . import views

app_name = 'reviews'

# 'reviews/' 프리픽스로 마운트된다.
urlpatterns = [
    path('', views.ReviewListView.as_view(), name='list'),
    path('create/<int:menu_pk>/', views.ReviewCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', views.ReviewUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.ReviewDeleteView.as_view(), name='delete'),
    path('<int:pk>/like/', views.like_toggle, name='like'),
]
