import asyncio
import pandas as pd
import base64
import json

from datetime import datetime

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network

class InjectiveWalletInfo:

    NATIVE = [
        "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm",
        "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8",
        "factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt",
        "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck",
        "factory/inj1td7t8spd4k6uev6uunu40qvrrcwhr756d5qw59/ipepe",
        "factory/inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc/ffi",
        "factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS",
        "factory/inj10aa0h5s0xwzv95a8pjhwluxcm5feeqygdk3lkm/SAI"
    ]

    CW20 = [
        "inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm",
        "inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8",
        "inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck"
    ]

    def __init__(self, address):
        self.address = address
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)

    async def account_info(self):
        account = await self.client.fetch_account(address=self.address)
        return account
    
    async def fetch_native_balance(self) -> dict:
        all_bank_balances = await self.client.fetch_bank_balances(address=self.address)
        native_balances = [balance for balance in all_bank_balances.get('balances', []) if balance['denom'] in self.NATIVE]

        for balance in native_balances:
            fetch_info = await self.client.fetch_denom_metadata(denom=balance['denom'])
            balance['decimals'] = fetch_info['metadata']['decimals']

            if balance['decimals'] == 0: 
                balance['decimals'] = 18

            balance['amount'] = str(float(balance['amount']) / 10**balance['decimals'])
        
        return native_balances
    
    async def fetch_cw20_balance(self) -> dict:
        #This will be happend if the database is set up!
        return None

    async def my_wallet(self):
        account = await self.account_info()
        bank_balances = await self.fetch_native_balance()

        result = {
            'address': account.base_account.address,
            'clicks' : 100,
            'account_number': account.base_account.account_number,
            'balances': bank_balances,
            'holding': len(bank_balances),
            'time': datetime.now().strftime('%d-%m-%Y %H:%M')
        }
        return result
    
"""
result = 

{'address': 'inj1x6u08aa3plhk3utjk7wpyjkurtwnwp6dhudh0j', 
'clicks': 100, 
'account_number': 928331, 
'balances': [{'denom': 'factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm', 'amount': '1.0', 'decimals': 18}, {'denom': 'factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS', 'amount': '4424.734513', 'decimals': 6}], 
'holding': 2, 
'time': '06-01-2025 12:34'}
"""

#async def main():
#    injective_info = InjectiveInfo('inj1x6u08aa3plhk3utjk7wpyjkurtwnwp6dhudh0j')
#    wallet_info = await injective_info.my_wallet()
#    print(wallet_info)

#asyncio.run(main())