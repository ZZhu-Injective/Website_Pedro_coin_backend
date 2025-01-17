from django.urls import path
from . import views

urlpatterns = [
    path('wallet_info/<str:address>/', views.wallet_info_view, name='wallet_info'),
    path('token_info/', views.token_info_view, name='token_info'),
    path('token_holders/<path:native_address>/<path:cw20_address>/', views.token_holders_view, name='token_holders'),
    path('nft_holders/<path:cw20_address>/', views.nft_holders_view, name='nft_holders'),
]
