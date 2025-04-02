import asyncio
import json
from os import cpu_count
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial

def isolated_fetcher(address, tx_num):
    """Run in separate process to contain crashes"""
    async def _fetch():
        from pyinjective.async_client import AsyncClient
        from pyinjective.core.network import Network
        
        client = AsyncClient(Network.mainnet())
        try:
            response = await client.fetch_account_txs(
                address=address,
                from_number=tx_num,
                to_number=tx_num
            )
            
            if response and response.get('data'):
                first_tx = response['data'][0]
                return {
                    'tx': tx_num,
                    'status': 'success',
                    'data': {
                        'blockNumber': first_tx.get('blockNumber'),
                        'hash': first_tx.get('hash'),
                        'timestamp': first_tx.get('blockTimestamp')
                    }
                }
                
        except Exception as e:
            return {
                'tx': tx_num,
                'status': 'error',
                'error': str(e)
            }
            
        return {
            'tx': tx_num,
            'status': 'empty',
            'error': 'No data'
        }

    # Create new event loop for the subprocess
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_fetch())
    except Exception as e:
        result = {
            'tx': tx_num,
            'status': 'process_error',
            'error': str(e)
        }
    finally:
        loop.close()
    return result

class InjectiveWalletInfo:
    def __init__(self, address):
        self.address = address

    async def get_account_info(self, fetch_all=False):
        tx_range = range(1, 78)
        results = []
        
        # Use ProcessPoolExecutor to parallelize the work
        with ProcessPoolExecutor(max_workers=min(8, cpu_count())) as executor:
            # Prepare tasks
            futures = {
                executor.submit(isolated_fetcher, self.address, tx_num): tx_num 
                for tx_num in tx_range
            }
            
            # Process results as they complete
            for future in as_completed(futures):
                tx_num = futures[future]
                try:
                    result = future.result()
                    print(f"ℹ️ Result for tx {tx_num}: {result['status']}")
                    results.append(result)
                except Exception as e:
                    print(f"🔥 Error processing tx {tx_num}: {str(e)}")
                    results.append({
                        'tx': tx_num,
                        'status': 'process_error',
                        'error': str(e)
                    })
        
        print("\n✅ All transactions processed")
        return {
            'success_count': len([r for r in results if r.get('status') == 'success']),
            'error_count': len([r for r in results if r.get('status') != 'success']),
            'results': results
        }

async def main():
    wallet = InjectiveWalletInfo("inj1y43urcm8w0vzj74ys6pwl422qtd0a278hqchw8")
    results = await wallet.get_account_info(fetch_all=True)
    
    # Save results to file for analysis
    with open('tx_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("Results saved to tx_results.json")

if __name__ == "__main__":
    asyncio.run(main())