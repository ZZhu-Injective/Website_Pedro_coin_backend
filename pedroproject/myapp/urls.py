from django.urls import path
from . import views

urlpatterns = [
    path('wallet_info_view/<str:address>/', views.wallet_info_view, name='wallet_info'),
]
