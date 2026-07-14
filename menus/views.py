from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from menus.models import Course, Cuisine, Menu
from menus.services import catalog
from menus.services.recommender import recommend

RECENT_LIMIT = 10
RECOMMEND_LIMIT = 3
PAGE_SIZE = 12


@login_required
def dashboard(request):
    """메인 대시보드.

    추천 로직은 recommender.recommend() 에만 있다(CLAUDE.md 코드 스타일).
    이 뷰는 요청 파라미터 파싱 → recommend() 호출 → 화면용 데이터 조회만 한다.
    """
    # 점심/저녁 토글. 유효하지 않으면 점심으로.
    meal_time = request.GET.get('meal', Menu.MealTime.LUNCH)
    if meal_time not in {Menu.MealTime.LUNCH, Menu.MealTime.DINNER}:
        meal_time = Menu.MealTime.LUNCH

    cuisine_ids = _as_int_list(request.GET.getlist('cuisine'))
    course_ids = _as_int_list(request.GET.getlist('course'))

    recommendations = recommend(
        request.user,
        meal_time,
        cuisine_ids=cuisine_ids or None,
        course_ids=course_ids or None,
        limit=RECOMMEND_LIMIT,
    )

    recent_records = (
        request.user.meal_records
        .select_related('menu')
        .order_by('-date')[:RECENT_LIMIT]
    )

    context = {
        'meal_time': meal_time,
        'meal_lunch': Menu.MealTime.LUNCH,
        'meal_dinner': Menu.MealTime.DINNER,
        'recommendations': recommendations,
        'cuisines': Cuisine.objects.all(),
        'courses': Course.objects.all(),
        'selected_cuisines': cuisine_ids,
        'selected_courses': course_ids,
        'recent_records': recent_records,
        'allergies': request.user.allergies.all(),
    }
    return render(request, 'menus/dashboard.html', context)


def menu_list(request):
    """메뉴 목록. cuisine/course 다중 필터 + 이름 검색 + 12개 페이지네이션.

    쿼리 로직은 catalog 서비스에 있다. 이 뷰는 파라미터 파싱/페이지네이션만 담당.
    비로그인도 열람 가능하며, 알러지 경고는 로그인 사용자에게만 표시한다(숨기지 않음).
    """
    cuisine_ids = _as_int_list(request.GET.getlist('cuisine'))
    course_ids = _as_int_list(request.GET.getlist('course'))
    search = request.GET.get('q', '').strip()

    qs = catalog.menu_list_queryset(
        cuisine_ids=cuisine_ids or None,
        course_ids=course_ids or None,
        search=search or None,
    )
    page_obj = Paginator(qs, PAGE_SIZE).get_page(request.GET.get('page'))

    # 현재 페이지 카드들 중 사용자 알러지에 걸리는 것 표시용
    allergy_hits = catalog.allergy_hit_menu_ids(request.user, page_obj.object_list)

    context = {
        'page_obj': page_obj,
        'cuisines': Cuisine.objects.all(),
        'courses': Course.objects.all(),
        'selected_cuisines': cuisine_ids,
        'selected_courses': course_ids,
        'search': search,
        'allergy_hits': allergy_hits,
        'filter_querystring': _filter_querystring(request),
    }
    return render(request, 'menus/menu_list.html', context)


def menu_detail(request, pk):
    """메뉴 상세. 정보/알러지 재료/평균 평점·후기 수, 후기 목록(자리만)."""
    menu = catalog.get_menu_with_stats(pk)
    context = {
        'menu': menu,
        'allergens': menu.allergens.all(),
        'overlap_allergens': catalog.overlapping_allergens(request.user, menu),
    }
    return render(request, 'menus/menu_detail.html', context)


def _filter_querystring(request):
    """페이지네이션 링크에 붙일, page를 제외한 현재 필터 쿼리스트링."""
    params = request.GET.copy()
    params.pop('page', None)
    encoded = params.urlencode()
    return f'&{encoded}' if encoded else ''


def _as_int_list(values):
    """쿼리 파라미터(문자열 리스트)를 int 리스트로. 잘못된 값은 무시."""
    result = []
    for value in values:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return result
