from django import forms
from .models import Review

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['category', 'title', 'content', 'rating' , 'image']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control search-input', 'placeholder': '제목을 적어주세요'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': '자세한 후기를 남겨주세요'}),
            'rating': forms.Select(choices=[(i, f"{i}점") for i in range(1, 6)], attrs={'class': 'form-select'}),
            
        }

class ReviewGeneralForm(forms.ModelForm):
    """메뉴 선택이 포함된 폼"""
    class Meta:
        model = Review
        fields = ['menu', 'category', 'title', 'content', 'rating' , 'image']
        widgets = {
            'menu': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control search-input', 'placeholder': '제목을 적어주세요'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': '자세한 후기를 남겨주세요'}),
            'rating': forms.Select(choices=[(i, f"{i}점") for i in range(1, 6)], attrs={'class': 'form-select'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }