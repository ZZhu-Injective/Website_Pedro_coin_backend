import base64
import orjson as json
import asyncio
from typing import List
import backoff
from datetime import datetime
from pyinjective.core.network import Network
from pyinjective.async_client import AsyncClient
from pyinjective.client.model.pagination import PaginationOption
import aiohttp


class InjectiveWalletInfo:
    memecoin = [
        {"name": "Pedro", "native": "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm", "cw20": "inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm"},
        {"name": "Shroom", "native": "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8", "cw20": "inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8"},
        {"name": "Nonja", "native": "factory/inj14ejqjy8um4p3xfqj74yld5waqljf88f9eneuk/inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck", "cw20": "inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck"},
        {"name": "Qunt", "native": "factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt", "cw20": "none"},
        {"name": "Kira", "native": "factory/inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq/KIRA", "cw20": "none"},
        {"name": "ffi", "native": "factory/inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc/ffi", "cw20": "none"},
        {"name": "drugs", "native": "factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS", "cw20": "none"},
        {"name": "sai", "native": "factory/inj10aa0h5s0xwzv95a8pjhwluxcm5feeqygdk3lkm/SAI", "cw20": "none"},
        {"name": "Xiii", "native": "factory/inj18flmwwaxxqj8m8l5zl8xhjrnah98fcjp3gcy3e/XIII", "cw20": "none"},
    ]

    def __init__(self, address):
        self.address = address
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)
        self.session = aiohttp.ClientSession()
        self.sem = asyncio.Semaphore(10) 

    @backoff.on_exception(backoff.expo, Exception, max_tries=10)
    async def fetch_account_with_retry(self):
        return await self.client.fetch_account(address=self.address)

    @backoff.on_exception(backoff.expo, Exception, max_tries=10)
    async def fetch_bank_balances_with_retry(self):
        return await self.client.fetch_bank_balances(address=self.address)

    async def fetch_native_balance(self) -> dict:
        all_bank_balances = await self.fetch_bank_balances_with_retry()
        native_tokens = {token['native']: token for token in self.memecoin}

        balances = []
        for balance in all_bank_balances.get('balances', []):
            denom = balance['denom']
            token = native_tokens.get(denom)
            if token:
                decimal = 6 if denom in {"factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt", "factory/inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq/KIRA", "factory/inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc/ffi", "factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS", "factory/inj18flmwwaxxqj8m8l5zl8xhjrnah98fcjp3gcy3e/XIII"} else 18
                balances.append({'denom': denom, 'amount': float(balance['amount']) / 10**decimal})
        
        return balances

    async def fetch_cw20_balance(self):
        cw20_balances = []

        cw20_tokens = [token for token in self.memecoin if token['cw20'] != "none"]

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
                                cw20_balances.append({'denom': token['native'], 'amount': amount_Coin})
                except (ValueError, json.JSONDecodeError):
                    continue
        
            return cw20_balances

    async def my_wallet(self):
        account_task = self.fetch_account_with_retry()
        bank_balances_task = self.fetch_native_balance()
        cw20_balances_task = self.fetch_cw20_balance()

        account, bank_balances, cw20_balances = await asyncio.gather(account_task, bank_balances_task, cw20_balances_task)

        total_balances = {}
        for balance in bank_balances + cw20_balances:
            denom = balance['denom']
            amount = float(balance['amount'])
            total_balances[denom] = total_balances.get(denom, 0) + amount

        print(cw20_balances)

        return {
            'address': self.address,
            'clicks': 100,
            'account_number': account.base_account.account_number,
            'transactions': account.base_account.sequence,
            'balances': total_balances,
            'cw20_balances': cw20_balances,
            'native_balances': bank_balances,
            'holding': len(total_balances),
            'time': datetime.now().strftime('%d-%m-%Y %H:%M')
        }
