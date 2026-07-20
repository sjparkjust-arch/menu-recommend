"""식사 기록 통계 로직. 대시보드(간략)/마이페이지(상세)에서 공통으로 쓴다."""

import calendar as calendar_module
from collections import defaultdict
from datetime import datetime

from django.db.models import Count
from django.utils import timezone

from records.models import MealRecord


def food_count_stats(user, limit=None):
    """user가 각 음식(food_name)을 몇 번 먹었는지 집계. 많이 먹은 순으로 정렬."""
    qs = (
        MealRecord.objects
        .filter(user=user)
        .values('food_name')
        .annotate(count=Count('id'))
        .order_by('-count', 'food_name')
    )
    return list(qs[:limit]) if limit else list(qs)


def meal_calendar(user, year=None, month=None):
    """지정한 달의 달력 그리드 + 그 날짜에 먹은 음식들 (대시보드 '최근 먹은 음식' 달력용).

    year/month를 안 주면 이번 달. 일요일 시작 6주 그리드, 이번 달이 아닌 칸은 None.
    """
    now = timezone.localtime()
    year = year or now.year
    month = month or now.month

    # created_at__month/__date 는 MariaDB에서 CONVERT_TZ(=시간대 테이블 필요)를 써서
    # 시간대 테이블 미적재 시 NULL이 되어 아무것도 안 잡힌다. 그래서 로컬 기준 한 달
    # 구간을 datetime 범위(단순 비교)로 필터한다. (docs/troubleshooting.md 참고)
    month_start = timezone.make_aware(datetime(year, month, 1))
    if month == 12:
        month_end = timezone.make_aware(datetime(year + 1, 1, 1))
    else:
        month_end = timezone.make_aware(datetime(year, month + 1, 1))

    records = list(
        MealRecord.objects
        .filter(user=user, created_at__gte=month_start, created_at__lt=month_end)
        .order_by('created_at')
    )
    # 날짜(일)별 상세 기록 — 클릭 시 모달에 보여줄 용도(JSON 직렬화 가능한 dict).
    records_by_day = defaultdict(list)
    for r in records:
        day = timezone.localtime(r.created_at).day
        records_by_day[day].append({
            'food': r.food_name,
            'meal': r.get_meal_type_display(),
            'rating': r.rating,
        })

    cal = calendar_module.Calendar(firstweekday=6)  # 일요일 시작
    weeks = [
        [
            {'day': day, 'count': len(records_by_day.get(day, []))} if day else None
            for day in week
        ]
        for week in cal.monthdayscalendar(year, month)
    ]

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    return {
        'year': year,
        'month': month,
        'weeks': weeks,
        'records_by_day': dict(records_by_day),  # {일(int): [{food, meal, rating}]}
        'total': len(records),
        'today': now.date() if (now.year == year and now.month == month) else None,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
    }
