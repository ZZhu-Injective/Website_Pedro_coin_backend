import asyncio
from asyncio.log import logger
import json
import threading

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .Apedro_verify import PedroLogin
from .Apedro_talent_submission import discord_bot
from .Apedro_talent_confirmed import TalentDataReaders
from .Apedro_burned import PedroTokenBurnNotifier

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


def json_response(data, status=200):
    return JsonResponse(data, safe=False, status=status)

def home(request):
    return render(request, 'home.html')

async def verify(request, address):
    try:
        check = PedroLogin(address=address)
        info = await check.check()
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

def start_bot_in_thread():
    discord_bot.start()

if not hasattr(discord_bot, 'bot_thread'):
    discord_bot.bot_thread = threading.Thread(target=start_bot_in_thread, daemon=True)
    discord_bot.bot_thread.start()

@csrf_exempt
async def talent_submit(request, address):
    try:
        data = json.loads(request.body.decode('utf-8'))
        
        if data.get('walletAddress') != address:
            return JsonResponse({'error': 'Wallet mismatch'}, status=400)
        
        try:
            future = asyncio.run_coroutine_threadsafe(
                discord_bot.post_submission(data),
                discord_bot.loop
            )
            message = future.result(timeout=10)
            
            return JsonResponse({
                'success': True,
                'message_id': str(message.id)
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
async def talent(request):
    try:
        talent = TalentDataReaders()
        info = talent.read_approved_talents()
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

@csrf_exempt
async def token_burn_notification(request):
    if request.method != 'POST':
        return json_response({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        print(data)
        notifier = PedroTokenBurnNotifier()
        result = await notifier.process_burn_transaction(
            burn_data=data.get('burn_data', {}),
        )
        return json_response({'status': result})
    
    except Exception as e:
        logger.error(f"Burn notification error: {str(e)}", exc_info=True)
        return json_response({'error': 'Internal server error'}, status=500)















async def wallet_info_view(request, address):
    try:
        wallet = InjectiveWalletInfo(address)
        balance = await wallet.my_wallet()
        return json_response(balance)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

async def Injective_cw20(request, address):
    try:
        amount = InjectiveCw20(address)
        balance = await amount.fetch_cw20_balance()
        return json_response(balance)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

async def token_info_view(request):
    try:
        token = InjectiveTokenInfo()
        info = await token.circulation_supply()
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

async def token_holders_view(request, native_address, cw20_address):
    try:
        token = InjectiveHolders()
        info = await token.fetch_holders(cw20_address=cw20_address, native_address=native_address)
        return HttpResponse(info, content_type='application/x-msgpack')
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

async def nft_holders_view(request, cw20_address):
    try:
        nft = InjectiveHolders2()
        info = await nft.fetch_holder_nft(cw20_address=cw20_address)
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

async def check_wallet(request, address):
    try:
        check = InjectiveLogin(address=address)
        info = await check.check_total_balance()
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

async def native_holders(request, native_address):
    try:
        token = CoinDrop()
        info = await token.fetch_holders(native_address=native_address)
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

async def nft_holders(request, cw20):
    try:
        nft = NFTDrop()
        info = await nft.fetch_holder_nft(cw20_address=cw20)
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

async def checker(request, address):
    try:
        nft = XLSXReader()
        info = await nft.check(wallet=address)
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

async def scam(request):
    try:
        scam = ScamDataReader()
        info = scam.read_excel()
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

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
            accepted = await checker.send_scam_report(address, project, info, discord_name)
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
            
            notifier = TalentNotifier()
            
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