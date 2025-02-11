import asyncio
import pandas as pd
from datetime import datetime
from pyinjective.core.network import Network
from pyinjective.async_client import AsyncClient
from pyinjective.client.model.pagination import PaginationOption

class CoinDrop:

    def __init__(self):
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)

    async def fetch_holder_native_token(self, native_address):
        async def fetch_page(pagination_key=None):
            pagination = PaginationOption(limit=1000, encoded_page_key=pagination_key)
            return await self.client.fetch_denom_owners(denom=native_address, pagination=pagination)

        holders = await fetch_page()
        if holders is None:
            return

        tasks = []
        B = holders

        while holders['pagination']['nextKey']:
            tasks.append(fetch_page(holders['pagination']['nextKey']))
            if len(tasks) >= 1: 
                new_data = await asyncio.gather(*tasks)
                for data in new_data:
                    B['denomOwners'] += data['denomOwners']
                    holders = data
                tasks = []

        if tasks: 
            new_data = await asyncio.gather(*tasks)
            for data in new_data:
                B['denomOwners'] += data['denomOwners']
                holders = data

        decimal = 6 if native_address in ["factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt",
                                          "factory/inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq/KIRA",
                                          "factory/inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc/ffi",
                                          "factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS",
                                          "factory/inj18flmwwaxxqj8m8l5zl8xhjrnah98fcjp3gcy3e/XIII"] else 18

        data_wallet = [
            {'key': model['address'], 'value': int(model['balance']['amount']) / 10 ** decimal}
            for model in B['denomOwners']
            if int(model['balance']['amount']) / 10 ** decimal > 0
        ]

        df_holder_native = pd.DataFrame(data_wallet)
        df_holder_native = df_holder_native.sort_values(by='value', ascending=False)

        
        return df_holder_native

    async def fetch_holders(self, native_address):
        df_holders_native = await self.fetch_holder_native_token(native_address)
        total_supply = df_holders_native['value'].sum()
        df_holders_native['percentage'] = (df_holders_native['value'] / total_supply) * 100

        df_holders_native = df_holders_native.rename(columns={'key': 'owner', 'value': 'total'})
                
        dict_holders = {
            "holders": df_holders_native.to_dict(orient='records')
        }

        print(dict_holders)

        return dict_holders



