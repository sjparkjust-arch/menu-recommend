from django.contrib import admin

from .models import Course, Cuisine, Menu, MenuAllergy


@admin.register(Cuisine)
class CuisineAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']


class MenuAllergyInline(admin.TabularInline):
    model = MenuAllergy
    extra = 1
    autocomplete_fields = ['allergy']


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'cuisine', 'course', 'meal_time']
    list_filter = ['cuisine', 'course', 'meal_time']
    search_fields = ['name', 'description']
    autocomplete_fields = ['cuisine', 'course']
    inlines = [MenuAllergyInline]


@admin.register(MenuAllergy)
class MenuAllergyAdmin(admin.ModelAdmin):
    list_display = ['id', 'menu', 'allergy']
    list_filter = ['allergy']
    search_fields = ['menu__name', 'allergy__name']
    autocomplete_fields = ['menu', 'allergy']
