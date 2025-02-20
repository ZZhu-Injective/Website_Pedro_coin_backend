import asyncio
import base64
import json
import backoff
from pyinjective.core.network import Network
from pyinjective.async_client import AsyncClient
from pyinjective.client.model.pagination import PaginationOption

class InjectiveLogin:

    memecoin = [
        {
            "name": "Pedro",
            "native": "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm",
            "cw20": "inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm"
        }
    ]
    
    def __init__(self, address):
        self.address = address
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)

    @backoff.on_exception(backoff.expo, Exception, max_tries=5)
    async def fetch_account_with_retry(self):
        return await self.client.fetch_account(address=self.address)

    @backoff.on_exception(backoff.expo, Exception, max_tries=5)
    async def fetch_bank_balances_with_retry(self):
        return await self.client.fetch_bank_balances(address=self.address)
    
    async def fetch_native_balance(self) -> float:
        all_bank_balances = await self.fetch_bank_balances_with_retry()
        native_balances = [balance for balance in all_bank_balances.get('balances', []) if balance['denom'] in [coin['native'] for coin in self.memecoin]]

        total_native_balance = 0.0
        for balance in native_balances:
            if balance['denom'] == "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm":
                balance['amount'] = float(balance['amount']) / 10**18
                total_native_balance += balance['amount']
        return total_native_balance

    async def fetch_cw20_balance(self) -> float:
        cw20_tokens = [token for token in self.memecoin if token['cw20'] != "none"]

        total_cw20_balance = 0.0
        for token in cw20_tokens:
            holders = await self.client.fetch_all_contracts_state(address=token['cw20'], pagination=PaginationOption(limit=1000))

            first_fetch = holders
            while holders['pagination']['nextKey']:
                pagination = PaginationOption(limit=1000, encoded_page_key=holders['pagination']['nextKey'])
                holders = await self.client.fetch_all_contracts_state(address=token['cw20'], pagination=pagination)
                first_fetch['models'] += holders['models']
                first_fetch['pagination'] = holders['pagination']

            for model in first_fetch['models']:
                try:
                    value_decoded = base64.b64decode(model['value']).decode('utf-8').strip('"')

                    if value_decoded.isdigit():
                        amount_Coin = int(value_decoded) / 1e18
                        inj_address = base64.b64decode(model['key']).decode('utf-8')[9:]
                        
                        if amount_Coin > 0:
                            if inj_address == self.address:
                                total_cw20_balance += amount_Coin
                except (ValueError, json.JSONDecodeError):
                    continue
        return total_cw20_balance

    async def check_total_balance(self) -> str:
        native_balance = await self.fetch_native_balance()
        cw20_balance = await self.fetch_cw20_balance()
        total_balance = native_balance + cw20_balance

        if total_balance > 10000:
            return "yes"
        else:
            return "no"

