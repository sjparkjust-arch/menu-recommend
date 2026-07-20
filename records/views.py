from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from .models import MealRecord
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

@login_required
def history_view(request):
    records = MealRecord.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'records/history.html', {'records': records})

@login_required
def create_record(request):
    if request.method == 'POST':
        meal_type = request.POST.get('meal_type')
        food_name = request.POST.get('food_name', '').strip()
        rating = request.POST.get('rating', 5)
        comment = request.POST.get('comment', '').strip()
        record_date = request.POST.get('record_date')

        if food_name:
            # 1. 먼저 현재 시간 기준으로 기록을 생성합니다.
            record = MealRecord.objects.create(
                user=request.user,
                meal_type=meal_type,
                food_name=food_name,
                rating=int(rating),
                comment=comment
            )
            
            # 2. 폼에서 넘어온 날짜가 있다면, 강제 저장(update)을 통해 덮어씌웁니다. (시간은 낮 12시로 고정)
            if record_date:
                MealRecord.objects.filter(pk=record.pk).update(created_at=f"{record_date} 12:00:00")

        # 3. 등록 완료 후 식사 히스토리가 아닌 메인 대시보드로 돌아갑니다.
        return redirect('menus:dashboard')
        
    return redirect('accounts:profile')

@login_required
@require_POST
def delete_record(request, pk):
    record = get_object_or_404(MealRecord, pk=pk, user=request.user)
    record.delete()
    return redirect('records:history')