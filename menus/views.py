from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from menus.models import Cuisine, Menu, MenuLike
from menus.pagination import page_window
from menus.services import catalog
from menus.services.recommender import recommend_dashboard
from records import services as record_services
from reviews import services as review_services

PAGE_SIZE = 12
RANKING_LIMIT = 10
MY_BOBPICK_LIMIT = 10
FOOD_STATS_LIMIT = 5
POPULAR_RANK_LIMIT = 3
REC_SLOTS = ('lunch', 'dinner', 'taste')  # 확률적이라 세션에 고정하는 슬롯
# 재추첨(AJAX) 가능한 슬롯의 카드 제목/색상 variant (lunch/dinner는 끼니 구분 없는 일반 추천)
SLOT_META = {
    'lunch': ('🍽️ 오늘의 추천', 'lunch'),
    'dinner': ('🎲 또 다른 추천', 'dinner'),
    'taste': ('🎯 당신의 취향을 담은', 'taste'),
}


def _resolve_recs(request, cuisine_ids, reroll_set):
    """세션(Redis)에 고정된 추천 핀을 읽고/갱신해 최종 추천 dict를 반환.

    dashboard()와 reroll_slot()이 공유한다. 필터 시그니처가 바뀌면 핀을 버린다.
    """
    filter_sig = ','.join(str(c) for c in sorted(cuisine_ids))
    stored = request.session.get('rec_picks') or {}
    if stored.get('sig') == filter_sig:
        pinned = {s: stored[s] for s in REC_SLOTS if stored.get(s)}
    else:
        pinned = {}
    recs = recommend_dashboard(request.user, cuisine_ids=cuisine_ids or None,
                               pinned=pinned, reroll=reroll_set)
    request.session['rec_picks'] = {
        'sig': filter_sig,
        **{s: (recs[s].id if recs[s] else None) for s in REC_SLOTS},
    }
    return recs

def dashboard(request):
    """메인 대시보드. 비로그인도 열람 가능(알러지 필터·최근 기록은 로그인 사용자에게만).

    추천 로직은 recommender.recommend_dashboard() 에만 있다(CLAUDE.md 코드 스타일).
    점심/저녁/오늘의BEST/지금인기/당신의취향 5카드 + 하단 실시간 인기 순위.
    점심/저녁/취향은 세션(Redis)에 고정 → 새로고침해도 유지, ?reroll=<slot> 이나
    국가별 필터 변경 시에만 재추첨.
    """
    cuisine_ids = _as_int_list(request.GET.getlist('cuisine'))
    reroll = request.GET.get('reroll')
    reroll_set = {reroll} if reroll in REC_SLOTS else set()

    # 세션 핀을 읽고/갱신해 추천 확정(로직은 _resolve_recs에 공유).
    recs = _resolve_recs(request, cuisine_ids, reroll_set)

    # 리롤 버튼이 현재 필터를 유지하도록 querystring 조각.
    cuisine_qs = ''.join(f'&cuisine={c}' for c in cuisine_ids)

    # 리롤은 1회성: 세션에 새 결과를 저장한 뒤 reroll 파라미터를 뺀 깨끗한 URL로
    # 리다이렉트한다(PRG). 안 그러면 리롤 후 새로고침 때마다 계속 재추첨된다.
    if reroll_set:
        clean = reverse('menus:dashboard')
        if cuisine_ids:
            clean += '?' + '&'.join(f'cuisine={c}' for c in cuisine_ids)
        return redirect(clean)

    popular_ranking = catalog.recent_popular_menus(limit=POPULAR_RANK_LIMIT)
    # 순위 옆에 그 메뉴의 대표 후기(좋아요 top3 중 랜덤 1개) 붙이기
    review_samples = review_services.sample_reviews_for_menus([m.id for m in popular_ranking])
    for m in popular_ranking:
        m.sample_review = review_samples.get(m.id)

    # '지금 인기' 카드 자리를 대체할 음식 후기 카드용(일간/주간 탭)
    food_reviews = review_services.recent_food_reviews()

    if request.user.is_authenticated:
        my_bobpick = list(catalog.liked_menus(request.user, limit=MY_BOBPICK_LIMIT))
        # 찜한 메뉴 랜덤픽(클라 JS)용 직렬화 리스트
        my_bobpick_json = [{'id': m.id, 'name': m.name} for m in my_bobpick]
        food_stats = record_services.food_count_stats(request.user, limit=FOOD_STATS_LIMIT)
        # 막대 그래프 폭 계산용 최댓값
        food_stats_max = food_stats[0]['count'] if food_stats else 0
        meal_calendar = record_services.meal_calendar(
            request.user,
            year=_as_int_or_none(request.GET.get('cal_year')),
            month=_as_int_or_none(request.GET.get('cal_month')),
        )
        food_candidates = record_services.food_name_candidates(request.user)
        # MY밥픽 개인 요약: 활동 수치 + 선호 요리종류 top3
        my_likes_count = request.user.menu_likes.count()
        my_records_count = request.user.meal_records.count()
        my_reviews_count = request.user.reviews.count()
        my_top_cuisines = [
            p.cuisine for p in
            request.user.preferences.select_related('cuisine').order_by('-score')[:3]
        ]
    else:
        my_bobpick = None
        my_bobpick_json = []
        food_stats = None
        food_stats_max = 0
        meal_calendar = None
        food_candidates = None
        my_likes_count = my_records_count = my_reviews_count = 0
        my_top_cuisines = None

    context = {
        'recs': recs,
        'cuisines': Cuisine.objects.all(),
        'selected_cuisines': cuisine_ids,
        'cuisine_qs': cuisine_qs,
        'popular_ranking': popular_ranking,
        'food_reviews': food_reviews,
        'meal_calendar': meal_calendar,
        'my_bobpick': my_bobpick,
        'my_bobpick_json': my_bobpick_json,
        'food_stats': food_stats,
        'food_stats_max': food_stats_max,
        'food_candidates': food_candidates,
        'my_likes_count': my_likes_count,
        'my_records_count': my_records_count,
        'my_reviews_count': my_reviews_count,
        'my_top_cuisines': my_top_cuisines,
    }
    return render(request, 'menus/dashboard.html', context)


def reroll_slot(request):
    """추천 카드 1개만 재추첨하고 그 카드 partial HTML을 JSON으로 반환(AJAX).

    페이지 전체 새로고침 없이 카드만 교체하기 위한 엔드포인트 — 링크 이동이 아니라
    fetch로 호출되므로 화면이 상단으로 튀지 않는다. JS가 꺼져 있으면 카드의
    a[href]('?reroll=<slot>') 폴백이 그대로 동작한다(기존 PRG 경로).
    """
    slot = request.GET.get('slot')
    if slot not in SLOT_META:
        return JsonResponse({'error': 'invalid slot'}, status=400)
    cuisine_ids = _as_int_list(request.GET.getlist('cuisine'))
    recs = _resolve_recs(request, cuisine_ids, {slot})
    head, variant = SLOT_META[slot]
    cuisine_qs = ''.join(f'&cuisine={c}' for c in cuisine_ids)
    html = render_to_string('menus/_rec_card.html', {
        'menu': recs[slot],
        'head': head,
        'variant': variant,
        'reroll_url': f'?reroll={slot}{cuisine_qs}',
    }, request=request)
    return JsonResponse({'html': html})


def menu_list(request):
    """메뉴 목록. cuisine 다중 필터 + 이름 검색 + 12개 페이지네이션.

    '메인' 코스만 보여준다(사이드 제외). 쿼리 로직은 catalog 서비스에 있다.
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
        **page_window(page_obj),  # 페이지 번호 10개씩 그룹 노출
    }
    return render(request, 'menus/menu_list.html', context)


@login_required
def liked_menus_view(request):
    """찜한(좋아요한) 메뉴 전체보기 — 페이지 넘기며 열람."""
    qs = catalog.liked_menus(request.user)
    page_obj = Paginator(qs, PAGE_SIZE).get_page(request.GET.get('page'))
    return render(request, 'menus/liked_menus.html', {
        'page_obj': page_obj,
        **page_window(page_obj),
    })


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
        # 좋아요 실제 행은 MenuLike(through)에 있다. menu.likes(자동 M2M)가 아니라
        # menu_likes(MenuLike 역참조)로 세야 토글이 쓴 값과 일치한다.
        'like_count': menu.menu_likes.count(),
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