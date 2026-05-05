import asyncio
from asyncio.log import logger
import json
import threading
import time

from dotenv import load_dotenv

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

# Newest Version of the Backend
from .AApedro_verify_all_webpage import PedroLogin
from .ABpedro_talent_submission_update import talent_hub_bot
from .ABpedro_talent_web_confirmed import TalentDataReaders
from .ABpedro_talent_web_retrieve import TalentDatabase
from .ABpedro_marketplace_retrieve import MarketplaceDataReader

from .AApedro_burned_notif_discord import PedroTokenBurnNotifier
from .ACpedro_show_token_burn_web import TokenVerifier
from .ACpedro_info_token_burn_web import PedroTokenInfo
from .ADpedro_scam_checker_web import ScamScannerChecker

# Oldest Version of the Backend
from .injective_wallet_info import InjectiveWalletInfo
from .injective_token_info import InjectiveTokenInfo
from .injective_meme_holders import InjectiveHolders
from .injective_nft_holders import InjectiveHolders2
from .injective_login import InjectiveLogin
from .injective_cw20_token import InjectiveCw20
from .injective_coin_drop import CoinDrop
from .injective_nft_drop import NFTDrop
from .injective_checker import EligibilityChecker
from .injective_talented import TalentDataReader
from .injective_scam import ScamDataReader
from .injective_scam_check import ScamChecker
from .injective_talent_check import TalentNotifier

from datetime import datetime, timezone
from django.db import IntegrityError
from django.db.models import Sum
from .models import (
    GameLeaderboardEntry,
    GameUpgradeState,
    GameStealLog,
    GovernanceVoterSnapshot,
    GovernanceVote,
    GovernanceMonthResult,
    DashboardTxLog,
)
from .injective_game import GameVerifier, INJECTIVE_LCD
from .injective_governance import GovernanceVerifier, VALID_CHOICES
from .injective_dashboard_logs import DashboardLogVerifier, FEATURE_MEMOS

GAME_MAX_SCORE = 100_000_000
GAME_MAX_LEVEL = 1000

# Steal feature: amount = STEAL_BASE * 2^level. Default level 0 ⇒ 100 points.
STEAL_BASE_AMOUNT = 100
# Server-side cooldown so a spammed button can't drain a target instantly.
STEAL_COOLDOWN_SECONDS = 30 * 60


_NFT_COUNT_CACHE: dict[str, tuple[int, float]] = {}
_NFT_COUNT_TTL_SECONDS = 600  # 10 minutes — NFTs don't move every second.


# Crit table: (cumulative threshold, multiplier). Roll random in [0,1); the
# first row whose threshold is greater than the roll wins. Holding one NFT or
# a thousand makes no difference — only eligibility matters, by design.
_NFT_CRIT_TABLE = (
    (0.005, 10),  # 0.5% → 10×
    (0.035, 5),   # 3.0% → 5×  (cumulative 3.5%)
    (0.135, 2),   # 10.0% → 2× (cumulative 13.5%)
)


def _roll_nft_crit() -> int:
    """Returns 1 (no crit) or a crit multiplier (2/5/10). Caller should only
    invoke this when the user holds at least one Pedro NFT."""
    import random
    r = random.random()
    for threshold, mult in _NFT_CRIT_TABLE:
        if r < threshold:
            return mult
    return 1


def _fetch_pedro_nft_count(address: str) -> int:
    """Counts how many Pedro NFTs `address` owns by paging the standard CW721
    `tokens(owner)` query against the Injective LCD. Cached in-process for
    `_NFT_COUNT_TTL_SECONDS` so the game endpoints don't hammer LCD."""
    cached = _NFT_COUNT_CACHE.get(address)
    if cached and (time.time() - cached[1]) < _NFT_COUNT_TTL_SECONDS:
        return cached[0]

    import base64
    total = 0
    start_after: str | None = None
    # Safety cap: 20 pages × 100 = 2000 tokens. More than any realistic holder.
    for _ in range(20):
        query: dict = {'tokens': {'owner': address, 'limit': 100}}
        if start_after:
            query['tokens']['start_after'] = start_after
        encoded = base64.b64encode(
            json.dumps(query, separators=(',', ':')).encode()
        ).decode()
        url = (
            f"{INJECTIVE_LCD}/cosmwasm/wasm/v1/contract/"
            f"{PEDRO_NFT_CONTRACT}/smart/{encoded}"
        )
        try:
            import requests
            resp = requests.get(url, timeout=8)
            if resp.status_code != 200:
                break
            tokens = resp.json().get('data', {}).get('tokens', []) or []
        except Exception:
            break
        if not tokens:
            break
        total += len(tokens)
        if len(tokens) < 100:
            break
        start_after = tokens[-1]

    _NFT_COUNT_CACHE[address] = (total, time.time())
    return total


def _locked_name_for(address: str) -> str:
    """Returns the canonical display name for an address (the name used on
    its first leaderboard submission), or '' if the address has never
    submitted. Used both to enforce the lock on subsequent submits and to
    let the frontend prefill+disable the name field."""
    first = (
        GameLeaderboardEntry.objects
        .filter(address=address)
        .order_by('submitted_at', 'id')
        .values_list('name', flat=True)
        .first()
    )
    return first or ''

PEDRO_NFT_CONTRACT = 'inj1uq453kp4yda7ruc0axpmd9vzfm0fj62padhe0p'

# Mirrors the exclusion list in management/commands/snapshot_governance.py:
# burn address + Talis marketplace shouldn't get voting power.
GOVERNANCE_EXCLUDED_ADDRESSES = {
    'inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49',
    'inj1l9nh9wv24fktjvclc4zgrgyzees7rwdtx45f54',
}


def _current_month():
    return datetime.now(timezone.utc).strftime('%Y-%m')


def _run_async(coro_factory):
    """
    Run an async coroutine from a sync context. Handles both:
      - WSGI / pure sync Django: asyncio.run() in this thread.
      - ASGI / uvicorn / daphne: we're inside a running loop, so spin up a
        worker thread with its own loop.

    `coro_factory` must be a CALLABLE that returns a fresh coroutine — not a
    coroutine object. We defer instantiation until we're inside the right
    loop because libraries like gRPC bind their futures to whichever loop is
    running at construction/first-call time. Passing a pre-built coroutine
    creates futures attached to the parent loop, then awaiting them in the
    worker loop fails with "attached to a different loop".
    """
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop is None:
        return asyncio.run(coro_factory())

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro_factory())).result()


def _ensure_snapshot(month):
    """
    Lazy snapshot: the first request to governance endpoints in a new month
    triggers a fresh holder snapshot. Subsequent requests find rows already
    present and skip the on-chain fetch.

    Returns:
        None on success (or when a snapshot already exists)
        An error string when the lazy snapshot couldn't complete — useful for
        surfacing the reason in the API response so the UI / debugger can see
        why voting is still blocked.
    """
    if GovernanceVoterSnapshot.objects.filter(month=month).exists():
        return None

    try:
        from .injective_nft_holders import InjectiveHolders2

        async def _fetch():
            # Construct *inside* the loop so gRPC futures bind to it.
            return await InjectiveHolders2().fetch_holder_nft(PEDRO_NFT_CONTRACT)

        data = _run_async(_fetch)
    except Exception as e:
        logger.error(
            "Lazy snapshot for %s failed: %s", month, e, exc_info=True,
        )
        return f"on-chain fetch failed: {e}"

    rows = []
    for h in data.get('holders') or []:
        owner = h.get('owner')
        total = h.get('total')
        if not owner or owner in GOVERNANCE_EXCLUDED_ADDRESSES:
            continue
        try:
            count = int(total)
        except (TypeError, ValueError):
            continue
        if count <= 0:
            continue
        rows.append(GovernanceVoterSnapshot(month=month, address=owner, nft_count=count))

    if not rows:
        return "no holders returned by on-chain fetch"

    GovernanceVoterSnapshot.objects.bulk_create(
        rows,
        ignore_conflicts=True,
        batch_size=500,
    )
    return None

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

"""
Bot for Pedro Discord on Talent/Approval Channel. Where it show the talented to approve or reject.
"""

def start_bot():
    """Start the Discord bot in a separate thread"""
    if not hasattr(start_bot, 'bot_started') or not talent_hub_bot._bot_thread.is_alive():
        talent_hub_bot.start_bot_async()
        start_bot.bot_started = True
        logger.info("Discord bot started successfully")

start_bot()

"""
Show Pedro token burn, circulation and supply on the pedro website.
"""

async def pedro_burn_info(request):
    try:    
        pedro_token = PedroTokenInfo()
        result = await pedro_token.circulation_supply()
        print(result)
        return json_response(result)
            
    except Exception as e:
        logger.error(f"Error fetching pedro burn: {str(e)}", exc_info=True)
        return json_response({'error': str(e)}, status=500)


"""
Show wallet info, some important statistics you need.
"""

@csrf_exempt
def wallet_info(request, address):
    try:
        wallet_checker = ScamScannerChecker(address)
        df = wallet_checker.fetch_sequential_ranges()
        results = wallet_checker.analyze_transactions()
        
        print(results)

        return JsonResponse(results, safe=False)
        
    except Exception as e:
        logger.error(f"Error fetching walletinfo: {str(e)}", exc_info=True)


"""
Talent submission, retrieve and update views.
"""

@csrf_exempt
async def talent_submit(request, address):
    try:
        data = json.loads(request.body.decode('utf-8'))
        
        if not data.get('walletAddress'):
            return JsonResponse({'error': 'Missing wallet address'}, status=400)
            
        if data.get('walletAddress') != address:
            return JsonResponse({'error': 'Wallet mismatch'}, status=400)

        try:
            # Add submission to queue
            success = talent_hub_bot.submit_from_thread(data)
            
            if success:
                # Save to Excel
                excel_success = await talent_hub_bot._save_new_submission(data)
                
                if not excel_success:
                    return JsonResponse({
                        'error': 'Failed to save to Excel',
                        'success': False
                    }, status=500)
                
                # Start bot if not already running (in background thread)
                talent_hub_bot.start_bot_async()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Talent profile submitted successfully! It will be reviewed soon.'
                })
            else:
                return JsonResponse({
                    'error': 'Failed to submit to Discord',
                    'success': False
                }, status=500)
                
        except Exception as e:
            print(f"Discord submission error: {e}")
            return JsonResponse({'error': str(e)}, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Unexpected error: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)
























async def talent(request):
    try:
        talent = TalentDataReaders()
        info = await talent.read_approved_talents()
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)
    

def retrieve(request, address):
    try:
        db = TalentDatabase()
        
        result = db.get_talent_by_wallet(address)
        
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({
            "info": "no",
        }, status=500)
    
@csrf_exempt
async def talent_update(request, address):
    if request.method not in ['POST', 'PUT']:
        return JsonResponse(
            {'error': 'Only POST or PUT methods are allowed'}, 
            status=405
        )

    try:
        data = json.loads(request.body.decode('utf-8'))
        
        if data.get('walletAddress') != address:
            return JsonResponse(
                {'error': 'Wallet address does not match URL'}, 
                status=400
            )

        try:
            future = asyncio.run_coroutine_threadsafe(
                talent_hub_bot.post_update_request(data['walletAddress'], data),
                talent_hub_bot.loop
            )
            message = future.result(timeout=2)

            return JsonResponse({
                'success': True,
                'message_id': str(message.id),
                'message': 'Update request submitted successfully'
            })
        except asyncio.TimeoutError:
            return JsonResponse(
                {'error': 'Request timed out'}, 
                status=504
            )
        except Exception as e:
            logger.error(f"Error posting update: {str(e)}", exc_info=True)
            return JsonResponse(
                {'error': 'Failed to process update'}, 
                status=500
            )

    except json.JSONDecodeError:
        return JsonResponse(
            {'error': 'Invalid JSON data'}, 
            status=400
        )
    except Exception as e:
        logger.error(f"Error processing talent update: {str(e)}", exc_info=True)
        return JsonResponse(
            {'error': 'Internal server error'}, 
            status=500
        )

"""
Marketplace retrieval view.
"""

async def marketplace(request):
    try:
        market = MarketplaceDataReader()
        info = await market.read_approved_market()
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)
    






















@csrf_exempt
async def token_burn_notification(request):
    if request.method != 'POST':
        return json_response({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        notifier = PedroTokenBurnNotifier()
        result = await notifier.process_burn_transaction(
            burn_data=data.get('burn_data', {}),
        )
        return json_response({'status': result})
    
    except Exception as e:
        logger.error(f"Burn notification error: {str(e)}", exc_info=True)
        return json_response({'error': 'Internal server error'}, status=500)



async def token_balances(request, address):
    try:
        token_checker = TokenVerifier(address)
        
        try:
            result = await token_checker.get_balances()
            print(result)
            return json_response(result)
        finally:
            await token_checker.close()
            
    except Exception as e:
        logger.error(f"Error fetching token balances: {str(e)}", exc_info=True)
        return json_response({'error': str(e)}, status=500)
    

"""
Marketplace retrieval view.
"""




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

_TOKEN_INFO_CACHE = {'data': None, 'ts': 0.0}
_TOKEN_INFO_CACHE_TTL = 60  # seconds
_TOKEN_INFO_LOCK = asyncio.Lock()

async def token_info_view(request):
    now = time.time()
    cached = _TOKEN_INFO_CACHE['data']
    if cached is not None and now - _TOKEN_INFO_CACHE['ts'] < _TOKEN_INFO_CACHE_TTL:
        return json_response(cached)

    async with _TOKEN_INFO_LOCK:
        # Re-check after acquiring the lock so concurrent callers don't all refresh.
        now = time.time()
        cached = _TOKEN_INFO_CACHE['data']
        if cached is not None and now - _TOKEN_INFO_CACHE['ts'] < _TOKEN_INFO_CACHE_TTL:
            return json_response(cached)

        try:
            token = InjectiveTokenInfo()
            info = await token.circulation_supply()
            _TOKEN_INFO_CACHE['data'] = info
            _TOKEN_INFO_CACHE['ts'] = time.time()
            return json_response(info)
        except Exception as e:
            # Serve stale data if we have any, rather than a hard error.
            if cached is not None:
                return json_response(cached)
            return json_response({'error': str(e)}, status=500)

_HOLDERS_CACHE = {}            # (native, cw20) -> {'data': bytes, 'ts': float}
_HOLDERS_CACHE_TTL = 60        # seconds
_HOLDERS_LOCKS = {}            # (native, cw20) -> asyncio.Lock

def _holders_lock(key):
    lock = _HOLDERS_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _HOLDERS_LOCKS[key] = lock
    return lock

async def token_holders_view(request, native_address, cw20_address):
    cache_key = (native_address, cw20_address)
    now = time.time()
    cached = _HOLDERS_CACHE.get(cache_key)
    if cached is not None and now - cached['ts'] < _HOLDERS_CACHE_TTL:
        return HttpResponse(cached['data'], content_type='application/x-msgpack')

    async with _holders_lock(cache_key):
        cached = _HOLDERS_CACHE.get(cache_key)
        if cached is not None and time.time() - cached['ts'] < _HOLDERS_CACHE_TTL:
            return HttpResponse(cached['data'], content_type='application/x-msgpack')

        try:
            token = InjectiveHolders()
            info = await token.fetch_holders(cw20_address=cw20_address, native_address=native_address)
            _HOLDERS_CACHE[cache_key] = {'data': info, 'ts': time.time()}
            return HttpResponse(info, content_type='application/x-msgpack')
        except Exception as e:
            if cached is not None:
                return HttpResponse(cached['data'], content_type='application/x-msgpack')
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
        info = await EligibilityChecker().check(wallet=address)
        return json_response(info)
    except Exception as e:
        return json_response({'error': str(e)}, status=500)

async def scam(request):
    try:
        scam = ScamDataReader()
        info = await scam.read_excel()
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


@csrf_exempt
def game_submit_score(request):
    if request.method != 'POST':
        return json_response({'error': 'POST only'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return json_response({'error': 'Invalid JSON'}, status=400)

    address = (body.get('address') or '').strip()
    name = (body.get('name') or '').strip()[:64]
    score = body.get('score')
    tx_hash = (body.get('tx_hash') or '').strip()
    captcha_token = (body.get('captcha_token') or '').strip()

    if not address.startswith('inj1') or not name or not tx_hash:
        return json_response({'error': 'Missing or invalid fields'}, status=400)
    if not isinstance(score, int) or score < 1 or score > GAME_MAX_SCORE:
        return json_response(
            {'error': f'Score must be an integer in [1, {GAME_MAX_SCORE}]'},
            status=400,
        )

    remote_ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR', '')
    )
    ok, reason = GameVerifier.verify_captcha(captcha_token, remote_ip)
    if not ok:
        return json_response({'error': f'Captcha failed: {reason}'}, status=400)

    ok, reason = GameVerifier.verify_pedro_burn(tx_hash, address)
    if not ok:
        return json_response({'error': f'Burn verification failed: {reason}'}, status=400)

    # If the wallet has submitted before, force the original display name so
    # everyone sees consistent identity across submissions / steal targeting.
    locked = _locked_name_for(address)
    if locked:
        name = locked

    try:
        entry = GameLeaderboardEntry.objects.create(
            address=address,
            name=name,
            score=score,
            tx_hash=tx_hash,
            month=_current_month(),
        )
    except IntegrityError:
        return json_response({'error': 'Tx hash already used'}, status=409)

    return json_response({
        'ok': True,
        'id': entry.id,
        'month': entry.month,
        'name': entry.name,
    })


def game_leaderboard(request):
    month = _current_month()
    # Dedup by address — only keep the highest score per wallet. Because the
    # base queryset is already sorted by score desc, the first time we see an
    # address is also its highest entry for the month.
    qs = (
        GameLeaderboardEntry.objects
        .filter(month=month)
        .order_by('-score', 'submitted_at')
    )
    seen = set()
    deduped = []
    for entry in qs:
        if entry.address in seen:
            continue
        seen.add(entry.address)
        deduped.append(entry)
        if len(deduped) >= 50:
            break

    # Use the canonical (first-submitted) name for every row so a wallet that
    # has submitted under different names in the past still shows up under
    # its original identity.
    locked = {addr: _locked_name_for(addr) for addr in seen}
    return json_response({
        'month': month,
        'entries': [
            {
                'name': locked.get(e.address) or e.name,
                'address': e.address,
                'score': e.score,
                'tx_hash': e.tx_hash,
                'submitted_at': e.submitted_at.isoformat(),
            }
            for e in deduped
        ],
    })


def game_hall_of_fame(request):
    current = _current_month()
    months = (
        GameLeaderboardEntry.objects
        .exclude(month=current)
        .values_list('month', flat=True)
        .distinct()
        .order_by('-month')
    )
    winners = []
    for month in months:
        top = (
            GameLeaderboardEntry.objects
            .filter(month=month)
            .order_by('-score', 'submitted_at')
            .first()
        )
        if top:
            canonical = _locked_name_for(top.address) or top.name
            winners.append({
                'month': top.month,
                'name': canonical,
                'address': top.address,
                'score': top.score,
                'tx_hash': top.tx_hash,
            })
    return json_response({'winners': winners})


def game_upgrades_get(request, address):
    address = (address or '').strip()
    if not address.startswith('inj1'):
        return json_response({'error': 'Invalid address'}, status=400)
    locked_name = _locked_name_for(address)
    try:
        state = GameUpgradeState.objects.get(address=address)
        return json_response({
            'address': state.address,
            'click_level': state.click_level,
            'auto_level': state.auto_level,
            'steal_level': state.steal_level,
            'score': state.score,
            'last_steal_at': state.last_steal_at.isoformat() if state.last_steal_at else None,
            'locked_name': locked_name,
            'updated_at': state.updated_at.isoformat(),
        })
    except GameUpgradeState.DoesNotExist:
        return json_response({
            'address': address,
            'click_level': 0,
            'auto_level': 0,
            'steal_level': 0,
            'score': 0,
            'last_steal_at': None,
            'locked_name': locked_name,
            'updated_at': None,
        })


@csrf_exempt
def game_upgrades_set(request):
    if request.method != 'POST':
        return json_response({'error': 'POST only'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return json_response({'error': 'Invalid JSON'}, status=400)

    address = (body.get('address') or '').strip()
    click_level = body.get('click_level')
    auto_level = body.get('auto_level')
    steal_level = body.get('steal_level', 0)
    score = body.get('score', 0)

    if not address.startswith('inj1'):
        return json_response({'error': 'Invalid address'}, status=400)
    if not all(
        isinstance(x, int) and 0 <= x <= GAME_MAX_LEVEL
        for x in (click_level, auto_level, steal_level)
    ):
        return json_response({'error': 'Invalid levels'}, status=400)
    if not isinstance(score, int) or score < 0 or score > GAME_MAX_SCORE:
        return json_response({'error': 'Invalid score'}, status=400)

    GameUpgradeState.objects.update_or_create(
        address=address,
        defaults={
            'click_level': click_level,
            'auto_level': auto_level,
            'steal_level': steal_level,
            'score': score,
        },
    )
    return json_response({'ok': True})


def game_nft_status(request, address):
    """Returns the wallet's Pedro NFT count and whether they're crit-eligible.
    Holding one NFT enables the same crit chance as holding many — only
    eligibility matters. Cached server-side for ~10 min."""
    address = (address or '').strip()
    if not address.startswith('inj1'):
        return json_response({'error': 'Invalid address'}, status=400)
    count = _fetch_pedro_nft_count(address)
    return json_response({
        'address': address,
        'nft_count': count,
        'crit_eligible': count >= 1,
    })


@csrf_exempt
def game_steal(request):
    """
    Take points from another player. Steal amount is `STEAL_BASE_AMOUNT * 2^level`,
    where `level` comes from the attacker's server-stored steal_level (NOT from
    the client). Capped at the target's available score. Cooldown enforced
    server-side so the button can't be spammed.

    Body: { attacker: 'inj1...', target: 'inj1...' }
    """
    if request.method != 'POST':
        return json_response({'error': 'POST only'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return json_response({'error': 'Invalid JSON'}, status=400)

    attacker_addr = (body.get('attacker') or '').strip()
    target_addr = (body.get('target') or '').strip()

    if not attacker_addr.startswith('inj1') or not target_addr.startswith('inj1'):
        return json_response({'error': 'Invalid address'}, status=400)
    if attacker_addr == target_addr:
        return json_response({'error': "You can't steal from yourself"}, status=400)

    attacker, _ = GameUpgradeState.objects.get_or_create(address=attacker_addr)
    try:
        target = GameUpgradeState.objects.get(address=target_addr)
    except GameUpgradeState.DoesNotExist:
        return json_response({'error': 'Target has no game state'}, status=404)

    # Cooldown: time since last steal must exceed STEAL_COOLDOWN_SECONDS.
    now = datetime.now(timezone.utc)
    if attacker.last_steal_at:
        elapsed = (now - attacker.last_steal_at).total_seconds()
        if elapsed < STEAL_COOLDOWN_SECONDS:
            wait = int(STEAL_COOLDOWN_SECONDS - elapsed) + 1
            return json_response(
                {'error': f'Cooldown — try again in {wait}s'},
                status=429,
            )

    if target.score <= 0:
        return json_response(
            {'error': 'Target has no points to steal'},
            status=400,
        )

    base_amount = STEAL_BASE_AMOUNT * (2 ** attacker.steal_level)
    # NFT crit — Pedro NFT holders get random 2×/5×/10× steal hits. Holding
    # a single NFT is enough; holding more does NOT improve odds.
    nft_count = _fetch_pedro_nft_count(attacker_addr)
    crit_multiplier = _roll_nft_crit() if nft_count >= 1 else 1
    steal_amount = base_amount * crit_multiplier
    actual = min(steal_amount, target.score)

    target.score -= actual
    attacker.score = min(GAME_MAX_SCORE, attacker.score + actual)
    attacker.last_steal_at = now
    target.save(update_fields=['score', 'updated_at'])
    attacker.save(update_fields=['score', 'last_steal_at', 'updated_at'])

    GameStealLog.objects.create(
        attacker=attacker_addr,
        target=target_addr,
        amount=actual,
        attacker_level=attacker.steal_level,
    )

    return json_response({
        'ok': True,
        'stolen': actual,
        'crit': crit_multiplier,
        'attacker_score': attacker.score,
        'target_score': target.score,
        'cooldown_seconds': STEAL_COOLDOWN_SECONDS,
    })


def _tally_for_month(month):
    rows = (
        GovernanceVote.objects
        .filter(month=month)
        .values('choice')
        .annotate(points=Sum('points'))
    )
    tally = {c: 0 for c in VALID_CHOICES}
    for row in rows:
        tally[row['choice']] = int(row['points'] or 0)
    return tally


@csrf_exempt
def governance_vote(request):
    if request.method != 'POST':
        return json_response({'error': 'POST only'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return json_response({'error': 'Invalid JSON'}, status=400)

    address = (body.get('address') or '').strip()
    choice = (body.get('choice') or '').strip()
    tx_hash = (body.get('tx_hash') or '').strip()

    if not address.startswith('inj1') or not tx_hash:
        return json_response({'error': 'Missing or invalid fields'}, status=400)
    if choice not in VALID_CHOICES:
        return json_response(
            {'error': f'Invalid choice (allowed: {sorted(VALID_CHOICES)})'},
            status=400,
        )

    month = _current_month()
    _ensure_snapshot(month)

    try:
        snapshot = GovernanceVoterSnapshot.objects.get(month=month, address=address)
    except GovernanceVoterSnapshot.DoesNotExist:
        if not GovernanceVoterSnapshot.objects.filter(month=month).exists():
            return json_response(
                {'error': 'Voter snapshot for this month has not been taken yet'},
                status=409,
            )
        return json_response(
            {'error': 'You did not hold any Pedro NFTs at the start of this month'},
            status=403,
        )

    if GovernanceVote.objects.filter(month=month, address=address).exists():
        return json_response(
            {'error': 'You have already voted this month'},
            status=409,
        )

    ok, reason = GovernanceVerifier.verify_vote(tx_hash, address, month, choice)
    if not ok:
        return json_response({'error': f'Vote verification failed: {reason}'}, status=400)

    try:
        vote = GovernanceVote.objects.create(
            address=address,
            month=month,
            choice=choice,
            points=snapshot.nft_count,
            tx_hash=tx_hash,
        )
    except IntegrityError:
        return json_response(
            {'error': 'Tx hash already used or duplicate vote'},
            status=409,
        )

    return json_response({
        'ok': True,
        'id': vote.id,
        'month': month,
        'choice': choice,
        'points': vote.points,
    })


def governance_current(request):
    month = _current_month()
    snapshot_error = _ensure_snapshot(month)
    address = (request.GET.get('address') or '').strip()

    snapshot_count = GovernanceVoterSnapshot.objects.filter(month=month).count()
    total_power = (
        GovernanceVoterSnapshot.objects
        .filter(month=month)
        .aggregate(total=Sum('nft_count'))
    )['total'] or 0

    tally = _tally_for_month(month)
    voters = GovernanceVote.objects.filter(month=month).count()

    response = {
        'month': month,
        'snapshot_taken': snapshot_count > 0,
        'snapshot_error': snapshot_error,
        'eligible_voters': snapshot_count,
        'total_voting_power': int(total_power),
        'voters_so_far': voters,
        'tally': tally,
    }

    if address.startswith('inj1'):
        my = {
            'address': address,
            'eligible': False,
            'nft_count': 0,
            'has_voted': False,
            'choice': None,
            'tx_hash': None,
        }
        try:
            snap = GovernanceVoterSnapshot.objects.get(month=month, address=address)
            my['eligible'] = True
            my['nft_count'] = snap.nft_count
        except GovernanceVoterSnapshot.DoesNotExist:
            pass
        try:
            vote = GovernanceVote.objects.get(month=month, address=address)
            my['has_voted'] = True
            my['choice'] = vote.choice
            my['tx_hash'] = vote.tx_hash
        except GovernanceVote.DoesNotExist:
            pass
        response['me'] = my

    return json_response(response)


def governance_history(request):
    current = _current_month()
    months = (
        GovernanceVote.objects
        .exclude(month=current)
        .values_list('month', flat=True)
        .distinct()
        .order_by('-month')
    )
    out = []
    for month in months:
        tally = _tally_for_month(month)
        winner = max(tally, key=lambda c: tally[c]) if any(tally.values()) else None
        result = GovernanceMonthResult.objects.filter(month=month).first()
        out.append({
            'month': month,
            'winning_choice': (
                result.winning_choice if result and result.winning_choice else winner
            ),
            'tally': tally,
            'payout': {
                'tx_hash': result.payout_tx_hash if result else '',
                'amount': result.payout_amount if result else '',
                'notes': result.notes if result else '',
            } if result else None,
        })
    return json_response({'history': out})


@csrf_exempt
def dashboard_tx_log(request):
    if request.method != 'POST':
        return json_response({'error': 'POST only'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return json_response({'error': 'Invalid JSON'}, status=400)

    tx_hash = (body.get('tx_hash') or '').strip()
    feature = (body.get('feature') or '').strip()
    address = (body.get('address') or '').strip()
    summary = (body.get('summary') or '').strip()[:255]

    if not tx_hash or not address.startswith('inj1') or feature not in FEATURE_MEMOS:
        return json_response({'error': 'Missing or invalid fields'}, status=400)

    ok, reason = DashboardLogVerifier.verify(tx_hash, address, feature)
    if not ok:
        return json_response({'error': f'Tx verification failed: {reason}'}, status=400)

    try:
        DashboardTxLog.objects.create(
            tx_hash=tx_hash,
            feature=feature,
            address=address,
            summary=summary,
        )
    except IntegrityError:
        # Already logged — treat as success so the frontend doesn't surface an error.
        pass

    return json_response({'ok': True})


def dashboard_tx_recent(request, feature):
    if feature not in FEATURE_MEMOS:
        return json_response({'error': f"Unknown feature '{feature}'"}, status=400)
    qs = DashboardTxLog.objects.filter(feature=feature).order_by('-created_at')[:10]
    return json_response({
        'feature': feature,
        'entries': [
            {
                'tx_hash': e.tx_hash,
                'address': e.address,
                'summary': e.summary,
                'created_at': e.created_at.isoformat(),
            }
            for e in qs
        ],
    })