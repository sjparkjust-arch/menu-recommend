"""페이지네이션 표시 헬퍼. 메뉴 목록/후기 목록 등에서 공유한다."""


def page_window(page_obj, per_group=10):
    """페이지 번호를 per_group(기본 10)개씩 묶어 '현재 그룹'만 보여주기 위한 컨텍스트.

    예) 현재 3페이지면 1~10만 노출, '다음'을 누르면 11페이지(다음 그룹 첫 페이지)로 이동.
    반환 키: window_pages(range), has_prev_group, prev_group_page, has_next_group, next_group_page.
    '이전'은 이전 그룹의 마지막 페이지, '다음'은 다음 그룹의 첫 페이지로 점프한다.
    """
    number = page_obj.number
    total = page_obj.paginator.num_pages
    group = (number - 1) // per_group
    start = group * per_group + 1
    end = min(start + per_group - 1, total)
    return {
        'window_pages': range(start, end + 1),
        'has_prev_group': start > 1,
        'prev_group_page': start - 1,   # 이전 그룹의 마지막 페이지
        'has_next_group': end < total,
        'next_group_page': end + 1,     # 다음 그룹의 첫 페이지
    }
