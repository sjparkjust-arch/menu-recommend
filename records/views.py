# records/views.py
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from .models import MealRecord

@login_required
def history_view(request):
    # 현재 로그인한 사용자의 전체 기록을 가져옵니다.
    records = MealRecord.objects.filter(user=request.user)
    return render(request, 'records/history.html', {'records': records})

@login_required
def create_record(request):
    if request.method == 'POST':
        meal_type = request.POST.get('meal_type')
        food_name = request.POST.get('food_name', '').strip()
        rating = request.POST.get('rating', 5)
        comment = request.POST.get('comment', '').strip()

        if food_name:
            MealRecord.objects.create(
                user=request.user,
                meal_type=meal_type,
                food_name=food_name,
                rating=int(rating),
                comment=comment
            )
        # 등록 후 2번 히스토리 페이지로 리다이렉트 시킵니다.
        return redirect(reverse('records:history'))
        
    return redirect(reverse('accounts:profile'))