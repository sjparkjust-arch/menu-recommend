from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from menus.models import Cuisine, Menu, MenuLike
from menus.services import catalog
from menus.services.recommender import recommend_dashboard
from records import services as record_services
from reviews import services as review_services

PAGE_SIZE = 12
RANKING_LIMIT = 10
RANKING_PREVIEW_LIMIT = 3
MY_BOBPICK_LIMIT = 10
FOOD_STATS_LIMIT = 5


def dashboard(request):
    """메인 대시보드. 비로그인도 열람 가능(알러지 필터·최근 기록은 로그인 사용자에게만).

    추천 로직은 recommender.recommend_dashboard() 에만 있다(CLAUDE.md 코드 스타일).
    점심랜덤/저녁랜덤 + 오늘의BEST/지금인기/당신의취향 5개 카드를 보여준다.
    """
    recs = recommend_dashboard(request.user)

    if request.user.is_authenticated:
        my_bobpick = catalog.liked_menus(request.user, limit=MY_BOBPICK_LIMIT)
        food_stats = record_services.food_count_stats(request.user, limit=FOOD_STATS_LIMIT)
        # 막대 그래프 폭 계산용 최댓값
        food_stats_max = food_stats[0]['count'] if food_stats else 0
        meal_calendar = record_services.meal_calendar(
            request.user,
            year=_as_int_or_none(request.GET.get('cal_year')),
            month=_as_int_or_none(request.GET.get('cal_month')),
        )
    else:
        my_bobpick = None
        food_stats = None
        food_stats_max = 0
        meal_calendar = None

    ranking_preview = catalog.ranking_queryset(limit=RANKING_PREVIEW_LIMIT, period='week')

    context = {
        'recs': recs,
        'meal_calendar': meal_calendar,
        'my_bobpick': my_bobpick,
        'ranking_preview': ranking_preview,
        'food_stats': food_stats,
        'food_stats_max': food_stats_max,
    }
    return render(request, 'menus/dashboard.html', context)


def menu_list(request):
    """메뉴 목록. cuisine 다중 필터 + 이름 검색 + 12개 페이지네이션.

    '메인' 코스만 보여준다(사이드/디저트/음료 제외). 쿼리 로직은 catalog 서비스에 있다.
    비로그인도 열람 가능하며, 알러지 경고는 로그인 사용자에게만 표시한다(숨기지 않음).
    """
    cuisine_ids = _as_int_list(request.GET.getlist('cuisine'))
    search = request.GET.get('q', '').strip()

    qs = catalog.menu_list_queryset(
        cuisine_ids=cuisine_ids or None,
        search=search or None,
        main_only=True,
    )
    page_obj = Paginator(qs, PAGE_SIZE).get_page(request.GET.get('page'))

    # 현재 페이지 카드들 중 사용자 알러지에 걸리는 것 / 좋아요한 것 표시용
    allergy_hits = catalog.allergy_hit_menu_ids(request.user, page_obj.object_list)
    liked_menu_ids = catalog.liked_menu_ids(request.user, page_obj.object_list)

    context = {
        'page_obj': page_obj,
        'cuisines': Cuisine.objects.all(),
        'selected_cuisines': cuisine_ids,
        'search': search,
        'allergy_hits': allergy_hits,
        'liked_menu_ids': liked_menu_ids,
        'filter_querystring': _filter_querystring(request),
    }
    return render(request, 'menus/menu_list.html', context)


def ranking(request):
    """후기 평점 기준 메뉴 랭킹 Top N. 기간 탭(오늘/이번주/이번달/전체) 지원.

    쿼리 로직은 catalog.ranking_queryset()에 있다.
    """
    period = request.GET.get('period')
    if period not in catalog.RANKING_PERIODS:
        period = None
    menus = catalog.ranking_queryset(limit=RANKING_LIMIT, period=period)
    return render(request, 'menus/ranking.html', {'menus': menus, 'period': period})


def menu_detail(request, pk):
    """메뉴 상세. 정보/알러지 재료/평균 평점·후기 수 + 그 메뉴의 후기 목록."""
    menu = catalog.get_menu_with_stats(pk)
    reviews = review_services.reviews_for_menu(menu)
    review_services.record_reviews_viewed(request.user, reviews)
    context = {
        'menu': menu,
        'allergens': menu.allergens.all(),
        'overlap_allergens': catalog.overlapping_allergens(request.user, menu),
        'reviews': reviews,
        'liked_ids': review_services.liked_review_ids(request.user, reviews),
        'menu_liked': menu.pk in catalog.liked_menu_ids(request.user, [menu]),
    }
    return render(request, 'menus/menu_detail.html', context)


@login_required
@require_POST
def menu_like_toggle(request, pk):
    """메뉴 좋아요 토글(AJAX). 눌렀으면 취소, 안 눌렀으면 추가. JSON 반환."""
    menu = get_object_or_404(Menu, pk=pk)
    like, created = MenuLike.objects.get_or_create(user=request.user, menu=menu)
    if not created:
        like.delete()
    return JsonResponse({
        'liked': created,
        'like_count': menu.likes.count(),
    })


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


def _as_int_or_none(value):
    """쿼리 파라미터(문자열)를 int로. 없거나 잘못된 값이면 None."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
