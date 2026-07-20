"""데모용 샘플 사용자 + 상호작용(좋아요/후기/식사기록/선호도) 시드.

    python manage.py seed_demo

협업 필터링 추천이 실제로 '보이도록' 취향이 겹치는 가짜 사용자들을 만든다.
같은 취향 클러스터(한식/일식/양식) 안에서 좋아요가 일부 겹치고 일부 다르게 설계돼,
한 사용자로 로그인하면 같은 클러스터 다른 사용자가 좋아한 '내가 아직 안 누른' 메뉴가
추천으로 떠오른다. 재실행해도 중복이 생기지 않도록 모두 get_or_create를 쓴다.

마스터 데이터/메뉴는 seed_data가 만든다(이 명령은 seed_data 이후에 실행).
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import UserPreference
from menus.models import Cuisine, Menu, MenuLike
from records.models import MealRecord
from reviews.models import Review

User = get_user_model()

DEMO_PASSWORD = 'bobpick123!'

# (username, 성, 이름, [좋아요 메뉴], [(후기 메뉴, 평점)], [먹은 음식(=메뉴이름)], {요리종류: 선호점수})
# 클러스터 안에서 좋아요가 촘촘히 겹치도록 설계 → user-based/item-based 협업이 결과를 낸다.
# 저녁 전용 메뉴(삼겹살/스테이크)도 여러 명이 눌러 저녁 카드에도 신호가 생기게 한다.
# eaten은 (음식이름, 먹은 횟수) — 그래프가 의미 있게 보이도록 횟수를 다양하게. 횟수는 ≤4.
DEMO_USERS = [
    # ── 한식 클러스터 (4명) ──
    ('demo_hansik1', '김', '한결',
     ['김치찌개', '된장찌개', '불고기', '비빔밥', '삼겹살'],
     [('비빔밥', 5), ('불고기', 4)],
     [('김치찌개', 3), ('김밥', 2), ('불고기', 1)],
     {'한식': 5, '중식': 2}),
    ('demo_hansik2', '이', '집밥',
     ['김치찌개', '된장찌개', '갈비탕', '삼계탕', '삼겹살'],
     [('갈비탕', 5), ('삼계탕', 4)],
     [('된장찌개', 3), ('갈비탕', 2), ('삼겹살', 1)],
     {'한식': 5, '양식': 2}),
    ('demo_hansik3', '한', '수라',
     ['김치찌개', '불고기', '갈비탕', '떡볶이', '순두부찌개'],
     [('떡볶이', 5), ('김치찌개', 5)],
     [('떡볶이', 4), ('불고기', 2), ('김치찌개', 1)],
     {'한식': 5, '일식': 2}),
    ('demo_hansik4', '오', '밥심',
     ['된장찌개', '삼계탕', '순두부찌개', '삼겹살', '비빔밥'],
     [('삼겹살', 5), ('순두부찌개', 4)],
     [('삼계탕', 2), ('순두부찌개', 2), ('비빔밥', 1)],
     {'한식': 5, '중식': 3}),

    # ── 일식 클러스터 (3명) ──
    ('demo_ilsik1', '박', '스시',
     ['라멘', '우동', '돈카츠', '규동'],
     [('돈카츠', 5), ('라멘', 4)],
     [('라멘', 3), ('우동', 2), ('돈카츠', 1)],
     {'일식': 5, '한식': 3}),
    ('demo_ilsik2', '최', '사시미',
     ['라멘', '우동', '초밥', '텐동'],
     [('초밥', 5), ('텐동', 4)],
     [('우동', 3), ('초밥', 1)],
     {'일식': 5, '중식': 2}),
    ('demo_ilsik3', '유', '오마카세',
     ['라멘', '돈카츠', '초밥', '규동', '텐동'],
     [('규동', 5), ('초밥', 4)],
     [('돈카츠', 2), ('규동', 2), ('라멘', 1)],
     {'일식': 5, '양식': 2}),

    # ── 양식 클러스터 (3명) ──
    ('demo_yangsik1', '정', '파스타',
     ['토마토파스타', '까르보나라', '스테이크', '리조또'],
     [('스테이크', 5), ('리조또', 4)],
     [('토마토파스타', 3), ('스테이크', 2), ('리조또', 1)],
     {'양식': 5, '일식': 2}),
    ('demo_yangsik2', '강', '피자',
     ['토마토파스타', '까르보나라', '마르게리타피자', '스테이크'],
     [('마르게리타피자', 5), ('까르보나라', 4)],
     [('까르보나라', 3), ('마르게리타피자', 1)],
     {'양식': 5, '한식': 2}),
    ('demo_yangsik3', '서', '브런치',
     ['까르보나라', '스테이크', '리조또', '마르게리타피자', '토마토파스타'],
     [('리조또', 5), ('마르게리타피자', 4)],
     [('스테이크', 2), ('리조또', 2), ('까르보나라', 1)],
     {'양식': 5, '중식': 2}),
]

# 같은 음식을 여러 번 먹은 걸 표현할 때 끼니 종류를 돌려가며 만든다(get_or_create 중복 회피).
MEAL_ROTATION = ['LUNCH', 'DINNER', 'BREAKFAST', 'SNACK']


class Command(BaseCommand):
    help = '협업 추천 데모용 샘플 사용자와 좋아요/후기/식사기록/선호도를 넣는다.'

    @transaction.atomic
    def handle(self, *args, **options):
        menus = {m.name: m for m in Menu.objects.all()}
        cuisines = {c.name: c for c in Cuisine.objects.all()}
        if not menus:
            self.stderr.write(self.style.ERROR(
                '메뉴가 없습니다. 먼저 `python manage.py seed_data`를 실행하세요.'
            ))
            return

        users_created = likes_created = reviews_created = 0
        records_created = prefs_created = 0

        for username, last_name, first_name, liked, reviewed, eaten, prefs in DEMO_USERS:
            user, is_new = User.objects.get_or_create(
                username=username,
                defaults={'last_name': last_name, 'first_name': first_name},
            )
            if is_new:
                user.set_password(DEMO_PASSWORD)
                user.save()
                users_created += 1

            for menu_name in liked:
                menu = menus.get(menu_name)
                if not menu:
                    continue
                _, new = MenuLike.objects.get_or_create(user=user, menu=menu)
                likes_created += new

            for menu_name, rating in reviewed:
                menu = menus.get(menu_name)
                if not menu:
                    continue
                _, new = Review.objects.get_or_create(
                    user=user, menu=menu,
                    defaults={'rating': rating, 'content': f'{menu_name} 맛있어요!'},
                )
                reviews_created += new

            for food_name, count in eaten:
                for i in range(count):
                    _, new = MealRecord.objects.get_or_create(
                        user=user, food_name=food_name,
                        meal_type=MEAL_ROTATION[i % len(MEAL_ROTATION)],
                        defaults={'rating': 5},
                    )
                    records_created += new

            for cuisine_name, score in prefs.items():
                cuisine = cuisines.get(cuisine_name)
                if not cuisine:
                    continue
                _, new = UserPreference.objects.get_or_create(
                    user=user, cuisine=cuisine, defaults={'score': score},
                )
                prefs_created += new

        self.stdout.write(self.style.SUCCESS(
            f'데모 사용자 {users_created}명 신규 / 전체 {len(DEMO_USERS)}명 '
            f'(비밀번호: {DEMO_PASSWORD})\n'
            f'좋아요 {likes_created}건, 후기 {reviews_created}건, '
            f'식사기록 {records_created}건, 선호도 {prefs_created}건 신규'
        ))
        self.stdout.write(
            'demo_hansik1 등으로 로그인하면 같은 취향 사용자의 메뉴가 추천에 뜹니다.'
        )
