import asyncio
from asyncio.log import logger
import json
import os
import threading
import time

from dotenv import load_dotenv

from django.core.cache import cache
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

from datetime import datetime, timezone, timedelta
from django.db import IntegrityError
from django.db.models import Sum, F
from django.db.models.functions import Greatest
from .models import (
    GameLeaderboardEntry,
    GameUpgradeState,
    GameStealLog,
    GameMonthPayout,
    GovernanceVoterSnapshot,
    GovernanceVote,
    GovernanceMonthResult,
    SpecialProposal,
    SpecialVote,
    DashboardTxLog,
    RaffleTicket,
    RaffleFreeClaim,
    RafflePurchase,
    RaffleResult,
)
from .injective_game import GameVerifier, INJECTIVE_LCD, TENTH_PEDRO_WEI
from .injective_governance import GovernanceVerifier, VALID_CHOICES
from .injective_dashboard_logs import DashboardLogVerifier, FEATURE_MEMOS

# Effectively unlimited score. The only ceiling is the DB column type:
# `score` is a BigIntegerField, so the hard limit is the signed 64-bit max
# (9,223,372,036,854,775,807). We validate against it purely to stop an
# out-of-range value from crashing the database — players will never reach it.
GAME_MAX_SCORE = 9_223_372_036_854_775_807
GAME_MAX_LEVEL = 1000

# Raffle admins — comma-separated inj1 addresses in the RAFFLE_ADMIN_ADDRESSES
# env var. Only these wallets can call /raffle/admin/set_payout/.
RAFFLE_ADMIN_ADDRESSES = {
    a.strip().lower()
    for a in (os.getenv('RAFFLE_ADMIN_ADDRESSES', '') or '').split(',')
    if a.strip()
}

# Pedro admin wallet — allowed to create special proposals and record game payouts
PEDRO_ADMIN_ADDRESS = (
    os.getenv('PEDRO_ADMIN_ADDRESS') or 'inj1x6u08aa3plhk3utjk7wpyjkurtwnwp6dhudh0j'
).lower()

# Steal feature: amount = STEAL_BASE * 2^level. Default level 0 ⇒ 100 points.
STEAL_BASE_AMOUNT = 100
# Server-side cooldown so a spammed button can't drain a target instantly.
STEAL_COOLDOWN_SECONDS = 6 * 60 * 60
# Hard cap on steal upgrades — at level 12 the steal amount is already
# 100 * 2^12 = 409,600 base.
STEAL_MAX_LEVEL = 12


# Shared across all workers via the database cache (see settings.CACHES).
# Value is a dict[str, int] mapping inj1 address -> Pedro NFT count.
_NFT_HOLDERS_CACHE_KEY = 'pedro_nft_holders_v2'  # v2: value is {counts, fetched_at}
# Within this window the cached map is "fresh" and served as-is. Past it we
# still serve the (stale) map instantly but kick off a background refresh —
# stale-while-revalidate, so a user request never waits on the state scan.
_NFT_HOLDERS_FRESH_SECONDS = 600  # 10 minutes — NFTs don't move every second.
# How long the cache keeps the map around even when stale, so reads stay
# instant once it's been warmed once. The scheduled `refresh_nft_holders`
# command should run well inside this window to keep it fresh.
_NFT_HOLDERS_RETENTION_SECONDS = 86_400  # 24h
# Serializes refreshes so we never run the multi-page state scan twice at
# once (cold sync path and background revalidate share this lock).
_NFT_HOLDERS_LOCK = threading.Lock()


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


def _refresh_nft_holders() -> dict[str, int]:
    """Walks the full Pedro NFT contract state and rebuilds the
    address->count map. Called on cold cache or after TTL expiry. Cold
    refresh can take a few seconds — concurrent callers in the same worker
    block on the lock so only one refetch happens at a time.

    Uses the same approach as `AApedro_verify_all_webpage.fetch_holder_nft`
    (raw contract-state scan) because the standard CW721 `tokens(owner)`
    query doesn't return correct counts on this particular contract."""
    import base64
    import requests

    counts: dict[str, int] = {}
    next_key: str | None = None
    pages = 0

    while pages < 200:  # safety cap; supports up to ~200k state entries
        pages += 1
        params: dict[str, str] = {'pagination.limit': '1000'}
        if next_key:
            params['pagination.key'] = next_key
        url = (
            f"{INJECTIVE_LCD}/cosmwasm/wasm/v1/contract/"
            f"{PEDRO_NFT_CONTRACT}/state"
        )
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code != 200:
                logger.warning(
                    "NFT state fetch returned %s on page %s",
                    resp.status_code, pages,
                )
                break
            data = resp.json()
        except Exception as e:
            logger.warning("NFT state fetch failed on page %s: %s", pages, e)
            break

        for model in data.get('models') or []:
            try:
                value = model.get('value')
                if not value:
                    continue
                decoded = base64.b64decode(value).decode('utf-8')
                obj = json.loads(decoded)
            except Exception:
                continue
            owner = obj.get('owner') if isinstance(obj, dict) else None
            token_id = obj.get('token_id') if isinstance(obj, dict) else None
            # Token records have BOTH owner and token_id; other state entries
            # (config, minter, etc.) don't and get skipped.
            if owner and token_id:
                counts[owner] = counts.get(owner, 0) + 1

        next_key = (data.get('pagination') or {}).get('next_key')
        if not next_key:
            break

    # Write to the shared (database-backed) cache so all gunicorn workers see
    # the same value. Stored with a fetch timestamp so readers can tell a
    # fresh map from a stale one, and retained well past the freshness window
    # so reads keep hitting cache between refreshes.
    cache.set(
        _NFT_HOLDERS_CACHE_KEY,
        {'counts': counts, 'fetched_at': time.time()},
        _NFT_HOLDERS_RETENTION_SECONDS,
    )
    logger.info(
        "NFT holders refreshed: %s holders, %s tokens, %s pages",
        len(counts), sum(counts.values()), pages,
    )
    return counts


def _refresh_nft_holders_locked() -> dict[str, int]:
    """Run the refresh under the shared lock with a double-check, so a burst
    of cold-cache requests triggers only one state scan. Returns the map."""
    with _NFT_HOLDERS_LOCK:
        entry = cache.get(_NFT_HOLDERS_CACHE_KEY)
        # Another thread may have refreshed while we waited for the lock.
        if (
            isinstance(entry, dict)
            and 'counts' in entry
            and time.time() - entry.get('fetched_at', 0) <= _NFT_HOLDERS_FRESH_SECONDS
        ):
            return entry['counts']
        return _refresh_nft_holders()


def _trigger_async_holder_refresh() -> None:
    """Kick off a background refresh if one isn't already running. Never
    blocks the caller — this is the 'revalidate' half of stale-while-
    revalidate. If the lock is already held, a refresh is in flight, so we
    skip."""
    if not _NFT_HOLDERS_LOCK.acquire(blocking=False):
        return

    def _run():
        try:
            _refresh_nft_holders()
        except Exception as e:  # never let a background failure escape
            logger.warning("Background NFT holder refresh failed: %s", e)
        finally:
            _NFT_HOLDERS_LOCK.release()

    try:
        threading.Thread(
            target=_run, daemon=True, name='nft-holders-refresh',
        ).start()
    except Exception:
        _NFT_HOLDERS_LOCK.release()
        raise


def _fetch_pedro_nft_count(address: str) -> int:
    """Returns the number of Pedro NFTs the given address holds. Backed by
    Django's database cache so the value is shared across all workers.

    Stale-while-revalidate: a warmed cache always answers instantly. When the
    cached map is older than the freshness window we still return it right
    away and refresh in the background, so a user request only ever blocks on
    the (expensive, multi-page) state scan when the cache is completely cold —
    which the scheduled `refresh_nft_holders` command keeps from happening."""
    entry = cache.get(_NFT_HOLDERS_CACHE_KEY)
    if isinstance(entry, dict) and 'counts' in entry:
        if time.time() - entry.get('fetched_at', 0) > _NFT_HOLDERS_FRESH_SECONDS:
            _trigger_async_holder_refresh()
        return entry['counts'].get(address, 0)
    # Cold cache (first call after deploy / cache eviction) — block once to
    # fill it. Every subsequent read is served from cache.
    return _refresh_nft_holders_locked().get(address, 0)


def _locked_name_for(address: str) -> str:
    """Returns the canonical display name for an address (the name used on
    its first leaderboard submission), or '' if the address has never
    submitted. Cached on GameUpgradeState.locked_name so it survives the
    monthly leaderboard wipe."""
    return (
        GameUpgradeState.objects
        .filter(address=address)
        .values_list('locked_name', flat=True)
        .first()
        or ''
    )

PEDRO_NFT_CONTRACT = 'inj1uq453kp4yda7ruc0axpmd9vzfm0fj62padhe0p'

# Mirrors the exclusion list in management/commands/snapshot_governance.py:
# burn address + Talis marketplace shouldn't get voting power.
GOVERNANCE_EXCLUDED_ADDRESSES = {
    'inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49',
    'inj1l9nh9wv24fktjvclc4zgrgyzees7rwdtx45f54',
}


def _current_month():
    return datetime.now(timezone.utc).strftime('%Y-%m')


def _ensure_month_rolled_over(current_month: str) -> None:
    """Month-end housekeeping. For every past month still sitting in the live
    tables: snapshot its winner (highest score) into GameMonthPayout — the
    permanent Hall-of-Fame record — then wipe ALL three live game tables so
    the new month starts from a completely empty board:

        GameLeaderboardEntry · GameUpgradeState · GameStealLog

    Idempotent: once the live tables hold only the current month this is a
    no-op. It runs lazily on the first request of the new month, and can also
    be fired exactly at 00:00 UTC by the `rollover_game` management command
    (cron / Windows Task Scheduler)."""
    past_months = list(
        GameLeaderboardEntry.objects
        .exclude(month=current_month)
        .values_list('month', flat=True)
        .distinct()
    )
    if not past_months:
        return
    for month in past_months:
        top = (
            GameLeaderboardEntry.objects
            .filter(month=month)
            .order_by('-score', 'submitted_at', 'id')
            .first()
        )
        if top:
            payout, _ = GameMonthPayout.objects.get_or_create(month=month)
            # Only fill the winner snapshot the first time — subsequent calls
            # must not clobber it, and an admin-set payout_tx_hash must
            # survive untouched. Read the canonical name BEFORE the wipe
            # below deletes the GameUpgradeState row it lives on.
            if not payout.winning_address:
                canonical = _locked_name_for(top.address) or top.name
                payout.winning_address = top.address
                payout.winning_name = (canonical or '')[:64]
                payout.winning_score = top.score
                payout.winning_tx_hash = top.tx_hash
                payout.save(update_fields=[
                    'winning_address', 'winning_name',
                    'winning_score', 'winning_tx_hash', 'updated_at',
                ])
    # The winner(s) are now safely recorded in GameMonthPayout, so wipe every
    # live game table back to empty for the fresh month.
    GameLeaderboardEntry.objects.exclude(month=current_month).delete()
    GameUpgradeState.objects.exclude(current_month=current_month).delete()
    # GameStealLog has no month column — clear everything logged before the
    # current month began (any steal already logged in the new month stays).
    month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0,
    )
    GameStealLog.objects.filter(created_at__lt=month_start).delete()


def _reset_upgrade_state_if_needed(state, current_month: str) -> bool:
    """Wipes click/auto/steal levels, score, and steal cooldown when the
    state row is from a previous month. Preserves `locked_name` so wallet
    identity stays stable forever. Returns True if a reset happened."""
    if state.current_month == current_month:
        return False
    state.click_level = 0
    state.auto_level = 0
    state.steal_level = 0
    state.score = 0
    state.last_steal_at = None
    state.current_month = current_month
    state.save(update_fields=[
        'click_level', 'auto_level', 'steal_level',
        'score', 'last_steal_at', 'current_month', 'updated_at',
    ])
    return True


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

    # The game charges 0.1 $PEDRO per score submission (fractional burn).
    ok, reason = GameVerifier.verify_pedro_burn(
        tx_hash, address, expected_amount_wei=TENTH_PEDRO_WEI,
    )
    if not ok:
        return json_response({'error': f'Burn verification failed: {reason}'}, status=400)

    current_month = _current_month()
    _ensure_month_rolled_over(current_month)

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
            month=current_month,
        )
    except IntegrityError:
        return json_response({'error': 'Tx hash already used'}, status=409)

    # First submission for this wallet locks the display name forever — even
    # after monthly resets wipe their levels, the canonical name stays.
    state, _ = GameUpgradeState.objects.get_or_create(
        address=address,
        defaults={'current_month': current_month},
    )
    _reset_upgrade_state_if_needed(state, current_month)
    if not state.locked_name:
        state.locked_name = name[:64]
        state.save(update_fields=['locked_name', 'updated_at'])

    # Bank the submitted score into the wallet's persisted "saved" score so
    # the next page load reflects what was just submitted. Upgrades / steal
    # spend from this same field, so it has to stay in sync with leaderboard
    # submits. We never lower it here — a stale resubmission won't erase a
    # higher saved score earned via stealing.
    GameUpgradeState.objects.filter(address=address, score__lte=score).update(
        score=score,
    )

    return json_response({
        'ok': True,
        'id': entry.id,
        'month': entry.month,
        'name': entry.name,
    })


def game_leaderboard(request):
    month = _current_month()
    _ensure_month_rolled_over(month)
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
    # Trigger the lazy snapshot in case this is the first request of a new
    # month — otherwise the just-ended month's winner wouldn't appear yet.
    _ensure_month_rolled_over(current)
    payouts = (
        GameMonthPayout.objects
        .exclude(month=current)
        .exclude(winning_address='')
        .order_by('-month')
    )
    winners = [
        {
            'month': p.month,
            'name': _locked_name_for(p.winning_address) or p.winning_name,
            'address': p.winning_address,
            'score': p.winning_score,
            'tx_hash': p.winning_tx_hash,
            'payout_tx_hash': p.payout_tx_hash,
            'payout_nft_tx_hash': p.payout_nft_tx_hash,
            # The frontend uses this single flag to flip "pending" → "paid".
            'fully_paid': bool(p.payout_tx_hash and p.payout_nft_tx_hash),
        }
        for p in payouts
    ]
    return json_response({'winners': winners})


def game_upgrades_get(request, address):
    address = (address or '').strip()
    if not address.startswith('inj1'):
        return json_response({'error': 'Invalid address'}, status=400)
    current_month = _current_month()
    try:
        state = GameUpgradeState.objects.get(address=address)
        _reset_upgrade_state_if_needed(state, current_month)
        return json_response({
            'address': state.address,
            'click_level': state.click_level,
            'auto_level': state.auto_level,
            'steal_level': state.steal_level,
            'score': state.score,
            'last_steal_at': state.last_steal_at.isoformat() if state.last_steal_at else None,
            'locked_name': state.locked_name,
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
            'locked_name': '',
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
        for x in (click_level, auto_level)
    ):
        return json_response({'error': 'Invalid levels'}, status=400)
    if not (isinstance(steal_level, int) and 0 <= steal_level <= STEAL_MAX_LEVEL):
        return json_response({'error': 'Invalid steal level'}, status=400)
    if not isinstance(score, int) or score < 0 or score > GAME_MAX_SCORE:
        return json_response({'error': 'Invalid score'}, status=400)

    current_month = _current_month()
    state, created = GameUpgradeState.objects.get_or_create(
        address=address,
        defaults={
            'click_level': click_level,
            'auto_level': auto_level,
            'steal_level': steal_level,
            'score': score,
            'current_month': current_month,
        },
    )
    if not created:
        # If the row is from a prior month, the user's local state is stale
        # — wipe the row and ignore this sync. The frontend will pick up the
        # zeros on its next GET. Returning `reset: true` lets a future client
        # short-circuit its in-memory state too.
        if _reset_upgrade_state_if_needed(state, current_month):
            return json_response({'ok': True, 'reset': True})
        state.click_level = click_level
        state.auto_level = auto_level
        state.steal_level = steal_level
        state.score = score
        state.save(update_fields=[
            'click_level', 'auto_level', 'steal_level', 'score', 'updated_at',
        ])
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

    current_month = _current_month()
    _ensure_month_rolled_over(current_month)
    attacker, attacker_created = GameUpgradeState.objects.get_or_create(
        address=attacker_addr,
        defaults={'current_month': current_month},
    )
    if not attacker_created:
        _reset_upgrade_state_if_needed(attacker, current_month)
    try:
        target = GameUpgradeState.objects.get(address=target_addr)
    except GameUpgradeState.DoesNotExist:
        return json_response({'error': 'Target has no game state'}, status=404)
    _reset_upgrade_state_if_needed(target, current_month)

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

    # Reflect the steal on the public leaderboard immediately so a steal moves
    # both players' standings without anyone re-submitting (and re-burning).
    # We shift each existing current-month entry by exactly the stolen amount
    # — NOT by copying the live score, which also holds un-burned clicking
    # gains. We only UPDATE existing rows (never create): getting onto the
    # board still requires a paid 0.1 PEDRO burn, which supplies the unique
    # tx_hash an entry needs. `.update()` on an empty match is a harmless no-op,
    # so a player who never submitted simply isn't affected here.
    GameLeaderboardEntry.objects.filter(
        address=attacker_addr, month=current_month,
    ).update(score=F('score') + actual)
    GameLeaderboardEntry.objects.filter(
        address=target_addr, month=current_month,
    ).update(score=Greatest(F('score') - actual, 0))

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


def game_steal_log(request):
    """Today's steals (UTC), newest first, with player names resolved from each
    address's locked_name. Powers the game's 'Recent Steals' feed. The payload
    is capped; the client scrolls and searches within it."""
    today = datetime.now(timezone.utc).date()
    entries = list(
        GameStealLog.objects
        .filter(created_at__date=today)
        .order_by('-created_at')[:100]
    )

    addrs = set()
    for e in entries:
        addrs.add(e.attacker)
        addrs.add(e.target)
    name_map = dict(
        GameUpgradeState.objects
        .filter(address__in=addrs)
        .values_list('address', 'locked_name')
    )

    def name_for(addr):
        return (name_map.get(addr) or '').strip() or f'{addr[:6]}…{addr[-4:]}'

    return json_response({
        'count': len(entries),
        'steals': [
            {
                'attacker': name_for(e.attacker),
                'target': name_for(e.target),
                'amount': e.amount,
                'created_at': e.created_at.isoformat(),
            }
            for e in entries
        ],
    })


# ---------------------------------------------------------------------------
# Raffle
# ---------------------------------------------------------------------------

RAFFLE_PRIZE_LABEL = '1 INJ'
RAFFLE_COST_HOLDER_PEDRO = 5  # PEDRO per ticket if you hold ≥1 NFT
RAFFLE_COST_NON_HOLDER_PEDRO = 10  # PEDRO per ticket if you don't

# Lazy winner-picking runs on every raffle read. We use `secrets.choice` (CSPRNG)
# so the team can't be accused of cherry-picking even though picking is
# automatic. Same entropy source as the legacy `pick_raffle_winner` cron.
import secrets as _raffle_secrets


def _current_week() -> str:
    """ISO week string for the current UTC moment, e.g. '2026-W18'.
    Weeks roll over Monday 00:00 UTC."""
    now = datetime.now(timezone.utc)
    iso_year, iso_week, _ = now.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _ensure_raffle_weeks_finalized(current_week: str) -> None:
    """Lazy weekly draw: for every past ISO week that has tickets but no
    `RaffleResult` row yet, pick a winning ticket and persist it.

    Once a week is drawn its RaffleTicket rows are deleted — the winner and
    the ticket count live permanently on RaffleResult, so nothing visible is
    lost and the ticket table (one row PER TICKET) can't grow forever.

    RafflePurchase and RaffleFreeClaim are deliberately NOT deleted: their
    tx_hash rows are the replay ledger that stops an old burn from being
    credited again in a later week. They're one row per transaction rather
    than per ticket, so keeping them costs almost nothing.

    Idempotent — a second call is a no-op because the RaffleResult row now
    exists. Mirrors `_ensure_month_rolled_over` for the game.
    """
    past_weeks_with_tickets = list(
        RaffleTicket.objects
        .exclude(week=current_week)
        .values_list('week', flat=True)
        .distinct()
    )
    if not past_weeks_with_tickets:
        return
    already_drawn = set(
        RaffleResult.objects
        .filter(week__in=past_weeks_with_tickets)
        .values_list('week', flat=True)
    )
    for week in past_weeks_with_tickets:
        if week in already_drawn:
            continue
        ticket_ids = list(
            RaffleTicket.objects
            .filter(week=week)
            .values_list('id', 'address')
        )
        if not ticket_ids:
            continue
        winning_id, winning_address = _raffle_secrets.choice(ticket_ids)
        winning_name = _locked_name_for(winning_address)
        try:
            RaffleResult.objects.create(
                week=week,
                winning_address=winning_address,
                winning_ticket_id=winning_id,
                winning_name=winning_name,
                ticket_count=len(ticket_ids),
            )
        except IntegrityError:
            # Race with another concurrent request that just drew this week.
            # Whichever transaction got there first wins; we silently move on.
            continue

    # Re-query (the loop above may have just created results) and drop the
    # ticket rows for every past week that is now safely drawn. We filter on
    # RaffleResult rather than on `past_weeks_with_tickets` directly so a week
    # whose draw failed keeps its tickets and can still be drawn next time.
    drawn_weeks = set(
        RaffleResult.objects
        .filter(week__in=past_weeks_with_tickets)
        .values_list('week', flat=True)
    )
    if drawn_weeks:
        RaffleTicket.objects.filter(week__in=drawn_weeks).delete()


def _week_bounds_utc(week: str) -> tuple[datetime, datetime]:
    """Returns the [start, end) timestamps for the given ISO week."""
    year_str, week_str = week.split('-W')
    year, wk = int(year_str), int(week_str)
    # ISO weekday 1 == Monday. fromisocalendar handles ISO week boundaries.
    start = datetime.fromisocalendar(year, wk, 1).replace(tzinfo=timezone.utc)
    end = start + timedelta(days=7)
    return start, end


def _seconds_until_week_end(week: str) -> int:
    _, end = _week_bounds_utc(week)
    delta = (end - datetime.now(timezone.utc)).total_seconds()
    return max(0, int(delta))


def _ticket_cost_for(address: str) -> int:
    return (
        RAFFLE_COST_HOLDER_PEDRO
        if _fetch_pedro_nft_count(address) >= 1
        else RAFFLE_COST_NON_HOLDER_PEDRO
    )


def _serialize_my_tickets(address: str, week: str) -> list[dict]:
    return [
        {
            'id': t.id,
            'source': t.source,
            'created_at': t.created_at.isoformat(),
        }
        for t in RaffleTicket.objects
        .filter(week=week, address=address)
        .order_by('id')
    ]


def raffle_current(request, address):
    """Snapshot of the current week for one wallet — entries, totals, prize,
    ticket cost, free-claim eligibility."""
    address = (address or '').strip()
    if not address.startswith('inj1'):
        return json_response({'error': 'Invalid address'}, status=400)

    week = _current_week()
    # Whoever loads the page first after a Monday rollover triggers the draw
    # for last week. No more manual `pick_raffle_winner` cron needed.
    _ensure_raffle_weeks_finalized(week)
    nft_count = _fetch_pedro_nft_count(address)
    total_tickets = RaffleTicket.objects.filter(week=week).count()
    my_tickets = _serialize_my_tickets(address, week)
    already_claimed_free = RaffleFreeClaim.objects.filter(
        address=address, week=week,
    ).exists()
    cost_pedro = (
        RAFFLE_COST_HOLDER_PEDRO if nft_count >= 1 else RAFFLE_COST_NON_HOLDER_PEDRO
    )

    return json_response({
        'week': week,
        'seconds_until_end': _seconds_until_week_end(week),
        'prize': RAFFLE_PRIZE_LABEL,
        'nft_count': nft_count,
        'cost_pedro': cost_pedro,
        'free_tickets_available': nft_count if not already_claimed_free else 0,
        'free_already_claimed': already_claimed_free,
        'total_tickets_this_week': total_tickets,
        'my_tickets': my_tickets,
    })


@csrf_exempt
def raffle_claim_free(request):
    """One-shot per week per wallet: grants `nft_count` free raffle tickets.
    Requires a 1 $PEDRO burn from the claimer's wallet — proof of wallet
    control + Sybil resistance, even though the tickets themselves are free.

    Body: { address, tx_hash }
    """
    if request.method != 'POST':
        return json_response({'error': 'POST only'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return json_response({'error': 'Invalid JSON'}, status=400)

    address = (body.get('address') or '').strip()
    tx_hash = (body.get('tx_hash') or '').strip()
    if not address.startswith('inj1') or not tx_hash:
        return json_response({'error': 'Missing or invalid fields'}, status=400)

    # Replay protection — same tx_hash can't be reused across weeks/claims.
    if (
        RaffleFreeClaim.objects.filter(tx_hash=tx_hash).exists()
        or RafflePurchase.objects.filter(tx_hash=tx_hash).exists()
    ):
        return json_response({'error': 'Tx hash already used'}, status=409)

    week = _current_week()
    nft_count = _fetch_pedro_nft_count(address)
    if nft_count < 1:
        return json_response(
            {'error': 'Free tickets require at least one Pedro NFT'},
            status=400,
        )

    if RaffleFreeClaim.objects.filter(address=address, week=week).exists():
        return json_response(
            {'error': 'Free tickets already claimed for this week'},
            status=409,
        )

    ok, reason = GameVerifier.verify_pedro_burn(tx_hash, address, 1)
    if not ok:
        return json_response(
            {'error': f'Burn verification failed: {reason}'},
            status=400,
        )

    new_tickets = [
        RaffleTicket(
            week=week,
            address=address,
            source=RaffleTicket.SOURCE_FREE,
            tx_hash=tx_hash,
        )
        for _ in range(nft_count)
    ]
    RaffleTicket.objects.bulk_create(new_tickets)
    try:
        RaffleFreeClaim.objects.create(
            address=address,
            week=week,
            nft_count_at_claim=nft_count,
            tickets_granted=nft_count,
            tx_hash=tx_hash,
        )
    except IntegrityError:
        # Race lost — another request just consumed this tx_hash. Roll back.
        RaffleTicket.objects.filter(
            week=week, address=address, tx_hash=tx_hash, source=RaffleTicket.SOURCE_FREE,
        ).delete()
        return json_response({'error': 'Tx hash already used'}, status=409)

    return json_response({
        'ok': True,
        'tickets_granted': nft_count,
        'week': week,
        'my_tickets': _serialize_my_tickets(address, week),
    })


@csrf_exempt
def raffle_buy(request):
    """Buy paid tickets after burning the right amount of $PEDRO.

    Body: { address, tickets, tx_hash }
    Burn amount must equal `tickets * cost_per_ticket`. Cost is determined
    server-side from the buyer's current NFT holdings — clients can't
    haggle their way to the holder discount."""
    if request.method != 'POST':
        return json_response({'error': 'POST only'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return json_response({'error': 'Invalid JSON'}, status=400)

    address = (body.get('address') or '').strip()
    tickets = body.get('tickets')
    tx_hash = (body.get('tx_hash') or '').strip()

    if not address.startswith('inj1') or not tx_hash:
        return json_response({'error': 'Missing or invalid fields'}, status=400)
    if not isinstance(tickets, int) or tickets < 1 or tickets > 1000:
        return json_response(
            {'error': 'Tickets must be an integer between 1 and 1000'},
            status=400,
        )

    if RafflePurchase.objects.filter(tx_hash=tx_hash).exists():
        return json_response({'error': 'Tx hash already used'}, status=409)

    cost_per_ticket = _ticket_cost_for(address)
    expected_burn = tickets * cost_per_ticket

    ok, reason = GameVerifier.verify_pedro_burn(tx_hash, address, expected_burn)
    if not ok:
        return json_response(
            {'error': f'Burn verification failed: {reason}'},
            status=400,
        )

    week = _current_week()
    new_tickets = [
        RaffleTicket(
            week=week,
            address=address,
            source=RaffleTicket.SOURCE_PAID,
            tx_hash=tx_hash,
        )
        for _ in range(tickets)
    ]
    RaffleTicket.objects.bulk_create(new_tickets)
    try:
        RafflePurchase.objects.create(
            tx_hash=tx_hash,
            address=address,
            week=week,
            tickets=tickets,
            pedro_burned=expected_burn,
        )
    except IntegrityError:
        # Lost the race — another request just consumed this tx_hash.
        # Roll back the tickets we just created so they aren't double-credited.
        RaffleTicket.objects.filter(week=week, address=address, tx_hash=tx_hash).delete()
        return json_response({'error': 'Tx hash already used'}, status=409)

    return json_response({
        'ok': True,
        'tickets_added': tickets,
        'pedro_burned': expected_burn,
        'week': week,
        'my_tickets': _serialize_my_tickets(address, week),
    })


def raffle_history(request):
    """Past weekly winners + payout status."""
    _ensure_raffle_weeks_finalized(_current_week())
    rows = RaffleResult.objects.all()[:24]
    return json_response({
        'results': [
            {
                'week': r.week,
                'winning_address': r.winning_address,
                'winning_ticket_id': r.winning_ticket_id,
                'winning_name': r.winning_name,
                'ticket_count': r.ticket_count,
                'payout_tx_hash': r.payout_tx_hash,
                'picked_at': r.picked_at.isoformat(),
            }
            for r in rows
        ],
    })


@csrf_exempt
def raffle_admin_set_payout(request):
    """Admin-only: set or clear payout_tx_hash on a past raffle week.

    Authorization is by allowlist — admin_address in the request body must
    match one of the entries in the RAFFLE_ADMIN_ADDRESSES env var. The UI
    on the frontend gates which wallet can see the Edit button, but every
    request is still re-checked here.
    """
    if request.method != 'POST':
        return json_response({'error': 'POST only'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return json_response({'error': 'Invalid JSON'}, status=400)

    admin_address = (body.get('admin_address') or '').strip()
    week = (body.get('week') or '').strip()
    tx_hash = (body.get('tx_hash') or '').strip()

    if not admin_address.startswith('inj1'):
        return json_response({'error': 'Missing admin_address'}, status=400)

    # The main Pedro admin wallet is always authorized for raffle payouts,
    # in addition to anything listed in the RAFFLE_ADMIN_ADDRESSES env var.
    # This way the same wallet that signs game payouts can also sign raffle
    # payouts without needing extra server config.
    allowed = set(RAFFLE_ADMIN_ADDRESSES) | {PEDRO_ADMIN_ADDRESS}
    if admin_address.lower() not in allowed:
        return json_response({'error': 'Not authorized'}, status=403)

    if not week:
        return json_response({'error': 'Missing week'}, status=400)

    try:
        result = RaffleResult.objects.get(week=week)
    except RaffleResult.DoesNotExist:
        return json_response({'error': f'No raffle result for week {week}'}, status=404)

    result.payout_tx_hash = tx_hash[:128]
    result.save(update_fields=['payout_tx_hash'])

    return json_response({
        'ok': True,
        'week': result.week,
        'payout_tx_hash': result.payout_tx_hash,
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


def _ensure_governance_month_finalized(current_month: str) -> None:
    """Lazy month-end finalization: for every past month with votes but no
    `GovernanceMonthResult` row yet, compute the winning choice from the
    tallies and persist a result row. `payout_tx_hash` is left blank — admin
    fills it in via the UI later. Mirrors `_ensure_month_rolled_over` (game)
    and `_ensure_raffle_weeks_finalized` (raffle).
    """
    past_months = list(
        GovernanceVote.objects
        .exclude(month=current_month)
        .values_list('month', flat=True)
        .distinct()
    )
    if not past_months:
        return
    already_finalized = set(
        GovernanceMonthResult.objects
        .filter(month__in=past_months)
        .values_list('month', flat=True)
    )
    for month in past_months:
        if month in already_finalized:
            continue
        tally = _tally_for_month(month)
        winner = (
            max(tally, key=lambda c: tally[c]) if any(tally.values()) else ''
        )
        try:
            GovernanceMonthResult.objects.create(
                month=month,
                winning_choice=winner,
                points_liquidity=tally.get('liquidity', 0),
                points_buy_nfts=tally.get('buy_nfts', 0),
                points_giveaway=tally.get('giveaway', 0),
            )
        except IntegrityError:
            # Race with another concurrent request that just finalized this
            # month. Whichever transaction landed first wins; move on.
            continue


def governance_history(request):
    current = _current_month()
    _ensure_governance_month_finalized(current)
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
        payout_tx = result.payout_tx_hash if result else ''
        out.append({
            'month': month,
            'winning_choice': (
                result.winning_choice if result and result.winning_choice else winner
            ),
            'tally': tally,
            'payout': {
                'tx_hash': payout_tx,
                'amount': result.payout_amount if result else '',
                'notes': result.notes if result else '',
            } if result else None,
            'fully_paid': bool(payout_tx),
        })
    return json_response({'history': out})


def _options_for(proposal):
    """Ordered option labels, with a legacy yes/no fallback for old proposals."""
    opts = proposal.options if isinstance(proposal.options, list) else []
    opts = [str(o).strip() for o in opts if str(o).strip()]
    if opts:
        return opts
    return [proposal.choice_yes_label or 'Yes', proposal.choice_no_label or 'No']


def _choice_to_index(choice):
    """Map a stored vote choice to an option index. Handles both the new index
    strings ("0", "1", ...) and legacy 'yes'/'no'."""
    if choice is None:
        return None
    c = str(choice)
    if c.isdigit():
        return int(c)
    if c == 'yes':
        return 0
    if c == 'no':
        return 1
    return None


def _tally_for_special_proposal(proposal_id, num_options):
    """Points per option, as a list aligned to the proposal's options."""
    rows = (
        SpecialVote.objects
        .filter(proposal_id=proposal_id)
        .values('choice')
        .annotate(points=Sum('points'))
    )
    tally = [0] * max(num_options, 0)
    for row in rows:
        idx = _choice_to_index(row['choice'])
        if idx is not None and 0 <= idx < num_options:
            tally[idx] += int(row['points'] or 0)
    return tally


def special_proposals_list(request):
    from datetime import date
    address = (request.GET.get('address') or '').strip()
    today = date.today()
    proposals = SpecialProposal.objects.filter(is_active=True, end_date__gte=today)
    out = []
    for p in proposals:
        options = _options_for(p)
        tally = _tally_for_special_proposal(p.id, len(options))
        me = None
        if address.startswith('inj1'):
            month = _current_month()
            _ensure_snapshot(month)
            snap = GovernanceVoterSnapshot.objects.filter(month=month, address=address).first()
            sv = SpecialVote.objects.filter(proposal=p, address=address).first()
            me = {
                'address': address,
                'eligible': snap is not None,
                'nft_count': snap.nft_count if snap else 0,
                'has_voted': sv is not None,
                'choice': _choice_to_index(sv.choice) if sv else None,
                'tx_hash': sv.tx_hash if sv else None,
            }
        out.append({
            'id': p.id,
            'title': p.title,
            'description': p.description,
            'options': options,
            # Kept for backward-compatible clients; new UI uses `options`.
            'choice_yes_label': p.choice_yes_label,
            'choice_no_label': p.choice_no_label,
            'start_date': p.start_date.isoformat(),
            'end_date': p.end_date.isoformat(),
            'tally': tally,
            'total_points': sum(tally),
            'me': me,
        })
    return json_response({'proposals': out})


SPECIAL_PROPOSAL_BURN_PEDRO = 10_000


@csrf_exempt
def special_proposal_create(request):
    """Create a new special yes/no proposal.

    Authorization rules:
      • PEDRO_ADMIN_ADDRESS may create for free.
      • Any current-month NFT holder (per GovernanceVoterSnapshot) may create
        by burning SPECIAL_PROPOSAL_BURN_PEDRO $PEDRO and submitting the tx
        hash. Anti-spam gate — non-holders can't create even with a burn.
    """
    if request.method != 'POST':
        return json_response({'error': 'POST only'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return json_response({'error': 'Invalid JSON'}, status=400)

    # `admin_address` and `creator_address` are accepted as aliases — older
    # admin clients sent admin_address, new NFT-holder flow sends
    # creator_address.
    caller = (
        body.get('creator_address')
        or body.get('admin_address')
        or ''
    ).strip()
    if not caller.startswith('inj1'):
        return json_response({'error': 'Missing or invalid caller address'}, status=400)

    is_admin = caller.lower() == PEDRO_ADMIN_ADDRESS
    tx_hash = (body.get('tx_hash') or body.get('creation_tx_hash') or '').strip()

    if not is_admin:
        # Non-admin creators must be NFT holders this month AND burn the
        # creation fee.
        month = _current_month()
        _ensure_snapshot(month)
        snap = GovernanceVoterSnapshot.objects.filter(
            month=month, address=caller,
        ).first()
        if not snap or snap.nft_count < 1:
            return json_response(
                {'error': 'Only Pedro NFT holders can create proposals'},
                status=403,
            )
        if not tx_hash:
            return json_response(
                {
                    'error': (
                        f'Burn {SPECIAL_PROPOSAL_BURN_PEDRO} $PEDRO and submit '
                        f'the tx hash to create a proposal'
                    ),
                },
                status=400,
            )
        # Replay protection — reuse the same indexes the game/raffle use.
        if SpecialProposal.objects.filter(creation_tx_hash=tx_hash).exists():
            return json_response({'error': 'Tx hash already used'}, status=409)
        ok, reason = GameVerifier.verify_pedro_burn(
            tx_hash, caller, SPECIAL_PROPOSAL_BURN_PEDRO,
        )
        if not ok:
            return json_response(
                {'error': f'Burn verification failed: {reason}'},
                status=400,
            )

    title = (body.get('title') or '').strip()
    description = (body.get('description') or '').strip()
    end_date_str = (body.get('end_date') or '').strip()

    # New multi-option flow: `options` is a list of labels. Fall back to the
    # legacy yes/no labels if an old client doesn't send `options`.
    raw_options = body.get('options')
    if isinstance(raw_options, list):
        options = [str(o).strip()[:64] for o in raw_options if str(o).strip()]
    else:
        options = []
    if not options:
        yes_label = (body.get('choice_yes_label') or 'Yes').strip()[:64]
        no_label = (body.get('choice_no_label') or 'No').strip()[:64]
        options = [yes_label, no_label]

    if len(options) < 2:
        return json_response({'error': 'Provide at least 2 options'}, status=400)
    if len(options) > 8:
        return json_response({'error': 'A proposal can have at most 8 options'}, status=400)

    if not title or not description or not end_date_str:
        return json_response({'error': 'title, description and end_date are required'}, status=400)

    from datetime import date
    try:
        end_date = date.fromisoformat(end_date_str)
    except ValueError:
        return json_response({'error': 'end_date must be YYYY-MM-DD'}, status=400)

    if end_date < date.today():
        return json_response({'error': 'end_date must be in the future'}, status=400)

    proposal = SpecialProposal.objects.create(
        title=title[:200],
        description=description,
        options=options,
        # Keep the two label columns populated (from the first two options) so
        # any legacy reader still works.
        choice_yes_label=options[0],
        choice_no_label=options[1],
        is_active=True,
        start_date=date.today(),
        end_date=end_date,
        creator_address='' if is_admin else caller,
        creation_tx_hash='' if is_admin else tx_hash,
    )
    return json_response({
        'ok': True,
        'id': proposal.id,
        'title': proposal.title,
        'creator_address': proposal.creator_address,
        'creation_tx_hash': proposal.creation_tx_hash,
    })


@csrf_exempt
def special_proposal_vote(request):
    if request.method != 'POST':
        return json_response({'error': 'POST only'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return json_response({'error': 'Invalid JSON'}, status=400)

    address = (body.get('address') or '').strip()
    proposal_id = body.get('proposal_id')
    choice = ('' if body.get('choice') is None else str(body.get('choice'))).strip()
    tx_hash = (body.get('tx_hash') or '').strip()

    if not address.startswith('inj1') or not tx_hash:
        return json_response({'error': 'Missing or invalid fields'}, status=400)

    try:
        proposal = SpecialProposal.objects.get(id=proposal_id, is_active=True)
    except (SpecialProposal.DoesNotExist, TypeError, ValueError):
        return json_response({'error': 'Proposal not found or inactive'}, status=404)

    # `choice` is the option index ("0", "1", ...); legacy 'yes'/'no' still map.
    options = _options_for(proposal)
    choice_index = _choice_to_index(choice)
    if choice_index is None or not (0 <= choice_index < len(options)):
        return json_response({'error': 'Invalid option'}, status=400)

    from datetime import date
    if proposal.end_date < date.today():
        return json_response({'error': 'Voting has closed for this proposal'}, status=409)

    month = _current_month()
    _ensure_snapshot(month)
    try:
        snapshot = GovernanceVoterSnapshot.objects.get(month=month, address=address)
    except GovernanceVoterSnapshot.DoesNotExist:
        if not GovernanceVoterSnapshot.objects.filter(month=month).exists():
            return json_response({'error': 'Voter snapshot not yet taken'}, status=409)
        return json_response(
            {'error': 'You did not hold any Pedro NFTs at the start of this month'},
            status=403,
        )

    if SpecialVote.objects.filter(proposal=proposal, address=address).exists():
        return json_response({'error': 'You have already voted on this proposal'}, status=409)

    # Verify the on-chain memo using exactly the choice string the client
    # signed (`pedro-special:{id}:{choice}`), then store the canonical index.
    ok, reason = GovernanceVerifier.verify_special_vote(tx_hash, address, proposal.id, choice)
    if not ok:
        return json_response({'error': f'Vote verification failed: {reason}'}, status=400)

    try:
        vote = SpecialVote.objects.create(
            proposal=proposal,
            address=address,
            choice=str(choice_index),
            points=snapshot.nft_count,
            tx_hash=tx_hash,
        )
    except IntegrityError:
        return json_response({'error': 'Tx hash already used or duplicate vote'}, status=409)

    return json_response({'ok': True, 'id': vote.id, 'proposal_id': proposal.id, 'choice': choice_index, 'points': vote.points})


def special_proposals_history(request):
    from datetime import date
    past = SpecialProposal.objects.filter(end_date__lt=date.today()).order_by('-end_date')
    out = []
    for p in past:
        options = _options_for(p)
        tally = _tally_for_special_proposal(p.id, len(options))
        total = sum(tally)
        winner = None
        if total > 0:
            win_idx = max(range(len(tally)), key=lambda i: tally[i])
            winner = options[win_idx]
        out.append({
            'id': p.id,
            'title': p.title,
            'description': p.description,
            'options': options,
            'end_date': p.end_date.isoformat(),
            'tally': tally,
            'winner': winner,
        })
    return json_response({'history': out})


@csrf_exempt
def governance_admin_set_payout(request):
    """Admin-only: record the on-chain payout that executed the winning
    governance choice for a past month. Single tx hash, plus optional
    `payout_amount` (e.g. "5 INJ") and freeform `notes`. Same admin gating
    as game/raffle: only `PEDRO_ADMIN_ADDRESS` is authorized."""
    if request.method != 'POST':
        return json_response({'error': 'POST only'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return json_response({'error': 'Invalid JSON'}, status=400)

    admin_address = (body.get('admin_address') or '').strip().lower()
    if admin_address != PEDRO_ADMIN_ADDRESS:
        return json_response({'error': 'Not authorized'}, status=403)

    month = (body.get('month') or '').strip()
    if not month:
        return json_response({'error': 'Missing month'}, status=400)

    result, _ = GovernanceMonthResult.objects.get_or_create(month=month)
    update_fields = ['finalized_at']
    if body.get('payout_tx_hash') is not None:
        result.payout_tx_hash = (body.get('payout_tx_hash') or '').strip()[:128]
        update_fields.append('payout_tx_hash')
    if body.get('payout_amount') is not None:
        result.payout_amount = (body.get('payout_amount') or '').strip()[:64]
        update_fields.append('payout_amount')
    if body.get('notes') is not None:
        result.notes = (body.get('notes') or '').strip()
        update_fields.append('notes')
    result.save(update_fields=update_fields)

    return json_response({
        'ok': True,
        'month': result.month,
        'payout_tx_hash': result.payout_tx_hash,
        'payout_amount': result.payout_amount,
        'notes': result.notes,
        'fully_paid': bool(result.payout_tx_hash),
    })


@csrf_exempt
def game_admin_set_payout(request):
    if request.method != 'POST':
        return json_response({'error': 'POST only'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return json_response({'error': 'Invalid JSON'}, status=400)

    admin_address = (body.get('admin_address') or '').strip().lower()
    if admin_address != PEDRO_ADMIN_ADDRESS:
        return json_response({'error': 'Not authorized'}, status=403)

    month = (body.get('month') or '').strip()
    if not month:
        return json_response({'error': 'Missing month'}, status=400)

    # The prize is paid in two on-chain transactions: one for 5 INJ and one
    # for the 1 PEDRO NFT transfer. Both must be recorded before the Hall of
    # Fame considers the month fully paid out. Either field may be sent on
    # its own (e.g. admin pastes the INJ tx first, then the NFT tx later).
    # `tx_hash` is accepted as a legacy alias for the INJ tx.
    inj_tx = (
        body.get('payout_tx_hash')
        if body.get('payout_tx_hash') is not None
        else body.get('tx_hash')
    )
    nft_tx = body.get('payout_nft_tx_hash')

    payout, _ = GameMonthPayout.objects.get_or_create(month=month)
    update_fields = ['updated_at']
    if inj_tx is not None:
        payout.payout_tx_hash = (inj_tx or '').strip()[:128]
        update_fields.append('payout_tx_hash')
    if nft_tx is not None:
        payout.payout_nft_tx_hash = (nft_tx or '').strip()[:128]
        update_fields.append('payout_nft_tx_hash')
    payout.save(update_fields=update_fields)

    return json_response({
        'ok': True,
        'month': month,
        'payout_tx_hash': payout.payout_tx_hash,
        'payout_nft_tx_hash': payout.payout_nft_tx_hash,
        'fully_paid': bool(payout.payout_tx_hash and payout.payout_nft_tx_hash),
    })


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


# Activity features whose transactions live in their own models (game score
# burns, raffle ticket burns, governance votes / proposal-creation burns)
# rather than in DashboardTxLog. Surfaced in the same shape so the Activity
# feed can show them alongside converter/airdrop/launcher.
ONCHAIN_ACTIVITY_FEATURES = {'game', 'raffle', 'governance'}


def _onchain_activity_entries(feature):
    """Recent on-chain transactions for game / raffle / governance, newest
    first, in the DashboardTxLog entry shape: {tx_hash, address, summary,
    created_at}. Only rows that actually carry a tx hash are included."""
    rows = []  # (datetime, entry_dict)

    if feature == 'game':
        for e in GameLeaderboardEntry.objects.order_by('-submitted_at')[:15]:
            if not e.tx_hash:
                continue
            rows.append((e.submitted_at, {
                'tx_hash': e.tx_hash,
                'address': e.address,
                'summary': f'{e.name} submitted a score of {e.score:,} (burned 0.1 $PEDRO)',
                'created_at': e.submitted_at.isoformat(),
            }))

    elif feature == 'raffle':
        for p in RafflePurchase.objects.order_by('-created_at')[:15]:
            if not p.tx_hash:
                continue
            plural = 's' if p.tickets != 1 else ''
            rows.append((p.created_at, {
                'tx_hash': p.tx_hash,
                'address': p.address,
                'summary': f'Bought {p.tickets} raffle ticket{plural} (burned {p.pedro_burned:,} $PEDRO)',
                'created_at': p.created_at.isoformat(),
            }))
        for c in RaffleFreeClaim.objects.exclude(tx_hash__isnull=True).order_by('-claimed_at')[:15]:
            if not c.tx_hash:
                continue
            plural = 's' if c.tickets_granted != 1 else ''
            rows.append((c.claimed_at, {
                'tx_hash': c.tx_hash,
                'address': c.address,
                'summary': f'Claimed {c.tickets_granted} free raffle ticket{plural} (burned 1 $PEDRO)',
                'created_at': c.claimed_at.isoformat(),
            }))

    elif feature == 'governance':
        for v in GovernanceVote.objects.order_by('-voted_at')[:15]:
            if not v.tx_hash:
                continue
            rows.append((v.voted_at, {
                'tx_hash': v.tx_hash,
                'address': v.address,
                'summary': f'Voted "{v.choice}" in monthly governance',
                'created_at': v.voted_at.isoformat(),
            }))
        for sv in SpecialVote.objects.select_related('proposal').order_by('-voted_at')[:15]:
            if not sv.tx_hash:
                continue
            title = sv.proposal.title if sv.proposal_id else 'a proposal'
            rows.append((sv.voted_at, {
                'tx_hash': sv.tx_hash,
                'address': sv.address,
                'summary': f'Voted on proposal "{title}"',
                'created_at': sv.voted_at.isoformat(),
            }))
        for p in SpecialProposal.objects.exclude(creation_tx_hash='').order_by('-created_at')[:15]:
            if not p.creation_tx_hash:
                continue
            rows.append((p.created_at, {
                'tx_hash': p.creation_tx_hash,
                'address': p.creator_address,
                'summary': f'Created proposal "{p.title}" (burned 10,000 $PEDRO)',
                'created_at': p.created_at.isoformat(),
            }))

    rows.sort(key=lambda r: r[0], reverse=True)
    return [entry for _, entry in rows[:10]]


def dashboard_tx_recent(request, feature):
    if feature in ONCHAIN_ACTIVITY_FEATURES:
        return json_response({
            'feature': feature,
            'entries': _onchain_activity_entries(feature),
        })
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