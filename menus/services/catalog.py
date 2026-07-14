"""메뉴 목록/상세용 쿼리 로직.

뷰에는 비즈니스 로직을 넣지 않는다(CLAUDE.md 코드 스타일).
필터/검색/평점 집계/알러지 매칭 같은 쿼리는 전부 이 모듈에 모은다.
"""

from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404

from menus.models import Menu, MenuAllergy


def menu_list_queryset(cuisine_ids=None, course_ids=None, search=None):
    """목록 페이지용 메뉴 QuerySet.

    cuisine/course 다중 선택 필터 + 이름 검색을 적용하고,
    평균 평점/후기 수를 annotate 한다. (카드 렌더용으로 관계도 미리 로드)
    """
    qs = (
        Menu.objects
        .select_related('cuisine', 'course')
        .prefetch_related('allergens')
    )
    if cuisine_ids:
        qs = qs.filter(cuisine_id__in=cuisine_ids)
    if course_ids:
        qs = qs.filter(course_id__in=course_ids)
    if search:
        qs = qs.filter(name__icontains=search)
    return qs.annotate(
        avg_rating=Avg('reviews__rating'),
        review_count=Count('reviews', distinct=True),
    ).order_by('name')


def get_menu_with_stats(pk):
    """상세 페이지용 단건 조회. 평균 평점/후기 수 포함. 없으면 404."""
    qs = (
        Menu.objects
        .select_related('cuisine', 'course')
        .prefetch_related('allergens')
        .annotate(
            avg_rating=Avg('reviews__rating'),
            review_count=Count('reviews', distinct=True),
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


def overlapping_allergens(user, menu):
    """상세 페이지에서, menu의 알러지 재료 중 user의 알러지와 겹치는 것들의 리스트."""
    allergy_ids = user_allergy_ids(user)
    if not allergy_ids:
        return []
    # allergens 는 prefetch 되어 있으므로 추가 쿼리 없음.
    return [a for a in menu.allergens.all() if a.id in allergy_ids]
