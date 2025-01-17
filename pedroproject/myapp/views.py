from django.http import JsonResponse
from .injective_wallet_info import InjectiveWalletInfo
from .injective_token_info import InjectiveTokenInfo
from .injective_meme_holders import InjectiveHolders
from .injective_nft_holders import InjectiveHolders2


async def wallet_info_view(request, address):
    wallet = InjectiveWalletInfo(address)
    balance = await wallet.my_wallet()
    return JsonResponse(balance, safe=False)

async def token_info_view(request):
    token = InjectiveTokenInfo()
    info = await token.circulation_supply()
    return JsonResponse(info, safe=False)

async def token_holders_view(request, native_address, cw20_address):
    token = InjectiveHolders()
    info = await token.fetch_holders(cw20_address=cw20_address, native_address=native_address)
    return JsonResponse(info, safe=False)

async def nft_holders_view(request, cw20_address):
    nft = InjectiveHolders2()
    info = await nft.fetch_holder_nft(cw20_address=cw20_address)
    return JsonResponse(info, safe=False)