from django import forms

from reviews.models import Review


class ReviewForm(forms.ModelForm):
    """후기 작성/수정 폼. 평점은 템플릿에서 별점(라디오)으로 렌더한다."""

    class Meta:
        model = Review
        fields = ['review_type', 'rating', 'content', 'image']
        widgets = {
            'review_type': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': '메뉴는 어떠셨나요?',
            }),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
