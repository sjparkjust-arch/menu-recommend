from django.contrib import admin
from .models import Review

# Review 모델만 깔끔하게 등록
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'user', 'rating', 'created_at')
    list_filter = ('category', 'rating')
    search_fields = ('title', 'content')