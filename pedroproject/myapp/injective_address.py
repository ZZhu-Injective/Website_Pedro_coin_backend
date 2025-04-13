import asyncio
import aiohttp
from pyinjective.async_client import AsyncClient
from pyinjective.client.model.pagination import PaginationOption
from pyinjective.composer import Composer
from pyinjective.core.network import Network


async def fetch_all_transactions(client, composer, address, batch_size=20):
    all_transactions = []
    offset = 0
    total = None
    retry_count = 0
    max_retries = 5
    
    print(f"\nStarting transaction fetch for {address}...")
    
    while retry_count < max_retries:
        try:
            print(f"Fetching batch {offset//batch_size + 1} (offset {offset})...")
            
            pagination = PaginationOption(limit=batch_size, skip=offset)
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                response = await client.fetch_account_txs(
                    address=address,
                    pagination=pagination,
                )
            
            if not response:
                print("Empty response received")
                retry_count += 1
                await asyncio.sleep(5)
                continue
                
            if 'paging' in response and total is None:
                total = int(response['paging']['total'])
                print(f"Total transactions to fetch: {total}")
            
            if 'data' in response:
                batch_count = len(response['data'])
                print(f"Found {batch_count} transactions in this batch")
                all_transactions.extend(response['data'])
                
                if (total is not None and len(all_transactions) >= total) or batch_count < batch_size:
                    print("Finished fetching all available transactions")
                    break
                    
                offset += batch_size
                await asyncio.sleep(2)  # Rate limiting
                retry_count = 0  # Reset on success
            else:
                print("No transaction data found in response")
                retry_count += 1
                await asyncio.sleep(5)
            
        except asyncio.TimeoutError:
            retry_count += 1
            print(f"\nTimeout occurred (attempt {retry_count}/{max_retries})")
            await asyncio.sleep(5)
        except aiohttp.ClientError as e:
            retry_count += 1
            print(f"\nConnection error (attempt {retry_count}/{max_retries}): {str(e)}")
            await asyncio.sleep(10)
        except Exception as e:
            retry_count += 1
            print(f"\nUnexpected error (attempt {retry_count}/{max_retries}):")
            print(f"Type: {type(e).__name__}")
            print(f"Details: {str(e)}")
            await asyncio.sleep(5)
    
    return all_transactions


async def main() -> None:
    print("\nStarting Injective transaction fetcher...")
    
    try:
        network = Network.mainnet()
        print(f"Network: {network.string()}")
        
        # Initialize client with custom session configuration
        client = AsyncClient(network)
        composer = Composer(network=network.string())
        
        address = "inj14rmguhlul3p30ntsnjph48nd5y2pqx2qwwf4u9"
        print(f"Address: {address}")
        
        all_transactions = await fetch_all_transactions(client, composer, address)
        
        print(f"\nTotal transactions fetched: {len(all_transactions)}")
        
        if not all_transactions:
            print("No transactions available or unable to fetch transactions")
            return
            
        # Process first 3 transactions as example
        print("\nSample transactions:")
        for tx in all_transactions[:3]:
            print(f"\nTx Hash: {tx.get('hash', 'N/A')}")
            print(f"Block Time: {tx.get('blockTimestamp', 'N/A')}")
            try:
                messages = composer.unpack_transaction_messages(transaction_data=tx)
                for i, msg in enumerate(messages, 1):
                    print(f"  Message {i}: {msg.get('type', 'N/A')}")
                    if 'value' in msg:
                        print(f"    From: {msg['value'].get('fromAddress', 'N/A')}")
                        print(f"    To: {msg['value'].get('toAddress', 'N/A')}")
                        if 'amount' in msg['value']:
                            for amt in msg['value']['amount']:
                                print(f"    Amount: {amt.get('amount', 'N/A')} {amt.get('denom', 'N/A')}")
            except Exception as e:
                print(f"Error processing message: {str(e)}")
                
    except Exception as e:
        print(f"\nFatal error in main: {type(e).__name__} - {str(e)}")
    finally:
        print("\nScript completed")


if __name__ == "__main__":
    print("Script initialization...")
    try:
        # Configure event loop policy for Windows if needed
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
    except Exception as e:
        print(f"\nTop-level error: {type(e).__name__} - {str(e)}")
    print("Script termination")