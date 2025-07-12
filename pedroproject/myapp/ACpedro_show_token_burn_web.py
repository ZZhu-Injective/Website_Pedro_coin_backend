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
            os.path.join('pedroproject', 'myapp', 'ACpedro_verified_token.json')
        ]
        
        for filename in possible_filenames:
            try:
                if os.path.exists(filename):
                    with open(filename, 'r', encoding='utf-8') as f:
                        return json.load(f)
            except Exception:
                continue
        
        print("Warning: Could not load verified tokens file")
        return []

    @backoff.on_exception(backoff.expo, Exception, max_tries=5)
    async def _fetch_balances(self) -> Dict:
        return await self.client.fetch_bank_balances(address=self.address)

    def _find_verified_token(self, denom: str, symbol: str) -> Optional[Dict]:
        for token in self.verified_tokens:
            if token.get('denom') == denom:
                return token
        
        clean_symbol = symbol.lower().strip()
        for token in self.verified_tokens:
            if token.get('symbol', '').lower().strip() == clean_symbol:
                return token
            if token.get('overrideSymbol', '').lower().strip() == clean_symbol:
                return token
        
        return None

    async def _process_token(self, balance: Dict) -> Dict:
        async with self.semaphore:
            denom = balance['denom']
            amount = balance['amount']
            base_symbol = denom.split('/')[-1] if '/' in denom else denom
            
            if verified := self._find_verified_token(denom, base_symbol):
                return {
                    'symbol': verified.get('overrideSymbol', verified.get('symbol', base_symbol)),
                    'decimals': verified.get('decimals', 18),
                    'denom': denom,
                    'amount': amount,
                    'human_readable_amount': self._format_amount(amount, verified.get('decimals', 18)),
                    'name': verified.get('name', 'Unknown'),
                    'logo': verified.get('logo'),
                    'is_verified': True
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
                        'is_verified': False
                    }
            except Exception:
                pass
            
            return {
                'symbol': base_symbol,
                'decimals': 18,
                'denom': denom,
                'amount': amount,
                'human_readable_amount': self._format_amount(amount, 18),
                'name': 'Unknown',
                'is_verified': False
            }

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    async def _fetch_token_metadata(self, denom: str) -> Optional[Dict]:
        try:
            return await self.client.fetch_denom_metadata(denom=denom)
        except Exception:
            return None

    def _extract_decimals(self, metadata: Dict) -> int:
        if 'denomUnits' not in metadata:
            return 18
            
        display_denom = metadata.get('display', '')
        for unit in metadata['denomUnits']:
            if unit.get('denom') == display_denom:
                if exponent := unit.get('exponent'):
                    return exponent
        
        return max((u.get('exponent', 0) for u in metadata['denomUnits']))

    def _format_amount(self, amount: str, decimals: int) -> str:
        try:
            amount_int = int(amount)
            divisor = 10 ** decimals
            formatted = f"{amount_int / divisor:,.{max(2, decimals)}f}"
            return formatted.rstrip('0').rstrip('.') if '.' in formatted else formatted
        except (ValueError, TypeError):
            return amount

    async def get_balances(self) -> Dict:
        balances_data = await self._fetch_balances()
        balances = balances_data.get('balances', [])
        
        tasks = [self._process_token(balance) for balance in balances]
        return {
            "address": self.address,
            "token_info": await asyncio.gather(*tasks)
        }

    async def close(self):
        """Cleanup resources"""
        await self.session.close()

#async def main():
#    address = "inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49"
#    verifier = TokenVerifier(address)
#    
#    try:
#        result = await verifier.get_balances()
#        for token in result['token_info']:
#            print(f"\nToken: {token['symbol']}")
#            print(f"Name: {token['name']}")
#            print(f"Amount: {token['human_readable_amount']}")
#            print(f"Denom: {token['denom']}")
#            if token.get('logo'):
#                print(f"Logo: {token['logo']}")
#            print(f"Verified: {'Yes' if token['is_verified'] else 'No'}")
#            print("-" * 30)
#    finally:
#        await verifier.close()
#
#if __name__ == "__main__":
#    asyncio.run(main())