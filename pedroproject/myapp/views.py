from django.http import JsonResponse
from .injective_wallet_info import InjectiveWalletInfo

async def wallet_info_view(request, address):
    wallet = InjectiveWalletInfo(address)
    balance = await wallet.my_wallet()
    print(balance)
    return JsonResponse(balance, safe=False)
