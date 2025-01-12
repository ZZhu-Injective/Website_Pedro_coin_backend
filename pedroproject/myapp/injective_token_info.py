import pandas as pd
from datetime import datetime

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network
import aiohttp

class InjectiveTokenInfo:

    NATIVE = [
        "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm",
        "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8",
        "factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt",
        "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck",
        "factory/inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq/KIRA",
        "factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS",
        "factory/inj10aa0h5s0xwzv95a8pjhwluxcm5feeqygdk3lkm/SAI"
    ]

    SUBDENOM = [
        "inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm",
        "inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8",
        "qunt",
        "inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck",
        "kira",
        "DRUGS",
        "SAI"
    ]

    POOL = [
        "inj15ckgh6kdqg0x5p7curamjvqrsdw4cdzz5ky9v6",
        "inj1m35kyjuegq7ruwgx787xm53e5wfwu6n5uadurl",
        "inj193q4e4tqx2mmnkemhsf9tpdn50u5h34cf9qdnh",
        "inj1r7ahhyfe35l04ffa5gnzsxjkgmnn9jkd5ds0vg",
        "inj1eswdzx773we5zu2mz0zcmm7l5msr8wcss8ek0f",
        "inj1y6x5kfc5m7vhmy8dfry2vdqsvrnqrnwmw4rea0",
        "inj18nyltfvkyrx4wxfpdd6sn9l8wmqfr6t63y7nse",
    ]

    CREATOR = [
        "inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk",
        "inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk",
        "inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64",
        "inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk",
        "inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq",
        "inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89",
        "inj10aa0h5s0xwzv95a8pjhwluxcm5feeqygdk3lkm"
    ]

    CW20 = [
        "inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm",
        "inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8",
        "inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck"
    ]

    def __init__(self):
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)

    async def fetch_dex_info(self):

        pair_ids = [
            "inj15ckgh6kdqg0x5p7curamjvqrsdw4cdzz5ky9v6",
            "inj1m35kyjuegq7ruwgx787xm53e5wfwu6n5uadurl",
            "inj193q4e4tqx2mmnkemhsf9tpdn50u5h34cf9qdnh",
            "inj1r7ahhyfe35l04ffa5gnzsxjkgmnn9jkd5ds0vg",
            "inj1eswdzx773we5zu2mz0zcmm7l5msr8wcss8ek0f",
            "inj1y6x5kfc5m7vhmy8dfry2vdqsvrnqrnwmw4rea0",
            "inj18nyltfvkyrx4wxfpdd6sn9l8wmqfr6t63y7nse",
        ]

        NATIVE = [
            "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm",
            "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8",
            "factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt",
            "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck",
            "factory/inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq/KIRA",
            "factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS",
            "factory/inj10aa0h5s0xwzv95a8pjhwluxcm5feeqygdk3lkm/SAI"
        ]
        dex_info = {}

        async with aiohttp.ClientSession() as session:
            for pair_id, native in zip(pair_ids, NATIVE):
                async with session.get(f'https://api.dexscreener.com/latest/dex/pairs/injective/{pair_id}') as response:
                    data = await response.json()
                    if data is not None and 'pair' in data and data['pair'] is not None:
                        priceUsd = data['pair'].get('priceUsd', 'NAN')
                    else:
                        priceUsd = 'None'
                    dex_info[native] = {
                        "priceUsd": priceUsd
                    }
        return dex_info


    async def tracking_burn_address(self):
        results = {}
        for creator, subdenom, native, pool in zip(self.CREATOR, self.SUBDENOM, self.NATIVE, self.POOL):
            metadata = await self.client.fetch_denom_authority_metadata(creator=creator, sub_denom=subdenom)
            admin = metadata.get('authorityMetadata', {}).get('admin', '')
            burn_status = 'No' if admin == 'inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49' or admin == 'inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk' else 'Yes'
            results[native] = {'info': {"Burn": burn_status, "pairId": pool}}
        return results

    async def total_supply(self):
        supplies = {}
        for denom, pool in zip(self.NATIVE, self.POOL):
            supply = await self.client.fetch_supply_of(denom=denom)
            supplies[denom] = {"info": {"denom": denom, "amount": supply["amount"]["amount"], "pairId": pool}}

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
        burn_addresses = await self.tracking_burn_address()
        total_supplies = await self.total_supply()
        burn_supplies = await self.burn_supply()
        dex_info = await self.fetch_dex_info()

        tokenInfo = {}
        total_all_amount_usd = 0
        for denom, total_info in total_supplies.items():
            burn_amount = next((balance['amount'] for balance in burn_supplies if balance['denom'] == denom), '0')
            circulation_amount = str(float(total_info['info']['amount']) - float(burn_amount))
            price_usd = dex_info.get(denom, {}).get('priceUsd', 0)
            total_amount = float(price_usd) * float(circulation_amount)
            total_all_amount_usd += total_amount

            tokenInfo[denom] = {
                "info": {
                    "denom": denom,
                    "Total_supply": total_info['info']['amount'],
                    "Burn_supply": burn_amount,
                    "Circulation_supply": circulation_amount,
                    "Price_usd": dex_info.get(denom, {}).get('priceUsd'),
                    "Total_amount_usd": total_all_amount_usd,
                    **burn_addresses[denom]['info']
                },
                'time': datetime.now().strftime('%d-%m-%Y %H:%M')
            }

        return tokenInfo


"""
{'factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm': {'info': {'denom': 'factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm', 'Total_supply': '1.0', 'Burn_supply': '0', 'Circulation_supply': '1.0', 'Burn': 'yes'}, 'time': '11-01-2025 01:18'}, 
'factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8': {'info': {'denom': 'factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8', 'Total_supply': '219483424.98607278', 'Burn_supply': '0', 'Circulation_supply': '219483424.98607278', 'Burn': 'yes'}, 'time': '11-01-2025 01:18'}, 
'factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt': {'info': {'denom': 'factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt', 'Total_supply': '777777777.0', 'Burn_supply': '177686523.0', 'Circulation_supply': '600091254.0', 'Burn': 'yes'}, 'time': '11-01-2025 01:18'}, 
'factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck': {'info': {'denom': 'factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck', 'Total_supply': '93138792.00990751', 'Burn_supply': '0', 'Circulation_supply': '93138792.00990751', 'Burn': 'yes'}, 'time': '11-01-2025 01:18'}, 
'factory/inj1td7t8spd4k6uev6uunu40qvrrcwhr756d5qw59/ipepe': {'info': {'denom': 'factory/inj1td7t8spd4k6uev6uunu40qvrrcwhr756d5qw59/ipepe', 'Total_supply': '50000000.0', 'Burn_supply': '0', 'Circulation_supply': '50000000.0', 'Burn': 'no'}, 'time': '11-01-2025 01:18'}, 
'factory/inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc/ffi': {'info': {'denom': 'factory/inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc/ffi', 'Total_supply': '15400.0', 'Burn_supply': '3000.000391', 'Circulation_supply': '12399.999609', 'Burn': 'yes'}, 'time': '11-01-2025 01:18'}, 
'factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS': {'info': {'denom': 'factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS', 'Total_supply': '385887284.0', 'Burn_supply': '0', 'Circulation_supply': '385887284.0', 'Burn': 'no'}, 'time': '11-01-2025 01:18'}, 
'factory/inj10aa0h5s0xwzv95a8pjhwluxcm5feeqygdk3lkm/SAI': {'info': {'denom': 'factory/inj10aa0h5s0xwzv95a8pjhwluxcm5feeqygdk3lkm/SAI', 'Total_supply': '1000000.0', 'Burn_supply': '1.0', 'Circulation_supply': '999999.0', 'Burn': 'yes'}, 'time': '11-01-2025 01:18'}}
"""

#async def main():
#    injective_token_info = InjectiveTokenInfo()
#    circulation_supplies = await injective_token_info.circulation_supply()
#    print(circulation_supplies)

#asyncio.run(main())
