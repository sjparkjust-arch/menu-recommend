"""음식 유튜버들의 추천 영상(썸네일)을 유튜브 검색에서 수집해 정적 파일로 저장한다.

    python manage.py fetch_youtube_picks

각 유튜버 이름으로 유튜브 검색 결과 HTML을 받아 상위 영상 videoId를 뽑아
menus/youtube_picks.py (PICKS 리스트)로 저장한다. 대시보드는 이 저장본을 렌더하므로
발표 중 매번 유튜브를 긁지 않는다(빠르고 안정적). 새로고침하려면 이 명령을 다시 실행.

API 키 불필요. 썸네일은 https://img.youtube.com/vi/<id>/hqdefault.jpg (구글 CDN).
"""

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

# 사용자가 지정한 음식 유튜버(순서 유지)
YOUTUBERS = [
    '입질의 추억', '육식맨', '취요남', '밥굽남',
    '히밥', '쯔양', '떵개떵', '흥삼이네', '입짧은햇님',
]
# 음식 리뷰/먹방 영상만 잡히도록 검색어에 덧붙이는 키워드
FOOD_KEYWORD = '먹방'
PER_CHANNEL = 6  # 유튜버당 수집할 영상 수(풀). 대시보드는 매 새로고침 이 중 랜덤으로 노출.
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'
VIDEO_RE = re.compile(r'"videoId":"([A-Za-z0-9_-]{11})"')


def _top_video_ids(name, n):
    q = urllib.parse.quote(f'{name} {FOOD_KEYWORD}')
    # sp=EgIQAQ%3D%3D : 검색 필터 '영상(video)'만 → 채널/재생목록 잡음 제거
    url = f'https://www.youtube.com/results?search_query={q}&sp=EgIQAQ%253D%253D'
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ko-KR,ko'})
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode('utf-8', 'ignore')
    seen, out = set(), []
    for vid in VIDEO_RE.findall(html):
        if vid not in seen:
            seen.add(vid)
            out.append(vid)
        if len(out) >= n:
            break
    return out


def _video_title(vid):
    """유튜브 oEmbed로 영상 제목을 정확히 가져온다(API 키 불필요). 실패 시 ''."""
    url = ('https://www.youtube.com/oembed?format=json&url='
           + urllib.parse.quote(f'https://www.youtube.com/watch?v={vid}', safe=''))
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get('title', '')
    except Exception:  # noqa: BLE001 (비공개/삭제 영상 등은 제목 없이 진행)
        return ''


class Command(BaseCommand):
    help = '음식 유튜버 추천 영상 썸네일을 수집해 menus/youtube_picks.py로 저장한다.'

    def handle(self, *args, **options):
        picks = []
        for name in YOUTUBERS:
            try:
                vids = _top_video_ids(name, PER_CHANNEL)
                videos = []
                for vid in vids:
                    videos.append({'id': vid, 'title': _video_title(vid)})
                    time.sleep(0.4)  # oEmbed 예의상 간격
                if videos:
                    picks.append({'name': name, 'videos': videos})
                    self.stdout.write(self.style.SUCCESS(f'  ✓ {name}: {len(videos)}개'))
                else:
                    self.stdout.write(f'  ! {name}: 영상 못 찾음')
            except Exception as e:  # noqa: BLE001
                self.stdout.write(f'  ! {name}: {type(e).__name__} → 스킵')
            time.sleep(1.0)

        out_path = Path(settings.BASE_DIR) / 'menus' / 'youtube_picks.py'
        lines = ['"""fetch_youtube_picks 명령이 생성한 유튜버 추천 영상 목록. 직접 수정 금지."""',
                 '# 각 항목: {"name": 유튜버, "videos": [{"id": 영상ID, "title": 제목}, ...]}', '', 'PICKS = [']
        for p in picks:
            lines.append(f'    {{"name": {p["name"]!r}, "videos": [')
            for v in p['videos']:
                lines.append(f'        {{"id": {v["id"]!r}, "title": {v["title"]!r}}},')
            lines.append('    ]},')
        lines.append(']')
        out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

        self.stdout.write(self.style.SUCCESS(
            f'\n저장: {out_path} ({len(picks)}/{len(YOUTUBERS)} 유튜버)'
        ))
