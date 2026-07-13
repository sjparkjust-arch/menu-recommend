"""config 프로젝트 URL 설정 (최종본 — 앞으로 수정하지 않음).

각 앱의 라우팅은 해당 앱의 urls.py에서 관리한다. 여기서는 마운트 지점만 고정한다.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),

    # 루트는 menus 앱으로 위임 — 메인 대시보드는 menus/urls.py 의 '' 경로에 둔다.
    path('', include('menus.urls')),
    path('accounts/', include('accounts.urls')),
    path('records/', include('records.urls')),
    path('reviews/', include('reviews.urls')),
]

# 개발용 미디어 파일 서빙. 운영에서는 웹서버/스토리지가 담당한다(CLAUDE.md 절대원칙 2, 4).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
