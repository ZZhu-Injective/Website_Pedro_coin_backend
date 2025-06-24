import asyncio
from typing import Dict
import aiohttp
import json
from pyinjective.core.network import Network
from pyinjective.async_client import AsyncClient
import backoff

class ShowToken:
    def __init__(self, address):
        self.address = address
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)
        self.session = aiohttp.ClientSession()
        self.sem = asyncio.Semaphore(10)

    @backoff.on_exception(backoff.expo, Exception, max_tries=5)
    async def fetch_bank_balances_with_retry(self):
        return await self.client.fetch_bank_balances(address=self.address)
    
    @backoff.on_exception(backoff.expo, Exception, max_tries=5)
    async def fetch_token_metadata_with_retry(self, denom: str):
        try:
            return await self.client.fetch_denom_metadata(denom=denom)
        except Exception:
            return None
    
    async def fetch_balances_with_metadata(self) -> Dict:
        balances_data = await self.fetch_bank_balances_with_retry()
        balances = balances_data.get('balances', [])
        
        tasks = [self.process_token_balance(balance) for balance in balances]
        token_infos = await asyncio.gather(*tasks)
        
        return {
            "address": self.address,
            "token_info": token_infos
        }
    
    async def process_token_balance(self, balance: Dict) -> Dict:
        async with self.sem:
            denom = balance['denom']
            amount = balance['amount']
            
            metadata_response = await self.fetch_token_metadata_with_retry(denom)

            print(metadata_response)
            
            token_info = {
                'symbol': denom.split('/')[-1] if '/' in denom else denom,
                'decimals': 18,
                'uri': None,
                'denom': denom,
                'amount': amount,
                'human_readable_amount': None,
                'name': 'Unknown',
                'description': 'No description available'
            }
            
            if metadata_response and 'metadata' in metadata_response:
                metadata = metadata_response['metadata']
                
                token_info.update({
                    'symbol': metadata.get('symbol', token_info['symbol']),
                    'uri': metadata.get('uri'),
                    'name': metadata.get('name', token_info['name']),
                    'description': metadata.get('description', token_info['description'])
                })
                
                if 'denomUnits' in metadata:
                    display_denom = metadata.get('display', '')
                    found_decimals = False
                    
                    for unit in metadata['denomUnits']:
                        if unit.get('denom') == display_denom:
                            exponent = unit.get('exponent')
                            if exponent is not None and exponent != 0:
                                token_info['decimals'] = exponent
                                found_decimals = True
                                break
                    
                    if not found_decimals:
                        max_exponent = 0
                        for unit in metadata['denomUnits']:
                            exponent = unit.get('exponent', 0)
                            if exponent > max_exponent:
                                max_exponent = exponent
                        if max_exponent > 0:
                            token_info['decimals'] = max_exponent
            
            token_info['human_readable_amount'] = self.format_amount(
                amount=amount,
                decimals=token_info['decimals']
            )
            
            return token_info
    
    def format_amount(self, amount: str, decimals: int) -> str:
        try:
            amount_int = int(amount)
            divisor = 10 ** decimals
            formatted = f"{amount_int / divisor:,.{max(2, decimals)}f}"
            if '.' in formatted:
                formatted = formatted.rstrip('0').rstrip('.') if formatted.endswith('.00') else formatted
            return formatted
        except:
            return amount
            
    async def close(self):
        await self.session.close()
