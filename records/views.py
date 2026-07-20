# records/views.py
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from .models import MealRecord
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

@login_required
def history_view(request):
    # 현재 로그인한 사용자의 전체 기록을 가져옵니다. 
    # (최신 날짜가 위로 오도록 -created_at 정렬을 추가해주면 더 좋습니다)
    records = MealRecord.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'records/history.html', {'records': records})

@login_required
def create_record(request):
    if request.method == 'POST':
        meal_type = request.POST.get('meal_type')
        food_name = request.POST.get('food_name', '').strip()
        rating = request.POST.get('rating', 5)
        comment = request.POST.get('comment', '').strip()
        
        # 💡 1. 폼에서 선택한 날짜 데이터를 가져옵니다.
        record_date = request.POST.get('record_date')

        if food_name:
            # 먼저 기록을 생성합니다.
            record = MealRecord.objects.create(
                user=request.user,
                meal_type=meal_type,
                food_name=food_name,
                rating=int(rating),
                comment=comment
            )
            
            # 💡 2. 폼에서 넘어온 날짜가 있다면, 생성된 기록의 날짜를 덮어씌우고 다시 저장합니다.
            if record_date:
                record.created_at = record_date
                record.save()

        # 💡 3. 등록 후 식사 히스토리가 아닌 '메인 대시보드'로 리다이렉트 시킵니다.
        return redirect(reverse('menus:dashboard'))
        
    return redirect(reverse('accounts:profile'))

@login_required
@require_POST
def delete_record(request, pk):
    """자신의 식사 기록을 삭제하는 함수"""
    # 현재 로그인한 사용자의 기록인지 한 번 더 확인(보안) 후 삭제합니다.
    record = get_object_or_404(MealRecord, pk=pk, user=request.user)
    record.delete()
    return redirect('records:history')