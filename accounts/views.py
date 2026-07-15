import re
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import get_user_model, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from records.models import MealRecord

User = get_user_model()


# Create your views here.
def index(request):
    return render(request, 'accounts/index.html')

def login_view(request):
    remembered_username = request.COOKIES.get('remembered_username', '')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        remember_id = request.POST.get('remember_id')

        errors = {}

        # 입력값 검증
        if not username:
            errors['username'] = '아이디를 입력하세요.'

        if not password:
            errors['password'] = '비밀번호를 입력하세요.'

        if errors:
            return render(
                request,
                'accounts/login.html',
                {
                    'errors': errors,
                    'username': username,
                    'remember_id': remember_id,
                }
            )

        # 아이디/비밀번호 인증
        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is None:
            errors['login'] = '아이디 또는 비밀번호가 올바르지 않습니다.'

            return render(
                request,
                'accounts/login.html',
                {
                    'errors': errors,
                    'username': username,
                    'remember_id': remember_id,
                }
            )

        # 로그인 성공: 세션 생성
        auth_login(request, user) # login에서 auth_login으로 변경

        response = redirect(reverse('accounts:index'))

        # 아이디 기억하기 체크 시 쿠키 저장
        if remember_id == 'on':
            response.set_cookie(
                'remembered_username',
                username,
                max_age=60 * 60 * 24 * 30
            )
        else:
            response.delete_cookie('remembered_username')

        return response

    return render(
        request,
        'accounts/login.html',
        {
            'username': remembered_username,
            'remember_id': 'on' if remembered_username else '',
        }
    )
    
def logout_view(request):
    logout(request)
    return redirect(reverse('accounts:login'))

#@login_required(login_url='accounts:login')
def profile(request):
    return render(request, 'accounts/profile.html')

def signup_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password1 = request.POST.get('password1', '').strip()
        password2 = request.POST.get('password2', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        email = request.POST.get('email', '').strip()
        
        errors = {}

        # 아이디 검증
        if not username:
            errors['username'] = '아이디를 입력하세요.'
        elif len(username) < 4:
            errors['username'] = '아이디는 4글자 이상 입력하세요.'
        # 추가된 로직: 영문, 숫자, 밑줄(_)만 허용하는 규칙
        elif not re.match(r'^[a-z0-9_]+$', username):
            errors['username'] = '아이디는 영문(소문자), 숫자, 밑줄(_)만 사용할 수 있습니다.'
        elif User.objects.filter(username=username).exists():
            errors['username'] = '이미 사용 중인 아이디입니다.'

        # 비밀번호 검증
        if not password1:
            errors['password1'] = '비밀번호를 입력하세요.'
        elif len(password1) < 8:
            errors['password1'] = '비밀번호는 8글자 이상 입력하세요.'
        # re.search를 사용해 영어 알파벳(a-z, A-Z)과 숫자(0-9)가 각각 하나라도 있는지 확인합니다.
        elif not (re.search(r'[a-zA-Z]', password1) and re.search(r'[0-9]', password1)):
            errors['password1'] = '비밀번호는 영문과 숫자를 모두 포함해야 합니다.'
        elif not re.match(r'^[a-zA-Z0-9]+$', password1):
            errors['password1'] = '비밀번호는 영문(소문자/대문자)과 숫자만 사용할 수 있습니다.'

        # 비밀번호 확인 검증
        if not password2:
            errors['password2'] = '비밀번호 확인을 입력하세요.'
        elif password1 != password2:
            errors['password2'] = '비밀번호가 서로 일치하지 않습니다.'

        # 검증 실패
        if errors:
            return render(
                request,
                'accounts/signup.html',
                {
                    'errors': errors,
                    'username': username,
                    'last_name': last_name,
                    'first_name': first_name,
                    'email': email,
                }
            )

        # 검증 성공
        User.objects.create_user(
            username=username,
            password=password1,
            last_name=last_name,
            first_name=first_name,
            email=email,
        )

        return redirect(reverse('accounts:login'))

    return render(request, 'accounts/signup.html')


def find_id(request):
    if request.method == 'POST':
        # 1. 사용자가 폼에 입력한 정보 가져오기
        last_name = request.POST.get('last_name', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        email = request.POST.get('email', '').strip()
        
        errors = {}

        # 2. 빈칸 검사
        if not last_name or not first_name:
            errors['name'] = '성명(성, 이름)을 모두 입력해주세요.'
        if not email:
            errors['email'] = '이메일을 입력해주세요.'

        # 3. 에러가 없다면 데이터베이스에서 회원 찾기
        if not errors:
            # User 모델에서 성, 이름, 이메일이 모두 일치하는 사람을 찾습니다. (.first()는 첫 번째 사람을 가져오라는 뜻)
            user = User.objects.filter(last_name=last_name, first_name=first_name, email=email).first()
            
            if user:
                # 일치하는 회원을 찾았을 때: HTML로 'found_username'이라는 정답을 보냅니다.
                return render(request, 'accounts/find_id.html', {'found_username': user.username})
            else:
                # 일치하는 회원이 없을 때
                errors['not_found'] = '입력하신 정보와 일치하는 계정이 없습니다.'

        # 4. 검증 실패 시 에러 메시지와 함께 폼을 다시 띄움
        return render(
            request, 
            'accounts/find_id.html', 
            {
                'errors': errors,
                'last_name': last_name,
                'first_name': first_name,
                'email': email,
            }
        )

    # 처음 페이지에 들어왔을 때(GET 요청) 빈 화면 띄우기
    return render(request, 'accounts/find_id.html')

def find_pw(request):
    if request.method == 'POST':
        # HTML 폼에서 보낸 '현재 단계(step)'를 확인합니다. 기본값은 '1'입니다.
        step = request.POST.get('step', '1')

        # ----------------------------------------------------
        # [1단계] 사용자 신원 확인 (아이디, 성, 이름, 이메일)
        # ----------------------------------------------------
        if step == '1':
            username = request.POST.get('username', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            email = request.POST.get('email', '').strip()
            
            errors = {}
            if not username:
                errors['username'] = '아이디를 입력해주세요.'
            if not last_name or not first_name:
                errors['name'] = '성명(성, 이름)을 모두 입력해주세요.'
            if not email:
                errors['email'] = '이메일을 입력해주세요.'

            # 에러가 없다면 DB에서 정보가 모두 일치하는 유저가 있는지 확인
            if not errors:
                user = User.objects.filter(username=username, last_name=last_name, first_name=first_name, email=email).first()
                if user:
                    # 일치하는 회원을 찾았다면, 비밀번호를 바꿀 수 있도록 reset_mode를 True로 보냅니다.
                    return render(request, 'accounts/find_pw.html', {'reset_mode': True, 'verified_username': username})
                else:
                    errors['not_found'] = '입력하신 정보와 일치하는 계정이 없습니다.'

            return render(request, 'accounts/find_pw.html', {
                'errors': errors,
                'username': username,
                'last_name': last_name,
                'first_name': first_name,
                'email': email,
            })

        # ----------------------------------------------------
        # [2단계] 새로운 비밀번호 입력받아 변경하기
        # ----------------------------------------------------
        elif step == '2':
            username = request.POST.get('verified_username') # 1단계에서 넘겨받은 아이디
            new_password = request.POST.get('new_password', '').strip()
            new_password_confirm = request.POST.get('new_password_confirm', '').strip()

            errors = {}
            if not new_password or not new_password_confirm:
                errors['password'] = '새 비밀번호를 모두 입력해주세요.'
            elif new_password != new_password_confirm:
                errors['password'] = '비밀번호가 서로 일치하지 않습니다.'
            elif len(new_password) < 8 or not (re.search(r'[a-zA-Z]', new_password) and re.search(r'[0-9]', new_password)):
                errors['password'] = '비밀번호는 8자 이상 영문과 숫자를 모두 포함해야 합니다.'

            # 에러가 없다면 최종적으로 비밀번호를 변경합니다.
            if not errors:
                user = User.objects.get(username=username)
                user.set_password(new_password) # 장고가 안전하게 암호화해서 저장해주는 핵심 명령어!
                user.save()
                return render(request, 'accounts/find_pw.html', {'success': True}) # 성공 화면 띄우기

            # 에러가 있다면 다시 재설정 폼을 띄웁니다.
            return render(request, 'accounts/find_pw.html', {
                'reset_mode': True,
                'verified_username': username,
                'errors': errors
            })

    # 처음 페이지에 들어왔을 때(GET 요청) 빈 화면 띄우기
    return render(request, 'accounts/find_pw.html')

@login_required
def delete_account(request):
    # 진짜 탈퇴 처리 (POST)
    if request.method == 'POST':
        user = request.user
        user.delete() # 데이터베이스에서 회원 정보 삭제
        return redirect(reverse('accounts:login')) # 로그인 페이지로 리다이렉트
        
    return redirect(reverse('accounts:profile'))

@login_required
def delete_account_confirm(request):
    # 회원탈퇴 확인 페이지 (GET)
    return render(request, 'accounts/delete_confirm.html')

@login_required
def profile(request):
    # 로그인한 사용자의 식사 기록 중 최신 5개만 가져옵니다.
    # records모델에서 데이터를 가져옴
    recent_records = MealRecord.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    context = {
        'meal_records': recent_records, # 템플릿의 {% for record in meal_records %} 와 매핑됩니다. / # 여기에 식사 기록 데이터 바인딩
    }
    return render(request, 'accounts/profile.html', context)