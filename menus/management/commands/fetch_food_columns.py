"""미식 칼럼(블루리본 서베이 / 미슐랭 가이드)을 수집해 정적 파일로 저장한다.

    python manage.py fetch_food_columns

각 사이트의 칼럼 목록에서 기사 URL을 뽑고, 개별 기사의 og:title / og:image(표준 메타태그)로
제목·썸네일을 가져와 menus/food_columns.py (COLUMNS)로 저장한다. 대시보드는 이 저장본을
렌더하므로 발표 중 매번 외부 사이트를 긁지 않는다. 새로고침하려면 이 명령을 다시 실행.
"""

import html as htmllib
import re
import time
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'
PER_SITE = 8

MICHELIN_LIST = 'https://guide.michelin.com/kr/ko/articles/dining-in'
MICHELIN_BASE = 'https://guide.michelin.com'
MICHELIN_ART_RE = re.compile(r'/kr/ko/article/dining-in/[a-z0-9][a-z0-9-]{6,}')

BLUER_LIST = 'https://www.bluer.co.kr/magazine'
BLUER_BASE = 'https://www.bluer.co.kr'
BLUER_ART_RE = re.compile(r'/magazine/(\d+)')

OG_TITLE_RE = re.compile(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', re.I)
OG_IMAGE_RE = re.compile(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.I)


def _fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ko-KR,ko'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode('utf-8', 'ignore')


def _og(url):
    """기사 페이지에서 og:title / og:image 추출. 실패 시 None."""
    html = _fetch(url)
    t = OG_TITLE_RE.search(html)
    i = OG_IMAGE_RE.search(html)
    if not t:
        return None
    return {
        'title': htmllib.unescape(t.group(1)).strip(),
        'image': htmllib.unescape(i.group(1)).strip() if i else '',
        'url': url,
    }


def _collect(list_url, art_re, base, build, n):
    """목록 페이지에서 기사 URL을 뽑아 각 기사의 og 정보를 모은다."""
    html = _fetch(list_url)
    seen, urls = set(), []
    for m in art_re.finditer(html):
        path = build(m)
        if path and path not in seen:
            seen.add(path)
            urls.append(base + path)
        if len(urls) >= n:
            break
    out = []
    for u in urls:
        try:
            og = _og(u)
            if og and og['image']:
                out.append(og)
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.6)
    return out


class Command(BaseCommand):
    help = '미식 칼럼(블루리본/미슐랭)을 수집해 menus/food_columns.py로 저장한다.'

    def handle(self, *args, **options):
        michelin = _collect(
            MICHELIN_LIST, MICHELIN_ART_RE, MICHELIN_BASE,
            lambda m: m.group(0), PER_SITE,
        )
        self.stdout.write(self.style.SUCCESS(f'미슐랭: {len(michelin)}건'))
        for c in michelin:
            self.stdout.write(f'  ✓ {c["title"][:40]}')

        bluer = _collect(
            BLUER_LIST, BLUER_ART_RE, BLUER_BASE,
            lambda m: f'/magazine/{m.group(1)}', PER_SITE,
        )
        self.stdout.write(self.style.SUCCESS(f'블루리본: {len(bluer)}건'))
        for c in bluer:
            self.stdout.write(f'  ✓ {c["title"][:40]}')

        out_path = Path(settings.BASE_DIR) / 'menus' / 'food_columns.py'
        lines = ['"""fetch_food_columns 명령이 생성한 미식 칼럼 목록. 직접 수정 금지."""',
                 '# COLUMNS = {"michelin": [{title,image,url}], "bluer": [...]}', '', 'COLUMNS = {']
        for key, items in (('michelin', michelin), ('bluer', bluer)):
            lines.append(f'    {key!r}: [')
            for c in items:
                lines.append(f'        {{"title": {c["title"]!r}, "image": {c["image"]!r}, "url": {c["url"]!r}}},')
            lines.append('    ],')
        lines.append('}')
        out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'\n저장: {out_path}'))
