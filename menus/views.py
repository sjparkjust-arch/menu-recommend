from django.core.paginator import Paginator
from django.shortcuts import render

from menus.models import Course, Cuisine, Menu
from menus.services import catalog
from menus.services.recommender import recommend
from reviews import services as review_services
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from .models import Menu
import json

RECENT_LIMIT = 10
RECOMMEND_LIMIT = 3
PAGE_SIZE = 12


def dashboard(request):
    """메인 대시보드. 달력 데이터 포함."""
    cuisine_ids = _as_int_list(request.GET.getlist('cuisine'))
    course_ids = _as_int_list(request.GET.getlist('course'))

    # 점심 추천 1개 호출
    lunch_recommendations = recommend(
        request.user, Menu.MealTime.LUNCH,
        cuisine_ids=cuisine_ids or None, course_ids=course_ids or None, limit=1,
    )
    lunch_recommendation = lunch_recommendations[0] if lunch_recommendations else None

    # 중복 방지용 ID 추출
    excluded_menu_ids = [lunch_recommendation.id] if lunch_recommendation else []

    # 저녁 추천 호출
    dinner_recommendations_raw = recommend(
        request.user, Menu.MealTime.DINNER,
        cuisine_ids=cuisine_ids or None, course_ids=course_ids or None, limit=3,
    )

    dinner_recommendation = None
    for menu in dinner_recommendations_raw:
        if menu.id not in excluded_menu_ids:
            dinner_recommendation = menu
            break

    # 💡 달력 데이터를 담을 빈 문자열 기본값
    calendar_events_json = "[]" 

    if request.user.is_authenticated:
        recent_records = request.user.meal_records.order_by('-created_at')[:10]
        allergies = request.user.allergies.all()

        # 💡 [달력 데이터 변환 로직] 사용자가 기록한 모든 식사를 달력 포맷으로 변환
        all_records = request.user.meal_records.all()
        events = []
        for record in all_records:
            if record.meal_type == 'BREAKFAST':
                color = '#6FA3EF'
                display_title = '아침'
                sort_order = 1
            elif record.meal_type == 'LUNCH':
                color = '#E8623D'
                display_title = '점심'
                sort_order = 2
            elif record.meal_type == 'DINNER':
                color = '#2C2118'
                display_title = '저녁'
                sort_order = 3
            else:
                color = '#8C7E72'
                display_title = record.get_meal_type_display()
                sort_order = 4
                
            events.append({
                'title': display_title, 
                'start': record.created_at.strftime('%Y-%m-%d'), 
                'color': color,
                'textColor': 'white',
                'food_name': record.food_name,
                'sort_order': sort_order # 정렬용 숨김 데이터 추가
            })
        
        calendar_events_json = json.dumps(events)
    else:
        recent_records = None
        allergies = None

    context = {
        'lunch_recommendation': lunch_recommendation,
        'dinner_recommendation': dinner_recommendation,
        'cuisines': Cuisine.objects.all(),
        'courses': Course.objects.all(),
        'selected_cuisines': cuisine_ids,
        'selected_courses': course_ids,
        'recent_records': recent_records,
        'allergies': allergies,
        # 💡 HTML 템플릿으로 달력 JSON 데이터를 전송
        'calendar_events_json': calendar_events_json, 
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
    """메뉴 상세. 정보/알러지 재료/평균 평점·후기 수 + 그 메뉴의 후기 목록."""
    menu = catalog.get_menu_with_stats(pk)
    reviews = review_services.reviews_for_menu(menu)
    context = {
        'menu': menu,
        'allergens': menu.allergens.all(),
        'overlap_allergens': catalog.overlapping_allergens(request.user, menu),
        'reviews': reviews,
        'liked_ids': review_services.liked_review_ids(request.user, reviews),
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

@require_POST
def menu_like_toggle(request, pk):
    """메뉴 좋아요 토글 (AJAX 비동기 처리)"""
    # 1. 로그인 여부를 먼저 안전하게 검사합니다.
    if not request.user.is_authenticated:
        return JsonResponse({'error': '로그인이 필요합니다.'}, status=401)
        
    menu = get_object_or_404(Menu, pk=pk)
    
    # 2. 좋아요 토글 처리
    if request.user in menu.likes.all():
        menu.likes.remove(request.user)
        liked = False
    else:
        menu.likes.add(request.user)
        liked = True
        
    return JsonResponse({
        'liked': liked,
        'like_count': menu.likes.count(),
    })
