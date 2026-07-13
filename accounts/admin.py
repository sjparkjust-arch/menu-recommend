from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Allergy, User, UserAllergy, UserPreference

admin.site.register(User, UserAdmin)


@admin.register(Allergy)
class AllergyAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']


@admin.register(UserAllergy)
class UserAllergyAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'allergy']
    list_filter = ['allergy']
    search_fields = ['user__username', 'allergy__name']
    autocomplete_fields = ['user', 'allergy']


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'cuisine', 'score']
    list_filter = ['cuisine', 'score']
    search_fields = ['user__username', 'cuisine__name']
    autocomplete_fields = ['user', 'cuisine']
