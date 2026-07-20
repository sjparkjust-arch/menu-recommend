from django import forms
from .models import Review

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        # review_type(라디오) + title('음식점 후기'일 때만 노출, JS 토글) 구조 유지.
        fields = ['review_type', 'title', 'rating', 'content', 'image']
        widgets = {
            'review_type': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '음식점 이름 등 후기 제목',
            }),
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5, 'class': 'form-control'}),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': '메뉴나 음식점은 어떠셨나요?',
            }),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        """음식점 후기(place)면 제목을 필수로, 음식 후기(food)면 제목을 버린다."""
        cleaned = super().clean()
        if cleaned.get('review_type') == Review.ReviewType.PLACE:
            if not (cleaned.get('title') or '').strip():
                self.add_error('title', '음식점 후기는 제목을 입력해 주세요.')
        else:
            cleaned['title'] = ''  # 음식 후기엔 제목 저장 안 함
        return cleaned
        
class ReviewGeneralForm(forms.ModelForm):
    """메뉴 선택이 포함된 폼"""
    class Meta:
        model = Review
        fields = ['menu', 'category', 'title', 'content', 'rating' , 'image']
        widgets = {
            'menu': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control search-input'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'rating': forms.Select(choices=[(i, f"{i}점") for i in range(1, 6)]),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }