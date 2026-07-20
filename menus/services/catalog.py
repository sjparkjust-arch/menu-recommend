"""메뉴 목록/상세용 쿼리 로직.

뷰에는 비즈니스 로직을 넣지 않는다(CLAUDE.md 코드 스타일).
필터/검색/평점 집계/알러지 매칭 같은 쿼리는 전부 이 모듈에 모은다.
"""

from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from menus.models import Menu, MenuAllergy, MenuLike

RANKING_PERIODS = {'today', 'week', 'month'}
# 실시간 인기 순위: 최근 이 시간 내 좋아요만 집계(없으면 전체로 폴백).
POPULAR_RECENT_HOURS = 6


def recent_popular_menus(limit=5, hours=POPULAR_RECENT_HOURS):
    """실시간 인기 순위: 최근 hours시간 내 좋아요를 우선 반영하되 목록은 항상 채운다.

    정렬 = (최근 좋아요 수 desc → 전체 좋아요 수 desc → 이름). 최근에 눌린 메뉴가 위로 뜨고,
    최근 활동이 적어도 전체 인기로 채워 top limit개를 유지한다. 표시는 전체 좋아요 수(like_count).
    데이터 그대로 반영(새로고침 안정적, 좋아요 생기면 순위에 반영).
    """
    since = timezone.now() - timedelta(hours=hours)
    recent = dict(
        MenuLike.objects
        .filter(menu__course__name='메인', created_at__gte=since)
        .values('menu_id').annotate(c=Count('id')).values_list('menu_id', 'c')
    )
    total = dict(
        MenuLike.objects
        .filter(menu__course__name='메인')
        .values('menu_id').annotate(c=Count('id')).values_list('menu_id', 'c')
    )
    if not total:
        return []
    menus = {m.id: m for m in Menu.objects.filter(id__in=list(total)).select_related('cuisine')}
    ordered_ids = sorted(
        total,
        key=lambda mid: (-recent.get(mid, 0), -total[mid], menus[mid].name),
    )[:limit]
    result = []
    for mid in ordered_ids:
        m = menus[mid]
        m.like_count = total[mid]  # 표시는 전체 좋아요 수
        result.append(m)
    return result


def menu_list_queryset(cuisine_ids=None, search=None, main_only=False):
    """목록 페이지용 메뉴 QuerySet.

    cuisine 다중 선택 필터 + 이름 검색을 적용하고,
    평균 평점/후기 수/좋아요 수를 annotate 한다. (카드 렌더용으로 관계도 미리 로드)
    main_only=True면 '메인' 코스만 (사이드 제외).
    """
    qs = (
        Menu.objects
        .select_related('cuisine', 'course')
        .prefetch_related('allergens')
    )
    if main_only:
        qs = qs.filter(course__name='메인')
    if cuisine_ids:
        qs = qs.filter(cuisine_id__in=cuisine_ids)
    if search:
        qs = qs.filter(name__icontains=search)
    return qs.annotate(
        avg_rating=Avg('reviews__rating'),
        review_count=Count('reviews', distinct=True),
        like_count=Count('likes', distinct=True),
    ).order_by('name')


def ranking_queryset(limit=10, period=None):
    """후기 평점 기준 랭킹. '메인' 코스 + 후기 1개 이상인 메뉴만, 평균 평점 -> 후기 수 순 정렬.

    period: None(전체 기간) | 'today' | 'week' | 'month'.
    지정하면 그 기간에 작성된 후기만 집계 대상으로 삼는다(다른 메뉴 정보에는 영향 없음).
    """
    review_filter = Q()
    since = _period_start(period)
    if since:
        review_filter = Q(reviews__created_at__gte=since)
    return (
        Menu.objects
        .filter(course__name='메인')
        .select_related('cuisine', 'course')
        .annotate(
            avg_rating=Avg('reviews__rating', filter=review_filter),
            review_count=Count('reviews', filter=review_filter, distinct=True),
        )
        .filter(review_count__gt=0)
        .order_by('-avg_rating', '-review_count', 'name')[:limit]
    )


def _period_start(period):
    """랭킹 기간 필터의 시작 시각. period가 없거나 잘못된 값이면 None(전체 기간)."""
    if period not in RANKING_PERIODS:
        return None
    now = timezone.now()
    if period == 'today':
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == 'week':
        return now - timedelta(days=7)
    return now - timedelta(days=30)  # 'month'


def get_menu_with_stats(pk):
    """상세 페이지용 단건 조회. 평균 평점/후기 수/좋아요 수 포함. 없으면 404."""
    qs = (
        Menu.objects
        .select_related('cuisine', 'course')
        .prefetch_related('allergens')
        .annotate(
            avg_rating=Avg('reviews__rating'),
            review_count=Count('reviews', distinct=True),
            like_count=Count('likes', distinct=True),
        )
    )
    return get_object_or_404(qs, pk=pk)


def user_allergy_ids(user):
    """로그인 사용자의 알러지 id 집합. 비로그인/없음이면 빈 set."""
    if not user.is_authenticated:
        return set()
    return set(user.allergies.values_list('id', flat=True))


def allergy_hit_menu_ids(user, menus):
    """주어진 메뉴들 중 user의 알러지에 걸리는 menu id 집합.

    목록 카드에 경고를 표시하기 위한 것. 메뉴를 숨기지는 않는다(표시만).
    페이지당 12개에 대해서만 조회하므로 쿼리 1번으로 끝난다.
    """
    allergy_ids = user_allergy_ids(user)
    if not allergy_ids:
        return set()
    menu_ids = [m.pk for m in menus]
    if not menu_ids:
        return set()
    return set(
        MenuAllergy.objects
        .filter(menu_id__in=menu_ids, allergy_id__in=allergy_ids)
        .values_list('menu_id', flat=True)
    )


def liked_menu_ids(user, menus):
    """주어진 메뉴들 중 user가 좋아요한 menu id 집합. 좋아요 버튼 상태 표시용."""
    if not user.is_authenticated:
        return set()
    menu_ids = [m.pk for m in menus]
    if not menu_ids:
        return set()
    return set(
        MenuLike.objects
        .filter(user=user, menu_id__in=menu_ids)
        .values_list('menu_id', flat=True)
    )


def liked_menus(user, limit=None):
    """user가 좋아요한 메뉴 목록(MY밥픽). 최근 좋아요 순. 비로그인이면 빈 QuerySet."""
    if not user.is_authenticated:
        return Menu.objects.none()
    qs = (
        Menu.objects
        .filter(menu_likes__user=user)  # 수정됨: likes -> menu_likes
        .select_related('cuisine', 'course')
        .order_by('-menu_likes__created_at')  # 수정됨: likes -> menu_likes
    )
    return qs[:limit] if limit else qs

def overlapping_allergens(user, menu):
    """상세 페이지에서, menu의 알러지 재료 중 user의 알러지와 겹치는 것들의 리스트."""
    allergy_ids = user_allergy_ids(user)
    if not allergy_ids:
        return []
    # allergens 는 prefetch 되어 있으므로 추가 쿼리 없음.
    return [a for a in menu.allergens.all() if a.id in allergy_ids]
