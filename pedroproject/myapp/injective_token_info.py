import asyncio
import pandas as pd
import base64
import json
import sqlite3

from datetime import datetime

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network

class InjectiveTokenInfo:

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

    def __init__(self):
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)

    async def total_supply(self):
        supplies = {}
        for denom in self.NATIVE:
            supply = await self.client.fetch_supply_of(denom=denom)
            supplies[denom] = {"info": {"denom": denom, "amount": supply["amount"]["amount"]}}

        for denom, supply_info in supplies.items():
            fetch_info = await self.client.fetch_denom_metadata(denom=denom)
            decimals = fetch_info['metadata']['decimals']
            supply_info['info']['decimals'] = decimals if decimals != 0 else 18
            supply_info['info']['amount'] = str(float(supply_info['info']['amount']) / 10**supply_info['info']['decimals'])
        return supplies
    
    
    async def burn_supply(self):
        all_bank_balances = await self.client.fetch_bank_balances(address="inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49")
        burn_supply = [balance for balance in all_bank_balances.get('balances', []) if balance['denom'] in self.NATIVE]

        for balance in burn_supply:
            fetch_info = await self.client.fetch_denom_metadata(denom=balance['denom'])
            balance['decimals'] = fetch_info['metadata']['decimals']

            if balance['decimals'] == 0:
                balance['decimals'] = 18

            balance['amount'] = str(float(balance['amount']) / 10**balance['decimals'])

        return burn_supply

    async def circulation_supply(self):
        total_supplies = await self.total_supply()
        burn_supplies = await self.burn_supply()

        circulation_supplies = {}
        for denom, total_info in total_supplies.items():
            burn_amount = next((balance['amount'] for balance in burn_supplies if balance['denom'] == denom), '0')
            circulation_amount = str(float(total_info['info']['amount']) - float(burn_amount))
            circulation_supplies[denom] = {
                "info": {
                    "denom": denom,
                    "Total_supply": total_info['info']['amount'],
                    "Burn_supply": burn_amount,
                    "Circulation_supply": circulation_amount,
                }
            }

        return circulation_supplies

async def main():
    injective_token_info = InjectiveTokenInfo()
    circulation_supplies = await injective_token_info.circulation_supply()
    print(circulation_supplies)

asyncio.run(main())
