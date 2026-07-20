from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from menus.models import Menu
from reviews import services
from reviews.forms import ReviewForm
from reviews.mixins import OwnerOnlyMixin
from reviews.models import Review, ReviewLike

PAGE_SIZE = 10


class ReviewListView(ListView):
    """후기 목록. 최신순/좋아요순 정렬 + 페이지네이션."""

    template_name = 'reviews/review_list.html'
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        return services.review_queryset(self._sort(), search=self._search())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['sort'] = self._sort()
        ctx['search'] = self._search()
        ctx['liked_ids'] = services.liked_review_ids(
            self.request.user, ctx['page_obj'].object_list
        )
        services.record_reviews_viewed(self.request.user, ctx['page_obj'].object_list)
        return ctx

    def _sort(self):
        sort = self.request.GET.get('sort')
        return services.SORT_LIKES if sort == services.SORT_LIKES else services.SORT_LATEST

    def _search(self):
        return self.request.GET.get('q', '').strip()


class ReviewCreateView(LoginRequiredMixin, CreateView):
    """후기 작성. 로그인 필수. 같은 메뉴에 여러 개 작성 가능(제약 없음)."""

    model = Review
    form_class = ReviewForm
    template_name = 'reviews/review_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.menu = get_object_or_404(Menu, pk=kwargs['menu_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.menu = self.menu
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['menu'] = self.menu
        return ctx

    def get_success_url(self):
        return reverse('menus:detail', args=[self.menu.pk])


class ReviewUpdateView(OwnerOnlyMixin, UpdateView):
    """후기 수정. 본인 글만(아니면 403)."""

    model = Review
    form_class = ReviewForm
    template_name = 'reviews/review_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['menu'] = self.object.menu
        return ctx

    def get_success_url(self):
        return reverse('menus:detail', args=[self.object.menu_id])


class ReviewDeleteView(OwnerOnlyMixin, DeleteView):
    """후기 삭제. 본인 글만(아니면 403). 확인 모달에서 POST로 호출."""

    model = Review
    http_method_names = ['post']

    def get_success_url(self):
        return reverse('menus:detail', args=[self.object.menu_id])


@login_required
@require_POST
def like_toggle(request, pk):
    """좋아요 토글(AJAX). 눌렀으면 취소, 안 눌렀으면 추가. JSON 반환."""
    review = get_object_or_404(Review, pk=pk)
    like, created = ReviewLike.objects.get_or_create(user=request.user, review=review)
    if not created:
        like.delete()
    return JsonResponse({
        'liked': created,
        'like_count': review.likes.count(),
    })
