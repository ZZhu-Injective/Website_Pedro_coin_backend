import base64
from datetime import datetime
import json
import time
import asyncio
import pandas as pd
from pyinjective.core.network import Network
from pyinjective.async_client import AsyncClient
from pyinjective.client.model.pagination import PaginationOption

class InjectiveHolders:

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
            if len(tasks) >= 10:  # Adjust batch size as needed
                new_data = await asyncio.gather(*tasks)
                for data in new_data:
                    B['denomOwners'] += data['denomOwners']
                    holders = data
                tasks = []

        if tasks:  # Fetch remaining tasks
            new_data = await asyncio.gather(*tasks)
            for data in new_data:
                B['denomOwners'] += data['denomOwners']
                holders = data

        # Processing and filtering the data concurrently
        decimal = 6 if native_address in ["factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt",
                                          "factory/inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq/KIRA",
                                          "factory/inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc/ffi",
                                          "factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS"] else 18

        data_wallet = [
            {'key': model['address'], 'value': int(model['balance']['amount']) / 10 ** decimal}
            for model in B['denomOwners']
            if int(model['balance']['amount']) / 10 ** decimal > 0
        ]

        df_holder_native = pd.DataFrame(data_wallet)
        

        return df_holder_native
    
    async def fetch_holders_cw20_token(self, cw20_address):
        holders_cw20_wallet = []
        holders = await self.client.fetch_all_contracts_state(address=cw20_address, pagination=PaginationOption(limit=1000))
        if holders is None:
            return

        A = holders
        while A['pagination']['nextKey']:
            pagination = PaginationOption(limit=1000, encoded_page_key=A['pagination']['nextKey'])
            holders = await self.client.fetch_all_contracts_state(address=cw20_address, pagination=pagination)
            A['models'] += holders['models']
            A['pagination'] = holders['pagination']

        for model in A['models']:
            try:
                amount_Coin = int(base64.b64decode(model['value']).decode('utf-8').strip('"')) / 1e18
                inj_address = base64.b64decode(model['key']).decode('utf-8')[9:]

                if amount_Coin != 0:
                    holders_cw20_wallet.append({'key': inj_address, 'value': amount_Coin})

            except (ValueError, json.JSONDecodeError):
                continue

        df_holders_cw20 = pd.DataFrame(holders_cw20_wallet)
        return df_holders_cw20

    # Merge this two data to one dataframe.
    async def fetch_holders(self, cw20_address, native_address):
        if cw20_address == "no_cw20":
            df_holders_native = await self.fetch_holder_native_token(native_address)
            df_holders_native.rename(columns={'value': 'native_value'}, inplace=True)
            
            # Creating a dummy dataframe for cw20 with the same keys and default values
            df_holders_cw20 = df_holders_native.copy()
            df_holders_cw20['cw20_value'] = 0
            df_holders_cw20 = df_holders_cw20.drop(columns=['native_value'])
            
        elif native_address == "no_native":
            df_holders_cw20 = await self.fetch_holders_cw20_token(cw20_address)
            df_holders_cw20.rename(columns={'value': 'cw20_value'}, inplace=True)
            df_holders_native = pd.DataFrame(columns=['key', 'native_value'])

        else:
            df_holders_native = await self.fetch_holder_native_token(native_address)
            print(df_holders_native)
            df_holders_cw20 = await self.fetch_holders_cw20_token(cw20_address)
            print(df_holders_cw20)
            df_holders_cw20.rename(columns={'value': 'cw20_value'}, inplace=True)
            df_holders_native.rename(columns={'value': 'native_value'}, inplace=True)

        # Merging dataframes
        merged_df = pd.merge(df_holders_native, df_holders_cw20, on='key', how='outer')
        merged_df.fillna(0, inplace=True)

        # Calculating total value and percentage
        merged_df['total_value'] = merged_df['native_value'] + merged_df['cw20_value']
        total_supply = merged_df['total_value'].sum()
        merged_df['percentage'] = (merged_df['total_value'] / total_supply) * 100

        # Sorting and formatting the dataframe
        merged_df = merged_df.sort_values(by='total_value', ascending=False)
        merged_df = merged_df.round({'total_value': 0, 'percentage': 5, 'native_value': 2, 'cw20_value': 2})
        merged_df = merged_df.reset_index(drop=True)
        merged_df['Top'] = merged_df.index + 1

        current_time = datetime.now().strftime('%d-%m-%Y %H:%M')
        dict_holders = {
            "timestamp": current_time,
            "holders": merged_df.to_dict('records')
        }

        print(dict_holders)     
        return dict_holders