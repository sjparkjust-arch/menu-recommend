"""사이트를 채우기 위한 대량 더미데이터 시드.

    python manage.py seed_dummy [--users 40]

회원(더미) + 선호도/알러지 + 좋아요 + 후기(음식/음식점·평점·제목) + 후기 좋아요 +
식사기록(날짜 분산)을 대량으로 만든다. 협업추천 데모용 seed_demo(10명 클러스터)는
건드리지 않고 그 위에 얹는다. seed_data(메뉴) 이후에 실행한다.

멱등: 선택을 전역 random이 아니라 **엔티티별 결정적 RNG**(user.id/review.id 시드)로 하기
때문에, 몇 번을 다시 돌려도 같은 (user,menu)/(user,review) 조합을 뽑는다 → get_or_create가
전부 기존으로 처리해 신규 0. 식사기록은 자연키가 없어 '기록 0인 유저만' 게이트로 막는다.
알러지는 신규 더미 유저에게만 부여(기존 실유저 추천 동작을 바꾸지 않기 위해).
"""

import random
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Allergy, UserAllergy, UserPreference
from menus.models import Cuisine, Menu, MenuLike
from records.models import MealRecord
from reviews.models import Review, ReviewLike

User = get_user_model()

DUMMY_PASSWORD = 'bobpick123!'

SURNAMES = list('김이박최정강조윤장임한오서신권황안송전홍류')
GIVEN = ['민준', '서연', '도윤', '예은', '시우', '하은', '주원', '지호', '수아', '건우',
         '유진', '현우', '다은', '지훈', '서현', '우진', '하린', '은우', '채원', '준서',
         '지아', '승현', '소율', '지민', '민서', '예준', '지우', '서준', '하율', '윤아']

MEAL_TYPES = ['BREAKFAST', 'LUNCH', 'DINNER', 'SNACK']

FOOD_REVIEW_TEMPLATES = [
    '{m} 정말 맛있어요! 또 먹고 싶네요.',
    '{m} 국물이 진하고 깊은 맛이에요.',
    '가성비 좋은 {m}, 양도 푸짐합니다.',
    '{m}는 언제 먹어도 실패가 없어요.',
    '생각보다 아쉬웠던 {m}… 기대가 컸나 봐요.',
    '{m} 비주얼도 좋고 맛도 훌륭해요.',
    '혼밥으로 {m} 딱 좋네요.',
    '{m} 재료가 신선해서 만족스러웠어요.',
    '매콤한 {m}, 스트레스가 확 풀립니다.',
    '{m} 담백해서 자꾸 손이 가요.',
    '{m} 시켜봤는데 인생메뉴 등극했어요.',
    '{m} 무난하게 괜찮아요. 평타는 칩니다.',
]
PLACE_REVIEW_TEMPLATES = [
    '사장님이 친절하시고 {m}도 맛있어요.',
    '분위기 좋은 곳이에요. {m} 강력 추천합니다.',
    '웨이팅 있지만 {m} 먹으러 갈 만해요.',
    '재방문 의사 100%! {m} 최고였어요.',
    '주차가 조금 불편하지만 {m} 맛집 인정.',
    '가격대는 있지만 {m} 퀄리티가 좋아요.',
    '데이트 코스로 좋아요. {m} 플레이팅이 예뻐요.',
]
RESTAURANT_NAMES = [
    '골목집', '한상차림', '미도인', '우리동네맛집', '정성식당', '행복한밥상', '청담뜰',
    '종로할매집', '바다향기', '예담', '손맛나는집', '미가', '맛찬들', '노포식당', '봄날',
    '역전회관', '일품관', '홍대부엌', '강남옥', '수라간',
]
RECORD_COMMENTS = [
    '', '', '', '혼밥 성공', '친구랑 같이', '야근 후 든든하게', '점심 회식',
    '배달로 시켜먹음', '집에서 해먹음', '존맛탱', '그냥 그랬음', '또 먹고 싶다',
    '다이어트는 내일부터', '주말 브런치',
]


def _weighted_rating(rng):
    """평점 3~5에 가중, 가끔 1~2."""
    return rng.choices([5, 4, 3, 2, 1], weights=[38, 30, 20, 7, 5])[0]


class Command(BaseCommand):
    help = '사이트를 채우기 위한 대량 더미데이터(회원/좋아요/후기/리뷰좋아요/식사기록/선호도)를 넣는다.'

    def add_arguments(self, parser):
        parser.add_argument('--users', type=int, default=40, help='새로 만들 더미 유저 수')

    @transaction.atomic
    def handle(self, *args, **options):
        n_new = options['users']

        menus = list(Menu.objects.select_related('cuisine').all())
        cuisines = list(Cuisine.objects.all())
        allergies = list(Allergy.objects.all())
        if not menus:
            self.stderr.write(self.style.ERROR(
                '메뉴가 없습니다. 먼저 `python manage.py seed_data`를 실행하세요.'
            ))
            return
        menus_by_cuisine = {}
        for m in menus:
            menus_by_cuisine.setdefault(m.cuisine_id, []).append(m)

        c = dict(users=0, prefs=0, allergies=0, likes=0,
                 reviews=0, review_likes=0, records=0)

        def pick_menus(rng, pref_ids, n):
            """선호 요리종류 위주로 n개 메뉴(중복 없음). rng는 결정적 RNG."""
            preferred = [m for cid in pref_ids for m in menus_by_cuisine.get(cid, [])]
            others = [m for m in menus if m.cuisine_id not in pref_ids]
            n_pref = min(int(n * 0.7), len(preferred))
            n_other = min(n - n_pref, len(others))
            chosen = rng.sample(preferred, n_pref) if preferred else []
            chosen += rng.sample(others, n_other) if others else []
            return chosen

        # 1) 신규 더미 유저 (+선호도 +알러지). 이름/알러지는 인덱스 시드로 결정적.
        for i in range(1, n_new + 1):
            username = f'dummy_{i:03d}'
            urng = random.Random(10_000 + i)
            surname = urng.choice(SURNAMES)
            given = urng.choice(GIVEN)
            user, is_new = User.objects.get_or_create(
                username=username,
                defaults={'last_name': surname, 'first_name': given,
                          'email': f'{username}@example.com'},
            )
            if is_new:
                user.set_password(DUMMY_PASSWORD)
                user.save()
                c['users'] += 1
            # 알러지: 신규 더미 유저의 ~30%에 1~2개(결정적)
            if is_new and allergies and urng.random() < 0.3:
                for al in urng.sample(allergies, urng.randint(1, 2)):
                    _, new = UserAllergy.objects.get_or_create(user=user, allergy=al)
                    c['allergies'] += new

        # 대상 유저 = 모든 비-superuser (기존 실유저/데모 + 신규 더미).
        target_users = list(User.objects.filter(is_superuser=False))

        # 2) 선호도 없는 유저에게 선호도 부여(결정적)
        pref_ids_by_user = {}
        for user in target_users:
            existing = list(user.preferences.values_list('cuisine_id', flat=True))
            if not existing and cuisines:
                prng = random.Random(user.id * 7 + 1)
                for cz in prng.sample(cuisines, prng.randint(2, 3)):
                    _, new = UserPreference.objects.get_or_create(
                        user=user, cuisine=cz, defaults={'score': prng.randint(3, 5)},
                    )
                    c['prefs'] += new
                existing = list(user.preferences.values_list('cuisine_id', flat=True))
            pref_ids_by_user[user.id] = set(existing)

        # 3) 좋아요 (유저별 결정적; 일부는 최근 6시간 → 실시간 인기 순위 반영)
        for user in target_users:
            lrng = random.Random(user.id * 13 + 3)
            for menu in pick_menus(lrng, pref_ids_by_user[user.id], lrng.randint(8, 20)):
                like, new = MenuLike.objects.get_or_create(user=user, menu=menu)
                if new:
                    c['likes'] += 1
                    if lrng.random() < 0.15:
                        when = timezone.now() - timedelta(minutes=lrng.randint(5, 350))
                    else:
                        when = timezone.now() - timedelta(days=lrng.uniform(0, 30))
                    MenuLike.objects.filter(pk=like.pk).update(created_at=when)

        # 4) 후기 + 평점 (유저별 결정적; 1인1메뉴 1후기, food/place≈7:3, 날짜 분산)
        for user in target_users:
            rrng = random.Random(user.id * 17 + 5)
            for menu in pick_menus(rrng, pref_ids_by_user[user.id], rrng.randint(3, 8)):
                is_place = rrng.random() < 0.3
                if is_place:
                    rtype = Review.ReviewType.PLACE
                    content = rrng.choice(PLACE_REVIEW_TEMPLATES).format(m=menu.name)
                    title = rrng.choice(RESTAURANT_NAMES) + rrng.choice(['', '', ' 본점', ' 2호점'])
                else:
                    rtype = Review.ReviewType.FOOD
                    content = rrng.choice(FOOD_REVIEW_TEMPLATES).format(m=menu.name)
                    title = ''
                review, new = Review.objects.get_or_create(
                    user=user, menu=menu,
                    defaults={'review_type': rtype, 'rating': _weighted_rating(rrng),
                              'title': title, 'content': content},
                )
                if new:
                    c['reviews'] += 1
                    # 오늘 20% / 최근7일 35% / 최근30일 45%로 분산 → 랭킹 오늘·주간·전체,
                    # 대시보드 음식후기 일간/주간 카드가 모두 채워진다. '오늘'은 자정~현재 사이로
                    # 확실히 넣는다(UTC 기준 범위 비교라 안전).
                    now = timezone.now()
                    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    roll = rrng.random()
                    if roll < 0.2:
                        elapsed = max((now - today0).total_seconds(), 1)
                        when = today0 + timedelta(seconds=rrng.uniform(0, elapsed))
                    elif roll < 0.55:
                        when = now - timedelta(days=rrng.uniform(1, 7))
                    else:
                        when = now - timedelta(days=rrng.uniform(7, 30))
                    Review.objects.filter(pk=review.pk).update(created_at=when)

        # 5) 후기 좋아요 (후기별 결정적; 후기당 0~15명)
        user_ids = [u.id for u in target_users]
        for review in Review.objects.all():
            vrng = random.Random(review.id * 3 + 11)
            k = vrng.randint(0, min(15, len(user_ids) - 1))
            if k <= 0:
                continue
            for uid in vrng.sample(user_ids, k):
                if uid == review.user_id:
                    continue
                _, new = ReviewLike.objects.get_or_create(user_id=uid, review=review)
                c['review_likes'] += new

        # 6) 식사기록 — 기록 0인 유저만(멱등 게이트). 최근 90일에 분산.
        for user in target_users:
            if user.meal_records.exists():
                continue
            mrng = random.Random(user.id * 19 + 7)
            pref_ids = pref_ids_by_user[user.id]
            pool = [m for cid in pref_ids for m in menus_by_cuisine.get(cid, [])] or menus
            for _ in range(mrng.randint(20, 35)):
                menu = mrng.choice(pool)
                rec = MealRecord.objects.create(
                    user=user, menu=menu, food_name=menu.name,
                    meal_type=mrng.choice(MEAL_TYPES),
                    rating=_weighted_rating(mrng),
                    comment=mrng.choice(RECORD_COMMENTS),
                )
                d = timezone.localtime(timezone.now() - timedelta(days=mrng.randint(0, 90)))
                aware = timezone.make_aware(datetime(
                    d.year, d.month, d.day,
                    mrng.choice([8, 12, 13, 19]), mrng.randint(0, 59),
                ))
                MealRecord.objects.filter(pk=rec.pk).update(created_at=aware)
                c['records'] += 1

        self.stdout.write(self.style.SUCCESS(
            '더미데이터 신규 생성:\n'
            f"  회원 {c['users']}명 (비밀번호 {DUMMY_PASSWORD}), "
            f"선호도 {c['prefs']}건, 알러지 {c['allergies']}건\n"
            f"  좋아요 {c['likes']}건, 후기 {c['reviews']}건, "
            f"후기좋아요 {c['review_likes']}건, 식사기록 {c['records']}건"
        ))
        self.stdout.write(
            f'전체: 유저 {User.objects.count()} / 좋아요 {MenuLike.objects.count()} / '
            f'후기 {Review.objects.count()} / 리뷰좋아요 {ReviewLike.objects.count()} / '
            f'식사기록 {MealRecord.objects.count()}'
        )
