from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class OwnerOnlyMixin(LoginRequiredMixin):
    """본인이 작성한 객체만 접근 허용. 남의 것이면 403.

    뷰마다 소유자 if 문을 반복하지 않기 위해 get_object 단계에서 한 번에 검사한다.
    LoginRequiredMixin을 상속하므로 비로그인은 먼저 로그인 페이지로 보내진다.
    """

    owner_field = 'user'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if getattr(obj, self.owner_field) != self.request.user:
            raise PermissionDenied
        return obj
