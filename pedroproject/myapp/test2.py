import asyncio
from pyinjective.async_client import AsyncClient
from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import Network

async def fetch_transactions(address: str, limit: int = 50, max_transactions: int = 1000):
    network = Network.mainnet()
    client = AsyncClient(network)
    all_transactions = []
    skip = 0
    
        while len(all_transactions) < max_transactions:
            try:
                # Add timeout to prevent hanging
                pagination = PaginationOption(limit=limit, skip=skip)
                transactions_response = await asyncio.wait_for(
                    client.fetch_account_txs(address=address, pagination=pagination),
                    timeout=30
                )
                
                if not transactions_response.data:
                    break
                    
                for tx in transactions_response.data:
                    # Create a simplified transaction object
                    simplified_tx = {
                        'height': tx.get('height'),
                        'hash': tx.get('hash'),
                        'timestamp': tx.get('block_unix_timestamp'),
                        'messages': tx.get('messages'),
                        'gas_used': tx.get('gasUsed'),
                        'gas_wanted': tx.get('gasWanted'),
                        'fee': tx.get('gasFee'),
                        'tx_type': tx.get('txType'),
                        'memo': tx.get('memo'),
                        'code': tx.get('code')
                    }
                    all_transactions.append(simplified_tx)
                
                print(f"Fetched {len(transactions_response.data)} transactions (total: {len(all_transactions)})")
                
                if len(transactions_response.data) < limit:
                    break
                    
                skip += limit
                
            except asyncio.TimeoutError:
                print(f"Timeout after {skip} transactions, continuing...")
                skip += limit
                continue
            except Exception as e:
                print(f"Error fetching transactions: {e}")
                break
                
        
    return all_transactions

async def main():
    address = "inj14rmguhlul3p30ntsnjph48nd5y2pqx2qwwf4u9"
    try:
        transactions = await fetch_transactions(address)
        print(f"\nFetched {len(transactions)} total transactions")
        
        # Optionally save to file if you have many transactions
        with open('transactions.json', 'w') as f:
            import json
            json.dump(transactions, f, indent=2)
            
    except Exception as e:
        print(f"Main error: {e}")

if __name__ == "__main__":
    # Use asyncio.run() which is the preferred way in Python 3.7+
    asyncio.run(main())