from django.contrib.auth import views as auth_views
from django.urls import path

app_name = 'accounts'

# 'accounts/' 프리픽스로 마운트된다. 회원가입/프로필 등은 이후 추가.
urlpatterns = [
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='accounts/login.html'),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
