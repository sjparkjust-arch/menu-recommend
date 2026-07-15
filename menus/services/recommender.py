"""메뉴 추천 로직.

뷰에는 비즈니스 로직을 넣지 않는다(CLAUDE.md 코드 스타일). 추천은 이 모듈에서만.

파이프라인:
    1. 사용자 알러지 포함 메뉴 무조건 제외 (하드 필터, CLAUDE.md 절대원칙 5)
    2. 최근 7일 내 먹은 메뉴 제외
    3. meal_time 필터 (해당 끼니 + '무관')
    4. cuisine_ids / course_ids 필터 (지정된 경우만)
    5. 남은 후보에 UserPreference 점수로 가중치를 줘 확률적으로 상위 limit개 추출
"""

import logging
import random
from datetime import timedelta

from django.utils import timezone

from menus.models import Menu

logger = logging.getLogger(__name__)

# 알러지는 사용자가 끌 수 없는 하드 제외 조건이라 필터 인자로 받지 않는다(절대원칙 5).
RECENT_DAYS = 7
# 선호도 조사 결과가 없는 요리 종류에 부여할 중립 가중치(척도 1~5의 중앙값).
NEUTRAL_SCORE = 3


def recommend(user, meal_time, cuisine_ids=None, course_ids=None, limit=3):
    """user에게 메뉴를 추천한다.

    Args:
        user: 추천 대상 User 인스턴스.
        meal_time: 이번 끼니 (Menu.MealTime 값, 예: 'lunch' / 'dinner').
        cuisine_ids: 선택. 이 요리 종류들로만 후보를 좁힌다.
        course_ids: 선택. 이 코스들로만 후보를 좁힌다.
        limit: 추천 개수.

    Returns:
        list[Menu]: 최대 limit개. 후보가 없으면 빈 리스트.
    """
    qs = Menu.objects.all()
    total = qs.count()

    # 1. 알러지 하드 필터 --------------------------------------------------
    allergy_ids = list(user.allergies.values_list('id', flat=True))
    if allergy_ids:
        qs = qs.exclude(menu_allergies__allergy_id__in=allergy_ids)
    after_allergy = qs.count()
    logger.info(
        '[recommend] user=%s 알러지 필터: %d개 제외 (알러지 %d종) -> %d개',
        user.pk, total - after_allergy, len(allergy_ids), after_allergy,
    )

    # 2. 최근 7일 내 먹은 메뉴 제외 ----------------------------------------
    # records.MealRecord는 menus.Menu를 FK로 참조하지 않고 food_name을 자유
    # 텍스트로 저장한다. 따라서 이름 일치로 근사한다(오타·표기 차이는 놓칠 수 있음).
    since = timezone.now() - timedelta(days=RECENT_DAYS)
    recent_food_names = list(
        user.meal_records.filter(created_at__gte=since)
        .values_list('food_name', flat=True)
    )
    if recent_food_names:
        qs = qs.exclude(name__in=recent_food_names)
    after_recent = qs.count()
    logger.info(
        '[recommend] 최근 %d일 중복 필터: %d개 제외 -> %d개',
        RECENT_DAYS, after_allergy - after_recent, after_recent,
    )

    # 3. meal_time 필터 (해당 끼니 + 무관) ---------------------------------
    qs = qs.filter(meal_time__in=[meal_time, Menu.MealTime.ANY])
    after_mealtime = qs.count()
    logger.info(
        '[recommend] meal_time=%s 필터: %d개 제외 -> %d개',
        meal_time, after_recent - after_mealtime, after_mealtime,
    )

    # 4. cuisine / course 필터 (지정 시에만) -------------------------------
    if cuisine_ids:
        qs = qs.filter(cuisine_id__in=cuisine_ids)
    if course_ids:
        qs = qs.filter(course_id__in=course_ids)
    after_filter = qs.count()
    logger.info(
        '[recommend] cuisine/course 필터(cuisine=%s, course=%s): %d개 제외 -> %d개',
        cuisine_ids, course_ids, after_mealtime - after_filter, after_filter,
    )

    candidates = list(qs.select_related('cuisine', 'course'))

    # 후보 0개 처리 --------------------------------------------------------
    if not candidates:
        logger.warning(
            '[recommend] user=%s 후보 0개 — 추천할 메뉴가 없음 '
            '(meal_time=%s, cuisine=%s, course=%s)',
            user.pk, meal_time, cuisine_ids, course_ids,
        )
        return []

    # 5. 선호도 가중 확률 추출 ---------------------------------------------
    scores = dict(
        user.preferences.values_list('cuisine_id', 'score')
    )
    weighted = [
        (menu, scores.get(menu.cuisine_id, NEUTRAL_SCORE))
        for menu in candidates
    ]
    picked = _weighted_sample(weighted, limit)
    logger.info(
        '[recommend] user=%s 후보 %d개에서 %d개 추천: %s',
        user.pk, len(candidates), len(picked),
        [m.name for m in picked],
    )
    return picked


def _weighted_sample(weighted_items, k):
    """가중치 비복원 추출 (Efraimidis-Spirakis A-Res).

    각 항목에 key = U^(1/weight) (U는 0~1 균등난수)를 부여하고 key가 큰 순으로
    상위 k개를 뽑는다. weight가 클수록(선호도 높을수록) 뽑힐 확률이 커진다.
    """
    keyed = []
    for item, weight in weighted_items:
        weight = max(float(weight), 1e-6)
        key = random.random() ** (1.0 / weight)
        keyed.append((key, item))
    keyed.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in keyed[:k]]
