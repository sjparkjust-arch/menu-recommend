from django import forms
from .models import Review

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        # review_type(카테고리 라디오 버튼) 구조를 온전히 유지합니다.
        fields = ['review_type', 'rating', 'content', 'image']
        widgets = {
            'review_type': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5, 'class': 'form-control'}),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': '메뉴나 음식점은 어떠셨나요?',
            }),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        
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