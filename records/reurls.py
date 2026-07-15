from django.urls import path
from . import views

app_name = 'records'

urlpatterns = [
    path('history/', views.history_view, name='history'),
    path('create/', views.create_record, name='create'),
]