from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from menus.models import Course, Cuisine, Menu
from menus.services.recommender import recommend

RECENT_LIMIT = 10
RECOMMEND_LIMIT = 3


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


def _as_int_list(values):
    """쿼리 파라미터(문자열 리스트)를 int 리스트로. 잘못된 값은 무시."""
    result = []
    for value in values:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return result
