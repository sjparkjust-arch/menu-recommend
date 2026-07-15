from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.index, name='index'),                          # 시험용 인덱스 확인용 나중에 주석처리 또는 삭제 예정
    path('login/', views.login_view, name='login'),               # 로그인 화면
    path('signup/', views.signup_view, name='signup'),            # 회원가입 화면
    path('find-id/', views.find_id, name='find_id'),         # 아이디 찾기 화면
    path('find-pw/', views.find_pw, name='find_pw'),   # 비밀번호 찾기 화면
    path('logout/', views.logout_view, name='logout'), 
    path('profile/', views.profile, name='profile'),
    path('delete-confirm/', views.delete_account_confirm, name='delete_confirm'),
    path('delete-account/', views.delete_account, name='delete_account'),
]
