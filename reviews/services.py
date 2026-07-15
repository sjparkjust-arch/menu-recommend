"""후기 조회 로직. 뷰(목록/메뉴 상세)에서 공통으로 쓴다.

정렬/집계/좋아요 매칭 같은 쿼리를 여기 모아 뷰를 얇게 유지한다.
"""

from django.db.models import Count

from reviews.models import Review, ReviewLike

SORT_LATEST = 'latest'
SORT_LIKES = 'likes'


def review_queryset(sort=SORT_LATEST):
    """후기 목록용. 좋아요 수를 annotate 하고 정렬한다."""
    qs = (
        Review.objects
        .select_related('user', 'menu')
        .annotate(like_count=Count('likes'))
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
