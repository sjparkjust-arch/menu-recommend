from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, UpdateView
from django.db.models import Q, Count  # 검색과 정렬을 위해 추가
from reviews.forms import ReviewForm, ReviewGeneralForm


from menus.models import Menu
from reviews import services
from reviews.forms import ReviewForm
from reviews.mixins import OwnerOnlyMixin
# ReviewLike는 삭제하고 Review만 임포트합니다!
from reviews.models import Review

PAGE_SIZE = 10

# ---------------------------------------------------------
# 1. 리뷰 게시판 리스트 (말머리 필터, 검색, 정렬 포함)
# ---------------------------------------------------------
def review_list(request):
    """후기 목록. 말머리/최신순/좋아요순 정렬 + 검색 기능"""
    category = request.GET.get('category', '')
    q = request.GET.get('q', '')
    sort = request.GET.get('sort', 'latest')

    # 기본 데이터: 좋아요 갯수(like_count)를 미리 계산해서 가져옴
    reviews = Review.objects.annotate(like_count=Count('likes'))

    # 말머리 필터 적용
    if category:
        reviews = reviews.filter(category=category)

    # 검색 기능 (제목이나 내용에 검색어가 포함된 경우)
    if q:
        reviews = reviews.filter(
            Q(title__icontains=q) | Q(content__icontains=q)
        )

    # 정렬 기능
    if sort == 'likes':
        reviews = reviews.order_by('-like_count', '-created_at')
    else:
        reviews = reviews.order_by('-created_at')

    context = {
        'reviews': reviews,
        'current_category': category,
        'q': q,
        'sort': sort,
    }
    return render(request, 'reviews/review_list.html', context)


# ---------------------------------------------------------
# 2. 리뷰 작성, 수정, 삭제 뷰
# ---------------------------------------------------------
class ReviewCreateView(LoginRequiredMixin, CreateView):
    """후기 작성. 로그인 필수."""
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
        # 기획 2번: 글 작성 후 메뉴 상세가 아닌 '리뷰 게시판'으로 이동!
        return reverse('reviews:list')


class ReviewUpdateView(OwnerOnlyMixin, UpdateView):
    """후기 수정. 본인 글만."""
    model = Review
    form_class = ReviewForm
    template_name = 'reviews/review_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['menu'] = self.object.menu
        return ctx

    def get_success_url(self):
        # 수정 후 '리뷰 게시판'으로 이동
        return reverse('reviews:list')


class ReviewDeleteView(OwnerOnlyMixin, DeleteView):
    """후기 삭제. 본인 글만."""
    model = Review
    http_method_names = ['post']

    def get_success_url(self):
        # 삭제 후 '리뷰 게시판'으로 이동
        return reverse('reviews:list')


# ---------------------------------------------------------
# 3. 좋아요 기능 (새로운 M2M 방식 적용)
# ---------------------------------------------------------
@login_required
@require_POST
def like_toggle(request, pk):
    """좋아요 토글(AJAX). ReviewLike 모델 대신 likes 필드 직접 사용."""
    review = get_object_or_404(Review, pk=pk)
    
    # 로그인한 유저가 이미 이 리뷰에 좋아요를 눌렀는지 확인
    if request.user in review.likes.all():
        review.likes.remove(request.user)  # 눌렀다면 취소
        liked = False
    else:
        review.likes.add(request.user)     # 안 눌렀다면 추가
        liked = True
        
    return JsonResponse({
        'liked': liked,
        'like_count': review.likes.count(),
    })
    
class ReviewCreateGeneralView(LoginRequiredMixin, CreateView):
    """후기 게시판에서 바로 작성. (메뉴를 직접 선택)"""
    model = Review
    form_class = ReviewGeneralForm
    template_name = 'reviews/review_form.html'

    def form_valid(self, form):
        form.instance.user = self.request.user
        # 메뉴는 유저가 폼에서 직접 선택하므로 별도로 지정하지 않아도 됩니다.
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('reviews:list')