from django.http import JsonResponse
from .injective_wallet_info import InjectiveWalletInfo
from .injective_token_info import InjectiveTokenInfo

async def wallet_info_view(request, address):
    wallet = InjectiveWalletInfo(address)
    balance = await wallet.my_wallet()
    return JsonResponse(balance, safe=False)

async def token_info_view(request):
    token = InjectiveTokenInfo()
    info = await token.circulation_supply()
    return JsonResponse(info, safe=False)
