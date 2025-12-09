from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    path('talent/', views.talent, name='talent'),
    path('marketplace/', views.marketplace, name='marketplace'),
    path('burn/', views.token_burn_notification, name='burn'),
    path('pedro_burn/', views.pedro_burn_info, name='pedro_burn'),
    path('check_pedro/<str:address>/', views.verify, name='verify'),
    path('talent_retrieve/<str:address>/', views.retrieve, name='retrieve'),
    path('talent_submit/<str:address>/', views.talent_submit, name='talent_submit'),
    path('talent_update/<str:address>/', views.talent_update, name='talent_update'),
    path('token_balances/<str:address>/', views.token_balances, name='token_balances'),
    path('walletinfo/<str:address>/', views.wallet_info, name='wallet_info'),










    path('wallet_info/<str:address>/', views.wallet_info_view, name='wallet_info'),
    path('cw20/<str:address>', views.Injective_cw20, name='cw20'),
    path('token_info/', views.token_info_view, name='token_info'),
    path('token_holders/<path:native_address>/<path:cw20_address>/', views.token_holders_view, name='token_holders'),
    path('nft_holders/<path:cw20_address>/', views.nft_holders_view, name='nft_holders'),
    path('check/<path:address>/', views.check_wallet, name='check_wallet'),
    path('naholders/<path:native_address>/', views.native_holders, name='native_holders'),
    path('nfholders/<path:cw20>/', views.nft_holders, name='nft_holders'),
    path('checker/<path:address>/', views.checker, name='checker'),
    path('inputscam/', views.scam_check, name='scam_check'),
    path('scam/', views.scam, name='scam'),
    path('talendsubmit', views.talent_check, name='talent_check'),
]