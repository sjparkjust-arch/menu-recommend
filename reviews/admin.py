from django.contrib import admin

from .models import Review, ReviewLike


class ReviewLikeInline(admin.TabularInline):
    model = ReviewLike
    extra = 0
    autocomplete_fields = ['user']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'menu', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['user__username', 'menu__name', 'content']
    autocomplete_fields = ['user', 'menu']
    date_hierarchy = 'created_at'
    inlines = [ReviewLikeInline]


@admin.register(ReviewLike)
class ReviewLikeAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'review']
    search_fields = ['user__username', 'review__menu__name']
    autocomplete_fields = ['user', 'review']
