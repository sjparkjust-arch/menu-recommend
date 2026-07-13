"""초기 마스터 데이터 + 메뉴 시드.

    python manage.py seed_data

재실행해도 중복이 생기지 않도록 모든 행을 get_or_create로 만든다.
이미지는 비워둔다(나중에 admin/스토리지로 추가).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Allergy
from menus.models import Cuisine, Course, Menu, MenuAllergy

CUISINES = ['한식', '중식', '일식', '양식']
COURSES = ['메인', '사이드', '디저트', '음료']
ALLERGIES = ['갑각류', '견과류', '유제품', '계란', '밀', '대두']

LUNCH = Menu.MealTime.LUNCH
DINNER = Menu.MealTime.DINNER
ANY = Menu.MealTime.ANY

# (이름, 요리종류, 코스, meal_time, [실제 포함 알러지 재료])
MENUS = [
    # 한식
    ('김치찌개', '한식', '메인', ANY, ['대두']),                       # 두부, 된장
    ('된장찌개', '한식', '메인', ANY, ['대두']),                       # 된장, 두부
    ('삼겹살', '한식', '메인', DINNER, ['대두']),                      # 쌈장
    ('비빔밥', '한식', '메인', ANY, ['계란', '대두']),                 # 계란프라이, 고추장
    ('불고기', '한식', '메인', ANY, ['대두', '밀']),                   # 간장 양념
    ('냉면', '한식', '메인', LUNCH, ['계란', '밀']),                   # 계란 고명, 면
    ('갈비탕', '한식', '메인', ANY, ['계란']),                         # 계란 지단
    ('삼계탕', '한식', '메인', ANY, ['견과류']),                       # 잣
    ('떡볶이', '한식', '메인', ANY, ['밀', '대두']),                   # 밀떡/어묵, 고추장
    ('순두부찌개', '한식', '메인', ANY, ['대두', '계란']),             # 두부, 계란
    ('김밥', '한식', '메인', LUNCH, ['계란', '대두']),                # 계란, 단무지/맛살
    ('잡채', '한식', '사이드', ANY, ['대두', '밀']),                   # 간장
    ('김치전', '한식', '사이드', ANY, ['밀', '계란']),                 # 부침가루, 계란
    ('계란말이', '한식', '사이드', ANY, ['계란']),

    # 중식
    ('짜장면', '중식', '메인', ANY, ['밀', '대두']),                   # 면, 춘장
    ('짬뽕', '중식', '메인', ANY, ['밀', '갑각류']),                   # 면, 해산물
    ('탕수육', '중식', '메인', ANY, ['밀', '계란', '대두']),           # 튀김옷, 소스
    ('마파두부', '중식', '메인', ANY, ['대두', '밀']),                 # 두부, 두반장
    ('깐풍기', '중식', '메인', ANY, ['밀', '계란', '대두']),
    ('유산슬', '중식', '메인', ANY, ['갑각류', '대두']),               # 새우/해삼
    ('볶음밥', '중식', '메인', ANY, ['계란', '대두']),
    ('마라탕', '중식', '메인', ANY, ['대두']),                         # 두부
    ('양장피', '중식', '사이드', ANY, ['갑각류', '계란']),             # 새우/해삼, 지단
    ('꿔바로우', '중식', '사이드', ANY, ['밀', '계란', '대두']),

    # 일식
    ('초밥', '일식', '메인', ANY, ['갑각류', '계란', '대두']),         # 새우/계란초밥, 간장
    ('라멘', '일식', '메인', ANY, ['밀', '계란', '대두']),             # 면, 반숙란, 육수
    ('우동', '일식', '메인', ANY, ['밀', '대두']),                     # 면, 간장
    ('돈카츠', '일식', '메인', ANY, ['밀', '계란', '대두']),           # 빵가루, 튀김옷, 소스
    ('규동', '일식', '메인', ANY, ['대두', '밀', '계란']),             # 간장, 온천란
    ('텐동', '일식', '메인', ANY, ['밀', '갑각류', '대두']),           # 새우튀김
    ('오코노미야키', '일식', '사이드', ANY, ['밀', '계란', '갑각류']),
    ('가라아게', '일식', '사이드', ANY, ['밀', '대두']),               # 튀김옷, 간장
    ('미소시루', '일식', '사이드', ANY, ['대두']),                     # 미소, 두부
    ('연어사시미', '일식', '사이드', ANY, ['대두']),                   # 간장

    # 양식
    ('토마토파스타', '양식', '메인', ANY, ['밀']),
    ('까르보나라', '양식', '메인', ANY, ['밀', '계란', '유제품']),
    ('스테이크', '양식', '메인', DINNER, ['유제품']),                  # 버터
    ('마르게리타피자', '양식', '메인', ANY, ['밀', '유제품']),
    ('리조또', '양식', '메인', ANY, ['유제품']),                       # 파마산, 버터
    ('시저샐러드', '양식', '사이드', LUNCH, ['유제품', '계란', '밀']), # 파마산, 드레싱, 크루통
    ('크림스프', '양식', '사이드', ANY, ['유제품', '밀']),
    ('어니언링', '양식', '사이드', ANY, ['밀', '계란']),

    # 디저트
    ('치즈케이크', '양식', '디저트', ANY, ['유제품', '계란', '밀']),
    ('티라미수', '양식', '디저트', ANY, ['유제품', '계란', '밀']),
    ('마카롱', '양식', '디저트', ANY, ['견과류', '계란', '유제품']),   # 아몬드가루
    ('아이스크림', '양식', '디저트', ANY, ['유제품', '계란']),
    ('호떡', '한식', '디저트', ANY, ['밀', '견과류']),                 # 견과류 소
    ('붕어빵', '한식', '디저트', ANY, ['밀', '계란']),

    # 음료
    ('아메리카노', '양식', '음료', ANY, []),
    ('카페라떼', '양식', '음료', ANY, ['유제품']),
    ('밀크티', '양식', '음료', ANY, ['유제품']),
]


class Command(BaseCommand):
    help = '초기 마스터 데이터(요리종류/코스/알러지)와 메뉴 시드를 넣는다.'

    @transaction.atomic
    def handle(self, *args, **options):
        cuisines = self._seed_master(Cuisine, CUISINES, '요리 종류')
        courses = self._seed_master(Course, COURSES, '코스')
        allergies = self._seed_master(Allergy, ALLERGIES, '알러지')

        menu_created = 0
        link_created = 0
        for name, cuisine_name, course_name, meal_time, allergy_names in MENUS:
            menu, created = Menu.objects.get_or_create(
                name=name,
                defaults={
                    'cuisine': cuisines[cuisine_name],
                    'course': courses[course_name],
                    'meal_time': meal_time,
                },
            )
            if created:
                menu_created += 1

            for allergy_name in allergy_names:
                _, link_is_new = MenuAllergy.objects.get_or_create(
                    menu=menu,
                    allergy=allergies[allergy_name],
                )
                if link_is_new:
                    link_created += 1

        self.stdout.write(self.style.SUCCESS(
            f'메뉴 {menu_created}개 신규 / 전체 {Menu.objects.count()}개, '
            f'메뉴-알러지 연결 {link_created}건 신규 / 전체 {MenuAllergy.objects.count()}건'
        ))

    def _seed_master(self, model, names, label):
        objs = {}
        created = 0
        for name in names:
            obj, is_new = model.objects.get_or_create(name=name)
            objs[name] = obj
            if is_new:
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f'{label}: {created}개 신규 / 전체 {len(names)}개'
        ))
        return objs
