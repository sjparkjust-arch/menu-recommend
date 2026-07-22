"""음식분류(Cuisine) 9종 → 6종 재편: 한식/중식/일식/양식/아시안/패스트푸드.

없어지는 3종(멕시칸·인도·치킨)에 속한 5개 메뉴를 재배치한 뒤 그 3종 Cuisine을 삭제한다.
- 퀘사디아·타코(멕시칸) → 양식
- 버터치킨커리(인도) → 아시안
- 양념치킨·후라이드 치킨(치킨) → 패스트푸드

Cuisine.on_delete=PROTECT(Menu)이므로 먼저 재배치해야 삭제 가능하고,
UserPreference.cuisine은 on_delete=CASCADE라 삭제되는 Cuisine을 선호하던 유저의
선호도 레코드는 함께 자동 정리된다(별도 처리 불필요).
"""

from django.db import migrations

REMAP = {
    '퀘사디아': '양식',
    '타코': '양식',
    '버터치킨커리': '아시안',
    '양념치킨': '패스트푸드',
    '후라이드 치킨': '패스트푸드',
}
REMOVED_CUISINES = ['멕시칸', '인도', '치킨']


def remap_and_cleanup(apps, schema_editor):
    Menu = apps.get_model('menus', 'Menu')
    Cuisine = apps.get_model('menus', 'Cuisine')
    for menu_name, new_cuisine_name in REMAP.items():
        cuisine = Cuisine.objects.filter(name=new_cuisine_name).first()
        if cuisine:
            Menu.objects.filter(name=menu_name).update(cuisine=cuisine)
    Cuisine.objects.filter(name__in=REMOVED_CUISINES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('menus', '0001_initial'),
        ('accounts', '0002_initial'),  # UserPreference.cuisine cascade 삭제를 위해 필요
    ]

    operations = [
        migrations.RunPython(remap_and_cleanup, migrations.RunPython.noop),
    ]
