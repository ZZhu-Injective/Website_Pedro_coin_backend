import asyncio
import aiohttp
import json
import os
from typing import Dict, List, Optional
from pyinjective.core.network import Network
from pyinjective.async_client import AsyncClient
import backoff

class TokenVerifier:
    """Token verification system with logo support"""
    
    def __init__(self, address: str):
        self.address = address
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)
        self.session = aiohttp.ClientSession()
        self.semaphore = asyncio.Semaphore(10)
        self.verified_tokens = self._load_verified_tokens()

    def _load_verified_tokens(self) -> List[Dict]:
        possible_filenames = [
            'ACpedro_verified_token.json',
            'ACpedro_verifeid_token.json',
            os.path.join('pedroproject', 'myapp', 'ACpedro_verified_token.json'),
            os.path.join(os.path.dirname(__file__), 'ACpedro_verified_token.json')
        ]
        
        for filename in possible_filenames:
            try:
                if os.path.exists(filename):
                    print(f"Loading verified tokens from: {filename}")
                    with open(filename, 'r', encoding='utf-8') as f:
                        tokens = json.load(f)
                        if not isinstance(tokens, list):
                            print(f"Warning: Expected list in {filename}, got {type(tokens)}")
                            continue
                        return tokens
            except Exception as e:
                print(f"Error loading {filename}: {str(e)}")
                continue
        
        print("Warning: Could not load verified tokens file")
        return []

    @backoff.on_exception(backoff.expo, Exception, max_tries=5)
    async def _fetch_balances(self) -> Dict:
        """Fetch balances from the blockchain"""
        return await self.client.fetch_bank_balances(address=self.address)

    def _find_verified_token(self, denom: str, symbol: str) -> Optional[Dict]:        
        for token in self.verified_tokens:
            if token.get('denom') == denom:
                return token
        
        clean_symbol = symbol.lower().strip()
        for token in self.verified_tokens:
            token_symbol = token.get('symbol', '').lower().strip()
            override_symbol = token.get('overrideSymbol', '').lower().strip()
            
            if token_symbol == clean_symbol or override_symbol == clean_symbol:
                print(f"Symbol match found: {token.get('symbol')} (input: {symbol})")
                return token
        
        if 'factory/' in denom:
            last_part = denom.split('/')[-1]
            for token in self.verified_tokens:
                if token.get('denom', '').endswith(last_part):
                    print(f"Partial denom match found: {token.get('symbol')}")
                    return token
        
        print("No matching verified token found")
        return None

    async def _process_token(self, balance: Dict) -> Dict:
        async with self.semaphore:
            denom = balance['denom']
            amount = balance['amount']
            base_symbol = denom.split('/')[-1] if '/' in denom else denom
            
            verified_token = self._find_verified_token(denom, base_symbol)
            
            if verified_token:
                return {
                    'symbol': verified_token.get('overrideSymbol', verified_token.get('symbol', base_symbol)),
                    'decimals': verified_token.get('decimals', 18),
                    'denom': denom,
                    'amount': amount,
                    'human_readable_amount': self._format_amount(amount, verified_token.get('decimals', 18)),
                    'name': verified_token.get('name', 'Unknown'),
                    'logo': verified_token.get('logo'),
                    'is_verified': True,
                    'source': 'verified_list'
                }
            
            try:
                metadata = await self._fetch_token_metadata(denom)
                if metadata and 'metadata' in metadata:
                    metadata = metadata['metadata']
                    decimals = self._extract_decimals(metadata)
                    return {
                        'symbol': metadata.get('symbol', base_symbol),
                        'decimals': decimals,
                        'denom': denom,
                        'amount': amount,
                        'human_readable_amount': self._format_amount(amount, decimals),
                        'name': metadata.get('name', 'Unknown'),
                        'is_verified': False,
                        'source': 'chain_metadata'
                    }
            except Exception as e:
                print(f"Error fetching metadata for {denom}: {str(e)}")
            
            return {
                'symbol': base_symbol,
                'decimals': 18,
                'denom': denom,
                'amount': amount,
                'human_readable_amount': self._format_amount(amount, 18),
                'name': 'Unknown',
                'is_verified': False,
                'source': 'default_values'
            }

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    async def _fetch_token_metadata(self, denom: str) -> Optional[Dict]:
        try:
            return await self.client.fetch_denom_metadata(denom=denom)
        except Exception as e:
            print(f"Metadata fetch failed for {denom}: {str(e)}")
            return None

    def _extract_decimals(self, metadata: Dict) -> int:
        if 'denomUnits' not in metadata:
            return 18
            
        display_denom = metadata.get('display', '')
        for unit in metadata['denomUnits']:
            if unit.get('denom') == display_denom:
                if exponent := unit.get('exponent'):
                    return exponent
        
        return max((u.get('exponent', 0) for u in metadata['denomUnits']), default=18)

    def _format_amount(self, amount: str, decimals: int) -> str:
        try:
            amount_int = int(amount)
            if amount_int == 0:
                return "0"
            
            divisor = 10 ** decimals
            formatted = f"{amount_int / divisor:,.{max(2, decimals)}f}"
            
            if '.' in formatted:
                formatted = formatted.rstrip('0').rstrip('.')
            
            return formatted
        except (ValueError, TypeError):
            return amount

    async def get_balances(self) -> Dict:
        print("\nFetching balances...")
        balances_data = await self._fetch_balances()
        balances = balances_data.get('balances', [])
        
        print(f"Found {len(balances)} token balances to process")
        tasks = [self._process_token(balance) for balance in balances]
        results = await asyncio.gather(*tasks)
        
        return {
            "address": self.address,
            "token_info": results
        }

    async def close(self):
        await self.session.close()

#async def main():
#    address = "inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49"
#    verifier = TokenVerifier(address)
#    
#    try:
#        print("Starting token verification...")
#        result = await verifier.get_balances()
#        
#        # Pretty print the result
#        print("\nFinal Result:")
#        print(json.dumps(result, indent=2))
#        
#    except Exception as e:
#        print(f"Error: {str(e)}")
#    finally:
#        await verifier.close()
#
#if __name__ == "__main__":
#    asyncio.run(main())