import json

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .injective_wallet_info import InjectiveWalletInfo
from .injective_token_info import InjectiveTokenInfo
from .injective_meme_holders import InjectiveHolders
from .injective_nft_holders import InjectiveHolders2
from .injective_login import InjectiveLogin
from .injective_cw20_token import InjectiveCw20
from .injective_coin_drop import CoinDrop
from .injective_nft_drop import NFTDrop
from .injective_checker import XLSXReader
from .injective_talented import TalentDataReader
from .injective_scam import ScamDataReader
from .injective_scam_check import ScamChecker
from .injective_talent_check import TalentNotifier  


# Helper function to return JSON responses
def json_response(data, status=200):
    return JsonResponse(data, safe=False, status=status)

# Home view
def home(request):
    return render(request, 'home.html')

# Wallet info view
async def wallet_info_view(request, address):
    try:
        wallet = InjectiveWalletInfo(address)
        balance = await wallet.my_wallet()
        return json_response(balance)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

# CW20 token balance view
async def Injective_cw20(request, address):
    try:
        amount = InjectiveCw20(address)
        balance = await amount.fetch_cw20_balance()
        return json_response(balance)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

# Token info view
async def token_info_view(request):
    try:
        token = InjectiveTokenInfo()
        info = await token.circulation_supply()
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

# Token holders view
async def token_holders_view(request, native_address, cw20_address):
    try:
        token = InjectiveHolders()
        info = await token.fetch_holders(cw20_address=cw20_address, native_address=native_address)
        return HttpResponse(info, content_type='application/x-msgpack')
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

# NFT holders view
async def nft_holders_view(request, cw20_address):
    try:
        nft = InjectiveHolders2()
        info = await nft.fetch_holder_nft(cw20_address=cw20_address)
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

# Wallet balance check view
async def check_wallet(request, address):
    try:
        check = InjectiveLogin(address=address)
        info = await check.check_total_balance()
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

# Native token holders view
async def native_holders(request, native_address):
    try:
        token = CoinDrop()
        info = await token.fetch_holders(native_address=native_address)
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

# NFT holders view (alternative)
async def nft_holders(request, cw20):
    try:
        nft = NFTDrop()
        info = await nft.fetch_holder_nft(cw20_address=cw20)
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

# Wallet checker view
async def checker(request, address):
    try:
        nft = XLSXReader()
        info = await nft.check(wallet=address)
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

# Talented data view
async def talented(request):
    try:
        talent = TalentDataReader()
        info = talent.read_excel()
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

# Scam data view
async def scam(request):
    try:
        scam = ScamDataReader()
        info = scam.read_excel()
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

# Scam check view (updated to handle POST requests)
@csrf_exempt
async def scam_check(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            address = data.get('Address')
            project = data.get('Project')
            info = data.get('Info')
            discord_name = data.get('Discord')

            if not all([address, project, info, discord_name]):
                return json_response({'error': 'Missing required fields'}, status=400)

            checker = ScamChecker()
            print(checker)
            accepted = await checker._send_to_discord(address, project, info, discord_name, user_id_to_tag="everyone")
            return json_response(accepted)
        except json.JSONDecodeError:
            return json_response({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return json_response({'error': str(e)}, status=500)
    else:
        return json_response({'error': 'Only POST requests are allowed'}, status=405)
    

@csrf_exempt
async def talent_check(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            
            required_fields = ['name', 'profilePicture', 'role', 'continent', 
                             'education', 'description', 'injectiveRole', 'cvLink',
                             'transactionLink']
            
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Missing required fields: {", ".join(missing_fields)}'
                }, status=400)
            
            # Initialize TalentNotifier
            notifier = TalentNotifier()
            
            # Send notification to Discord
            notification_result = await notifier.send_talent_submission(data)
            
            if notification_result != "OK":
                return JsonResponse({
                    'status': 'error',
                    'message': 'Failed to send notification to Discord'
                }, status=500)

            return JsonResponse({
                'status': 'success',
                'message': 'Talent submission received and notification sent successfully',
                'data': {
                    'name': data.get('name'),
                    'role': data.get('role')
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data'
            }, status=400)
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST requests are allowed'
    }, status=405)