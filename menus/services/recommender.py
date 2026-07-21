"""메뉴 추천 로직.

뷰에는 비즈니스 로직을 넣지 않는다(CLAUDE.md 코드 스타일). 추천은 이 모듈에서만.

recommend_dashboard()는 대시보드에 보여줄 5개 카드를 서로 다른 방식으로 각 1개씩 뽑는다:
    1. 오늘의 추천      — 전체 메뉴 중 무작위 (끼니 구분 없음)
    2. 또 다른 추천     — 전체 메뉴 중 무작위 (1번과 중복 없음)
    3. 오늘의 BEST     — 평균 평점이 높은(잘 검증된) 메뉴
    4. 지금 인기 있는  — 좋아요가 많은 메뉴
    5. 당신의 취향을 담은 — 협업(나와 취향 겹치는 사용자) + 요리종류 선호도 개인화

모두 '메인' 코스만 대상으로 하고, 하드 제외(알러지·최근 먹은 메뉴·이미 좋아요)는 항상 적용한다.
알러지는 사용자가 끌 수 없는 하드 제외 조건이다(CLAUDE.md 절대원칙 5).
5개 카드끼리는 같은 메뉴가 중복되지 않게 뽑는다.
"""

import logging
import random
from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone

from menus.models import Menu, MenuLike
from menus.services import catalog
from reviews.models import Review

logger = logging.getLogger(__name__)

RECENT_DAYS = 7
HIGH_RATING = 4  # 이 평점 이상이면 '고평점'으로 보고 협업 신호에 포함
MAIN_COURSE_NAME = '메인'
# '지금 인기 있는 메뉴'는 최근 이 시간 내 좋아요만 집계(실시간). 그 안에 없으면 전체 좋아요로 폴백.
POPULAR_HOURS = 6

# '당신의 취향' 카드 점수 가중치 (협업 > 선호).
W_COLLAB = 3.0
W_PREF = 1.0
BASE_WEIGHT = 0.05  # 신호가 0이어도 뽑히게 하는 최소 가중치


def recommend_dashboard(user, cuisine_ids=None, pinned=None, reroll=None):
    """대시보드용 5개 카드 추천. 각기 다른 방식, 서로 중복 없음.

    점심/저녁/취향(확률적)은 pinned(세션에 저장된 이전 선택)이 여전히 유효 후보면
    그대로 유지 → 새로고침해도 안 바뀜. reroll 슬롯이거나 pin이 무효면 새로 뽑는다.
    cuisine_ids(국가별 필터)는 점심/저녁/취향에만 적용. BEST/인기는 전역·결정적이라
    필터/핀 없이 데이터 그대로(안정적). 확률/핀 카드를 먼저 확정하고 BEST/인기가 그걸 피한다.

    Args:
        cuisine_ids: 국가별 필터(선택). pinned: {slot: menu_id}. reroll: 재추첨할 슬롯 집합.

    Returns:
        dict: {'lunch','dinner','best','popular','taste'} → 각 Menu 또는 None.
    """
    pinned = pinned or {}
    reroll = reroll or set()
    used = set()

    def take(menu):
        if menu is not None:
            used.add(menu.id)
        return menu

    def pin(slot):
        return None if slot in reroll else pinned.get(slot)

    # 점심/저녁 구분 없이 둘 다 전체 메뉴에서 무작위(서로 중복 없음). 슬롯 키는 식별자로만 유지.
    lunch = take(_pick_meal(user, None, cuisine_ids, used, pin('lunch')))
    dinner = take(_pick_meal(user, None, cuisine_ids, used, pin('dinner')))
    taste = take(_pick_taste(user, cuisine_ids, used, pin('taste')))
    best = take(_pick_best(user, used))
    popular = take(_pick_popular(user, used))

    picks = {
        'lunch': lunch, 'dinner': dinner,
        'best': best, 'popular': popular, 'taste': taste,
    }
    logger.info(
        '[recommend_dashboard] user=%s cuisine=%s reroll=%s -> %s',
        getattr(user, 'pk', None), cuisine_ids, reroll,
        {k: (v.name if v else None) for k, v in picks.items()},
    )
    return picks


def _pick_meal(user, meal_time, cuisine_ids, used, preferred_id=None):
    """후보 중 1개. preferred_id가 아직 유효 후보면 그대로, 아니면 무작위.

    meal_time=None이면 끼니 구분 없이 전체 '메인' 후보에서 뽑는다.
    """
    pool = [m for m in _candidates(user, meal_time, cuisine_ids) if m.id not in used]
    if not pool:
        return None
    if preferred_id is not None:
        for m in pool:
            if m.id == preferred_id:
                return m
    return random.choice(pool)


def _pick_best(user, used):
    """오늘의 BEST: 평균 평점이 가장 높은 메뉴 1개(결정적, 하루 종일 고정).

    동점이면 후기 수 많은 순 → 이름 순으로 안정적으로 정한다. 후기가 하나도 없으면 None.
    """
    pool = [m for m in _candidates(user, None) if m.id not in used]
    if not pool:
        return None
    stats = _rating_stats([m.id for m in pool])  # {menu_id: (avg, count)}
    rated = [m for m in pool if m.id in stats]
    if not rated:
        return None
    rated.sort(key=lambda m: (-stats[m.id][0], -stats[m.id][1], m.name))
    return rated[0]


def _pick_popular(user, used):
    """지금 인기: 최근 POPULAR_HOURS시간 내 좋아요가 가장 많은 메뉴 1개(결정적, 실시간).

    그 시간 내 좋아요가 없으면 전체 기간 좋아요 최다로 폴백. 동점이면 이름 순.
    """
    pool = [m for m in _candidates(user, None) if m.id not in used]
    if not pool:
        return None
    ids = [m.id for m in pool]

    since = timezone.now() - timedelta(hours=POPULAR_HOURS)
    counts = {
        row['menu_id']: row['c']
        for row in MenuLike.objects.filter(menu_id__in=ids, created_at__gte=since)
        .values('menu_id').annotate(c=Count('id'))
    }
    if not counts:  # 최근 시간창에 좋아요 없음 → 전체 기간으로 폴백
        counts = _like_counts(ids)
    if not counts:
        return None

    by_id = {m.id: m for m in pool}
    top_id = sorted(counts, key=lambda mid: (-counts[mid], by_id[mid].name))[0]
    return by_id[top_id]


def _pick_taste(user, cuisine_ids, used, preferred_id=None):
    """당신의 취향을 담은 메뉴 1개. 협업(피어 좋아요/고평점) + 요리종류 선호도.

    preferred_id가 아직 유효 후보면 그대로 유지(새로고침 안정성).
    """
    pool = [m for m in _candidates(user, None, cuisine_ids) if m.id not in used]
    if not pool:
        return None
    if preferred_id is not None:
        for m in pool:
            if m.id == preferred_id:
                return m

    collab_counts = _collab_counts(user, [m.id for m in pool])
    max_collab = max(collab_counts.values(), default=0)
    pref_scores = (
        dict(user.preferences.values_list('cuisine_id', 'score'))
        if user.is_authenticated else {}
    )

    weighted = []
    for m in pool:
        collab_norm = (collab_counts.get(m.id, 0) / max_collab) if max_collab else 0.0
        pref_norm = (pref_scores.get(m.cuisine_id, 3) - 1) / 4.0  # 1~5 → 0~1, 기본 중립 3
        weighted.append((m, W_COLLAB * collab_norm + W_PREF * pref_norm + BASE_WEIGHT))
    return _weighted_one(weighted)


# ── 후보/신호 헬퍼 ─────────────────────────────────────────────────────────

def _candidates(user, meal_time, cuisine_ids=None):
    """하드 제외를 적용한 후보 메뉴 리스트('메인' 코스; meal_time 주면 해당 끼니+'무관';
    cuisine_ids 주면 그 국가만)."""
    qs = (
        Menu.objects
        .filter(course__name=MAIN_COURSE_NAME)
        .select_related('cuisine', 'course')
    )
    if meal_time:
        qs = qs.filter(meal_time__in=[meal_time, Menu.MealTime.ANY])
    if cuisine_ids:
        qs = qs.filter(cuisine_id__in=cuisine_ids)

    allergy_ids = list(catalog.user_allergy_ids(user))
    if allergy_ids:
        qs = qs.exclude(menu_allergies__allergy_id__in=allergy_ids)

    if user.is_authenticated:
        liked_ids = set(user.menu_likes.values_list('menu_id', flat=True))
        if liked_ids:
            qs = qs.exclude(id__in=liked_ids)  # 이미 좋아요 → 발견성 위해 제외
        since = timezone.now() - timedelta(days=RECENT_DAYS)
        recent = user.meal_records.filter(created_at__gte=since)
        # menu FK가 있는 기록은 id로 정확히 제외, 없는(레거시/카탈로그 밖) 것만 이름 근사.
        recent_menu_ids = set(
            recent.exclude(menu__isnull=True).values_list('menu_id', flat=True)
        )
        if recent_menu_ids:
            qs = qs.exclude(id__in=recent_menu_ids)
        recent_names = list(
            recent.filter(menu__isnull=True).values_list('food_name', flat=True)
        )
        if recent_names:
            qs = qs.exclude(name__in=recent_names)

    return list(qs)


def _collab_counts(user, cand_ids):
    """나와 취향이 겹치는 피어들이 좋아요/고평점한 후보 메뉴별 신호 합. {menu_id: count}."""
    if not user.is_authenticated:
        return {}
    interest_ids = _my_interest_ids(user)
    if not interest_ids:
        return {}

    peer_ids = set(
        MenuLike.objects.filter(menu_id__in=interest_ids)
        .exclude(user=user).values_list('user_id', flat=True)
    )
    peer_ids |= set(
        Review.objects.filter(menu_id__in=interest_ids, rating__gte=HIGH_RATING)
        .exclude(user=user).values_list('user_id', flat=True)
    )
    if not peer_ids:
        return {}

    counts = {}
    like_rows = (
        MenuLike.objects.filter(user_id__in=peer_ids, menu_id__in=cand_ids)
        .values('menu_id').annotate(c=Count('id'))
    )
    for row in like_rows:
        counts[row['menu_id']] = counts.get(row['menu_id'], 0) + row['c']
    review_rows = (
        Review.objects
        .filter(user_id__in=peer_ids, rating__gte=HIGH_RATING, menu_id__in=cand_ids)
        .values('menu_id').annotate(c=Count('id'))
    )
    for row in review_rows:
        counts[row['menu_id']] = counts.get(row['menu_id'], 0) + row['c']
    return counts


def _my_interest_ids(user):
    """내가 관심 있는 메뉴 id 집합: 좋아요 + 후기 + 먹은 것(menu FK 우선, 없으면 이름 근사)."""
    liked = set(user.menu_likes.values_list('menu_id', flat=True))
    reviewed = set(user.reviews.values_list('menu_id', flat=True))
    eaten = set(
        user.meal_records.exclude(menu__isnull=True).values_list('menu_id', flat=True)
    )
    eaten_names = list(
        user.meal_records.filter(menu__isnull=True).values_list('food_name', flat=True)
    )
    eaten |= set(Menu.objects.filter(name__in=eaten_names).values_list('id', flat=True))
    return liked | reviewed | eaten


def _like_counts(cand_ids):
    """후보 메뉴별 전역 좋아요 수. {menu_id: count}."""
    rows = (
        MenuLike.objects.filter(menu_id__in=cand_ids)
        .values('menu_id').annotate(c=Count('id'))
    )
    return {row['menu_id']: row['c'] for row in rows}


def _rating_stats(cand_ids):
    """후보 메뉴별 (평균 평점, 후기 수). 후기 없는 메뉴는 키에 없음. {menu_id: (avg, count)}."""
    rows = (
        Review.objects.filter(menu_id__in=cand_ids)
        .values('menu_id').annotate(a=Avg('rating'), c=Count('id'))
    )
    return {row['menu_id']: (row['a'], row['c']) for row in rows}


def _weighted_one(weighted_items):
    """가중치 확률로 1개만 뽑는다."""
    picked = _weighted_sample(weighted_items, 1)
    return picked[0] if picked else None


def _weighted_sample(weighted_items, k):
    """가중치 비복원 추출 (Efraimidis-Spirakis A-Res).

    각 항목에 key = U^(1/weight) (U는 0~1 균등난수)를 부여하고 key가 큰 순으로
    상위 k개를 뽑는다. weight가 클수록(점수가 높을수록) 뽑힐 확률이 커진다.
    """
    keyed = []
    for item, weight in weighted_items:
        weight = max(float(weight), 1e-6)
        key = random.random() ** (1.0 / weight)
        keyed.append((key, item))
    keyed.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in keyed[:k]]
