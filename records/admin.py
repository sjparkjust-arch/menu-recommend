from django.contrib import admin

from .models import MealRecord


@admin.register(MealRecord)
class MealRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'date', 'meal', 'menu']
    list_filter = ['meal', 'date']
    search_fields = ['user__username', 'menu__name']
    autocomplete_fields = ['user', 'menu']
    date_hierarchy = 'date'
