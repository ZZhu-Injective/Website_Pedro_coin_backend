import base64
import aiohttp
from datetime import datetime
from pyinjective.client.model.pagination import PaginationOption
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network

class InjectiveTokenInfo:

    memecoin = [
        {
            "name": "Pedro",
            "native": "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm",
            "cw20": "inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm",
            "denom": "inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm",
            "pool": "inj15ckgh6kdqg0x5p7curamjvqrsdw4cdzz5ky9v6",
            "creator": "inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk",
            "decimal": 18,
        },
        {
            "name": "Shroom",
            "native": "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8",
            "cw20": "inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8",
            "denom": "inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8",
            "pool": "inj1m35kyjuegq7ruwgx787xm53e5wfwu6n5uadurl",
            "creator": "inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk",
            "decimal": 18,

        },
        {
            "name": "Nonja",
            "native": "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck",
            "cw20": "inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck",
            "denom": "inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck",
            "pool": "inj1r7ahhyfe35l04ffa5gnzsxjkgmnn9jkd5ds0vg",
            "creator": "inj14ejqjy8um4p3xfqj74yld5waqljf88f9eneuk",
            "decimal": 18,
        },
        {
            "name": "Qunt",
            "native": "factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt",
            "cw20": "none",
            "denom": "qunt",
            "pool": "inj193q4e4tqx2mmnkemhsf9tpdn50u5h34cf9qdnh",
            "creator": "inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64",
            "decimal": 6,
        },
        {
            "name": "Kira",
            "native": "factory/inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq/KIRA",
            "cw20": "none",
            "denom": "kira",
            "pool": "inj1eswdzx773we5zu2mz0zcmm7l5msr8wcss8ek0f",
            "creator": "inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq",
            "decimal": 6,
        },
        {
            "name": "ffi",
            "native": "factory/inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc/ffi",
            "cw20": "none",
            "denom": "ffi",
            "pool": "inj1hrgkrr2fxt4nrp8dqf7acmgrglfarz88qk3sms",
            "creator": "inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc",
            "decimal": 6,
        },
        {
            "name": "drugs",
            "native": "factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS",
            "cw20": "none",
            "denom": "Drugs",
            "pool": "inj1y6x5kfc5m7vhmy8dfry2vdqsvrnqrnwmw4rea0",
            "creator": "inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89",
            "decimal": 6,
        },
        {
            "name": "sai",
            "native": "factory/inj10aa0h5s0xwzv95a8pjhwluxcm5feeqygdk3lkm/SAI",
            "cw20": "none",
            "denom": "SAI",
            "pool": "inj18nyltfvkyrx4wxfpdd6sn9l8wmqfr6t63y7nse",
            "creator": "inj10aa0h5s0xwzv95a8pjhwluxcm5feeqygdk3lkm",
            "decimal": 18,
        },
        {
            "name": "xiii",
            "native": "factory/inj18flmwwaxxqj8m8l5zl8xhjrnah98fcjp3gcy3e/XIII",
            "cw20": "none",
            "denom": "SAI",
            "pool": "inj1eswdzx773we5zu2mz0zcmm7l5msr8wcss8ek0f",
            "creator": "inj18flmwwaxxqj8m8l5zl8xhjrnah98fcjp3gcy3e",
            "decimal": 6,
        }
    ]

    def __init__(self):
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)


    async def fetch_dex_info(self):
        async with aiohttp.ClientSession() as session:
            for token in self.memecoin:            
                async with session.get(f'https://api.dexscreener.com/latest/dex/pairs/injective/{token["pool"]}') as response:
                    data = await response.json()
                    if data['pair'] is not None:
                        price_usd = data['pair'].get('priceUsd', 'Nan')
                    else:
                        price_usd = 'Nan'

                    token["price_usd"] = price_usd


    async def total_supply_native(self):
        for token in self.memecoin:
            if token['name'] == "Pedro" or token["name"] == "Shroom" or token["name"] == "Nonja":
                token["total_supply_native"] = 0
            else:
                total_supply = await self.client.fetch_supply_of(denom=token["native"])
                token["total_supply_native"] = str(float(total_supply["amount"]["amount"])/ 10 ** token['decimal'])

        
    async def burn_supply_native(self):
        all_bank_balances = await self.client.fetch_bank_balances(address="inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49")
        
        def get_token_details(native_denom):
            for token in self.memecoin:
                if token["native"] == native_denom:
                    return token
            return None

        for balance in all_bank_balances.get('balances', []):
            token_details = get_token_details(balance['denom'])

            if token_details:
                token_details['total_burn_native'] = str(float(balance['amount']) / 10 ** token_details['decimal'])

    async def total_and_burn_supply_cw20(self):
        cw20_tokens = [token for token in self.memecoin if token['cw20'] != "none"]

        for token in cw20_tokens:
            total_supply = 0
            burn_coin = 0
            holders = await self.client.fetch_all_contracts_state(address=token['cw20'], pagination=PaginationOption(limit=1000))

            first_fetch = holders
            while holders['pagination']['nextKey']:
                pagination = PaginationOption(limit=1000, encoded_page_key=holders['pagination']['nextKey'])
                holders = await self.client.fetch_all_contracts_state(address=token['cw20'], pagination=pagination)
                first_fetch['models'] += holders['models']
                first_fetch['pagination'] = holders['pagination']

            for model in first_fetch['models']:
                value_decoded = base64.b64decode(model['value']).decode('utf-8').strip('"')

                if value_decoded.isdigit():
                    amount_coin = float(value_decoded) / 10 ** 18

                    total_supply += amount_coin
                    
                    inj_address = base64.b64decode(model['key']).decode('utf-8')[9:]

                    if inj_address == "inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49" or inj_address == token['cw20']:
                        burn_coin += amount_coin


                    token['total_supply_cw20'] = total_supply
                    token['total_burn_cw20'] = burn_coin                      


    async def mintable(self):
        for token in self.memecoin:
            metadata = await self.client.fetch_denom_authority_metadata(creator=token['creator'], sub_denom=token['denom'])
            admin = metadata.get('authorityMetadata', {}).get('admin', '')
            mintable = 'No' if admin == 'inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49' or admin == 'inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk' else 'Yes'
            
            token['mintable'] = mintable

    async def circulation_supply(self):
        await self.fetch_dex_info()
        await self.mintable()
        await self.total_supply_native()
        await self.burn_supply_native()
        await self.total_and_burn_supply_cw20()

        total_market_cap = 0

        for token in self.memecoin:
            total_burn_native = float(token.get('total_burn_native', 0))
            total_burn_cw20 = float(token.get('total_burn_cw20', 0))
            total_supply_native = float(token.get('total_supply_native', 0))
            total_supply_cw20 = float(token.get('total_supply_cw20', 0))

            token['total_burn'] = total_burn_native + total_burn_cw20
            token['total_supply'] = total_supply_native + total_supply_cw20
            token['circulation_supply'] = token['total_supply'] - token['total_burn']
            if token['price_usd']=="Nan":
                token['market_cap'] = "Nan"
            else:
                token['market_cap'] = token['circulation_supply'] * float(token.get('price_usd', 0))

            token['time'] = datetime.now().strftime('%d-%m-%Y %H:%M')
            token['total_token'] = len(self.memecoin)
            
            if token['market_cap'] == "Nan": 
                continue
            else:
                total_market_cap += token['market_cap']


        for token in self.memecoin:
            token['total_market_cap'] = total_market_cap
        
        return self.memecoin