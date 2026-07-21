from datetime import datetime

from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from menus.models import Menu
from menus.pagination import page_window
from .models import MealRecord
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

HISTORY_PAGE_SIZE = 15

@login_required
def history_view(request):
    from records import services as record_services
    records = MealRecord.objects.filter(user=request.user).select_related('menu').order_by('-created_at')
    page_obj = Paginator(records, HISTORY_PAGE_SIZE).get_page(request.GET.get('page'))
    return render(request, 'records/history.html', {
        'page_obj': page_obj,
        'records': page_obj,  # 템플릿 호환(현재 페이지 항목 순회)
        'food_candidates': record_services.food_name_candidates(request.user),
        **page_window(page_obj),
    })


@login_required
def food_stats_view(request):
    """음식별 섭취 통계 전체보기 페이지. food_count_stats 전체를 막대그래프로."""
    from records import services as record_services
    stats = record_services.food_count_stats(request.user)  # limit 없음 = 전체
    return render(request, 'records/food_stats.html', {
        'food_stats': stats,
        'food_stats_max': stats[0]['count'] if stats else 0,
        'total_records': MealRecord.objects.filter(user=request.user).count(),
    })


@login_required
def check_food(request):
    """입력한 음식이름과 비슷한 기존 이름을 되물어주는 근사매칭(AJAX, 모달용).

    GET name → {'suggestion': '돈카츠', 'menu_id': 12} 또는 {'suggestion': None}.
    """
    from records import services as record_services
    typed = request.GET.get('name', '').strip()
    candidates = record_services.food_name_candidates(request.user)
    names = [c['name'] for c in candidates]
    suggestion = record_services.similar_food_name(typed, names)
    menu_id = None
    if suggestion:
        # 제안된 이름이 카탈로그 메뉴면 menu_id도 함께 넘겨 바로 링크되게 한다.
        menu_id = next((c['menu_id'] for c in candidates if c['name'] == suggestion), None)
    return JsonResponse({'suggestion': suggestion, 'menu_id': menu_id})


@login_required
def create_record(request):
    if request.method == 'POST':
        meal_type = request.POST.get('meal_type')
        food_name = request.POST.get('food_name', '').strip()
        rating = request.POST.get('rating', 5)
        comment = request.POST.get('comment', '').strip()
        record_date = request.POST.get('record_date')
        menu_id = request.POST.get('menu_id')

        # 카탈로그 연결 결정(서버가 최종 정규화 — 클라 값 그대로 믿지 않음):
        # 1) 콤보박스에서 메뉴를 골라 menu_id가 오면 그 Menu로.
        # 2) 아니어도 입력 문자열이 Menu.name과 정확히 일치하면 자동 링크.
        menu = None
        if menu_id:
            menu = Menu.objects.filter(pk=menu_id).first()
        if menu is None and food_name:
            menu = Menu.objects.filter(name__iexact=food_name).first()
        if menu is not None:
            food_name = menu.name  # 표기 스냅샷을 카탈로그 이름으로 고정

        if food_name:
            # 1. 먼저 현재 시간 기준으로 기록을 생성합니다.
            record = MealRecord.objects.create(
                user=request.user,
                meal_type=meal_type,
                menu=menu,
                food_name=food_name,
                rating=int(rating),
                comment=comment
            )

            # 2. 폼에서 넘어온 날짜가 있으면 그 날짜 낮 12시(로컬)로 덮어쓴다.
            #    naive 문자열을 그대로 넣으면 시간대 경고/오차가 나므로 aware datetime으로.
            if record_date:
                try:
                    aware = timezone.make_aware(
                        datetime.strptime(record_date, '%Y-%m-%d').replace(hour=12)
                    )
                    MealRecord.objects.filter(pk=record.pk).update(created_at=aware)
                except (ValueError, TypeError):
                    pass  # 잘못된 날짜 형식이면 생성 시각(현재) 그대로 둔다

        # 3. 등록 완료 후 식사 히스토리가 아닌 메인 대시보드로 돌아갑니다.
        return redirect('menus:dashboard')
        
    return redirect('accounts:profile')

@login_required
@require_POST
def delete_record(request, pk):
    record = get_object_or_404(MealRecord, pk=pk, user=request.user)
    record.delete()
    return redirect('records:history')