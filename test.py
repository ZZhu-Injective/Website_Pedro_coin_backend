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
            "creator": "inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk"
        },
        {
            "name": "Shroom",
            "native": "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8",
            "cw20": "inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8",
            "denom": "inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8",
            "pool": "inj1m35kyjuegq7ruwgx787xm53e5wfwu6n5uadurl",
            "creator": "inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk"
        },
        {
            "name": "Nonja",
            "native": "factory/inj14ejqjy8um4p3xfqj74yld5waqljf88f9eneuk/inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck",
            "cw20": "inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck",
            "denom": "inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck",
            "pool": "inj193q4e4tqx2mmnkemhsf9tpdn50u5h34cf9qdnh",
            "creator": "inj14ejqjy8um4p3xfqj74yld5waqljf88f9eneuk"
        },
        {
            "name": "Qunt",
            "native": "factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt",
            "cw20": "none",
            "denom": "qunt",
            "pool": "inj1r7ahhyfe35l04ffa5gnzsxjkgmnn9jkd5ds0vg",
            "creator": "inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64"
        },
        {
            "name": "Kira",
            "native": "factory/inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq/KIRA",
            "cw20": "none",
            "denom": "kira",
            "pool": "inj1eswdzx773we5zu2mz0zcmm7l5msr8wcss8ek0f",
            "creator": "inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq"
        },
        {
            "name": "ffi",
            "native": "factory/inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc/ffi",
            "cw20": "none",
            "denom": "ffi",
            "pool": "inj1hrgkrr2fxt4nrp8dqf7acmgrglfarz88qk3sms",
            "creator": "inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc"
        },
        {
            "name": "drugs",
            "native": "factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS",
            "cw20": "none",
            "denom": "none",
            "pool": "inj1y6x5kfc5m7vhmy8dfry2vdqsvrnqrnwmw4rea0",
            "creator": "inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89"
        },
        {
            "name": "sai",
            "native": "factory/inj10aa0h5s0xwzv95a8pjhwluxcm5feeqygdk3lkm/SAI",
            "cw20": "none",
            "denom": "none",
            "pool": "inj18nyltfvkyrx4wxfpdd6sn9l8wmqfr6t63y7nse",
            "creator": "inj10aa0h5s0xwzv95a8pjhwluxcm5feeqygdk3lkm"
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
                    if data is not None:
                        price_usd = data['pair'].get('priceUsd', 'NAN')
                    else:
                        price_usd = 'NAN'

                    token["price_usd"] = price_usd

    async def tracking_burn_address(self):
        for token in self.memecoin:
            data = await self.client.fetch_denom_authority_metadata(creator=token["creator"], sub_denom=token["denom"])
            print(data)

            admin = data.get('authorityMetadata', {}).get('admin', '')

            if admin == 'inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49' or admin == 'inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk':

                token["burn_token"] = data["amount"]
            else:
                continue

                

async def main():
    injective_info = InjectiveTokenInfo()
    await injective_info.tracking_burn_address()


# To run the script
import asyncio
asyncio.run(main())
