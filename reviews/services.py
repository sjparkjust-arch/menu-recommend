"""후기 조회 로직. 뷰(목록/메뉴 상세)에서 공통으로 쓴다.

정렬/집계/좋아요 매칭 같은 쿼리를 여기 모아 뷰를 얇게 유지한다.
"""

from django.db.models import Count, Q

from reviews.models import Review, ReviewLike, ReviewView

SORT_LATEST = 'latest'
SORT_LIKES = 'likes'


def review_queryset(sort=SORT_LATEST, search=None):
    """후기 목록용. 좋아요 수를 annotate 하고, 메뉴 이름/후기 내용으로 검색한 뒤 정렬한다."""
    qs = (
        Review.objects
        .select_related('user', 'menu')
        .annotate(like_count=Count('likes'))
    )
    if search:
        qs = qs.filter(
            Q(content__icontains=search) | Q(menu__name__icontains=search)
        )
    if sort == SORT_LIKES:
        return qs.order_by('-like_count', '-created_at')
    return qs.order_by('-created_at')


def reviews_for_menu(menu):
    """특정 메뉴의 후기(최신순, 좋아요 수 포함). 메뉴 상세 페이지용."""
    return (
        Review.objects
        .filter(menu=menu)
        .select_related('user')
        .annotate(like_count=Count('likes'))
        .order_by('-created_at')
    )


def liked_review_ids(user, reviews):
    """reviews 중 user가 좋아요한 review id 집합. 버튼 상태 표시용."""
    if not user.is_authenticated:
        return set()
    review_ids = [r.pk for r in reviews]
    if not review_ids:
        return set()
    return set(
        ReviewLike.objects
        .filter(user=user, review_id__in=review_ids)
        .values_list('review_id', flat=True)
    )


def record_reviews_viewed(user, reviews):
    """user가 페이지에서 실제로 본 다른 사람 후기를 "최근 본 후기"에 기록한다.

    본인이 쓴 후기는 "본 것"으로 치지 않는다(내가 조회한 "다른 사람" 후기).
    이미 본 후기면 viewed_at만 갱신된다(auto_now).
    """
    if not user.is_authenticated:
        return
    for review in reviews:
        if review.user_id == user.id:
            continue
        ReviewView.objects.update_or_create(user=user, review=review)


def recently_viewed_reviews(user, limit=10):
    """user가 최근 조회한 다른 사람 후기 목록(마이페이지용). 최신 조회순."""
    if not user.is_authenticated:
        return Review.objects.none()
    return (
        Review.objects
        .filter(views__user=user)
        .select_related('user', 'menu')
        .annotate(like_count=Count('likes'))
        .order_by('-views__viewed_at')[:limit]
    )
