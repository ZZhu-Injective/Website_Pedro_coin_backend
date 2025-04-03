import asyncio
import json
import traceback
import time
import sys
from typing import List, Dict, Any
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network
from pyinjective.client.model.pagination import PaginationOption

def handle_async_exceptions(loop, context):
    """Handle exceptions in async tasks"""
    exc = context.get('exception')
    if exc:
        print(f"Async error: {exc}", flush=True)
        traceback.print_exception(type(exc), exc, exc.__traceback__)
    else:
        print(f"Async warning: {context.get('message')}", flush=True)

async def fetch_transactions_with_retry(client, address, pagination, max_retries=3):
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1} of {max_retries}", flush=True)
            response = await client.fetch_account_txs(
                address=address,
                pagination=pagination
            )
            return response
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = (attempt + 1) * 2
            print(f"Retrying in {wait_time} seconds...", flush=True)
            await asyncio.sleep(wait_time)

class InjectiveWalletInfo:
    def __init__(self, address: str):
        self.address = address
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)
        
    async def fetch_all_transactions(self) -> List[Dict[str, Any]]:
        """Fetch all transactions in bulk with pagination"""
        all_transactions = []
        limit = 100
        skip = 0
        total_count = None
        
        print("Starting transaction fetch...", flush=True)
        
        while True:
            try:
                print(f"\nFetching {limit} transactions from skip {skip}...", flush=True)
                
                pagination = PaginationOption(limit=limit, skip=skip)
                response = await fetch_transactions_with_retry(
                    self.client, 
                    self.address, 
                    pagination
                )
                
                if not response or not response.get('data'):
                    print("No more data received", flush=True)
                    break
                    
                print(f"Received {len(response['data'])} transactions", flush=True)
                all_transactions.extend(response['data'])
                
                if total_count is None:
                    total_count = response.get('pagination', {}).get('total', 0)
                    print(f"Total transactions available: {total_count}", flush=True)
                
                skip += len(response['data'])
                if skip >= total_count:
                    print("Fetched all transactions", flush=True)
                    break
                    
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"\nCritical error: {e}", flush=True)
                traceback.print_exc()
                break
                
        return all_transactions

    async def get_account_info(self) -> Dict[str, Any]:
        """Get all account information including transactions"""
        print(f"\nFetching all transactions for address {self.address}...", flush=True)
        
        start_time = time.time()
        try:
            transactions = await self.fetch_all_transactions()
        except Exception as e:
            print(f"Fatal error in get_account_info: {e}", flush=True)
            traceback.print_exc()
            return {
                'success_count': 0,
                'error_count': 1,
                'error': str(e),
                'transactions': []
            }
        
        elapsed_time = time.time() - start_time
        
        # Process results
        success_count = len(transactions)
        error_count = 0
        
        print(f"\n✅ Fetched {success_count} transactions in {elapsed_time:.2f} seconds", flush=True)
        
        return {
            'success_count': success_count,
            'error_count': error_count,
            'transactions': sorted(transactions, key=lambda x: x.get('blockNumber', 0)),
            'stats': {
                'total_time': elapsed_time,
                'transactions_per_second': success_count / elapsed_time if elapsed_time > 0 else 0,
                'total_available': len(transactions)
            }
        }

async def main_task():
    try:
        wallet = InjectiveWalletInfo("inj1y43urcm8w0vzj74ys6pwl422qtd0a278hqchw8")
        print("Wallet created", flush=True)
        
        results = await wallet.get_account_info()
        print("Fetch completed", flush=True)
        
        with open('all_transactions.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Saved {results['success_count']} transactions", flush=True)
        
    except Exception as e:
        print(f"Main task failed: {e}", flush=True)
        traceback.print_exc()

def main():
    # Configure event loop policy for Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(handle_async_exceptions)
    
    try:
        print("Starting script...", flush=True)
        loop.run_until_complete(main_task())
    except KeyboardInterrupt:
        print("\nInterrupted by user", flush=True)
    except Exception as e:
        print(f"Fatal error: {e}", flush=True)
        traceback.print_exc()
    finally:
        print("Cleaning up...", flush=True)
        tasks = asyncio.all_tasks(loop)
        for t in tasks:
            t.cancel()
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        loop.close()
        print("Script ended", flush=True)
        input("Press Enter to close...")

if __name__ == "__main__":
    main()