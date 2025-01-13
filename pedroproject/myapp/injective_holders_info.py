import pandas as pd
import base64
import json
import time

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network
from grpc import aio, StatusCode

class InjectiveHolders:

    def __init__(self):
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)


    # Fetch holders from CW20 Token
    async def fetch_holders_cw20(self, cw20_address):
        retry_attempts = 5
        holders = None

        for attempt in range(retry_attempts):
            try:
                holders = await self.client.fetch_all_contracts_state(address=cw20_address, pagination=PaginationOption(limit=1000))
                break
            except aio.AioRpcError as e:
                if e.code() == StatusCode.UNAVAILABLE and attempt < retry_attempts - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    raise

        if holders is None:
            return

        A = holders
        while holders['pagination']['nextKey']:
            pagination = PaginationOption(limit=1000, encoded_page_key=holders['pagination']['nextKey'])
            holders = await self.client.fetch_all_contracts_state(address=cw20_address, pagination=pagination)
            A['models'] += holders['models']
            A['pagination'] = holders['pagination']

        data_wallet = []

        for model in A['models']:
            try:
                amount_Coin = base64.b64decode(model['value']).decode('utf-8')
                inj_address = base64.b64decode(model['key']).decode('utf-8')

                inj_address = inj_address[9:]

                amount_Coin = amount_Coin.strip('"')

                amount_Coin = int(amount_Coin) / 1000000000000000000

                if amount_Coin == 0:
                    continue

                data_wallet.append({'key': inj_address, 'value': amount_Coin})

            except (ValueError, json.JSONDecodeError) as e:
                continue

        df_holders_cw20 = pd.DataFrame(data_wallet)

        return df_holders_cw20




    # Fetch holders from native Token
    async def fetch_holder_native_token(self, native_address):
        retry_attempts = 5
        holders = None

        for attempt in range(retry_attempts):
            try:
                holders = await self.client.fetch_denom_owners(denom=native_address, pagination=PaginationOption(limit=1000))
                break
            except aio.AioRpcError as e:
                if e.code() == StatusCode.UNAVAILABLE and attempt < retry_attempts - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    raise

        if holders is None:
            return

        B = holders
        while holders['pagination']['nextKey']:
            pagination = PaginationOption(limit=1000, encoded_page_key=holders['pagination']['nextKey'])
            holders = await self.client.fetch_denom_owners(denom=native_address, pagination=pagination)
            B['denomOwners'] += holders['denomOwners']
            B['pagination'] = holders['pagination']

        data_wallet = []

        for model in B['denomOwners']:
            try:
                amount_Coin = model['balance']['amount']
                inj_address = model['address']

                if native_address == "factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt":
                    decimal = 6
                elif native_address == "factory/inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq/KIRA":
                    decimal = 6
                elif native_address == "factory/inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc/ffi":
                    decimal = 6
                elif native_address == "factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS":
                    decimal = 6
                elif native_address == "factory/inj10aa0h5s0xwzv95a8pjhwluxcm5feeqygdk3lkm/SAI":
                    decimal = 18
                else:
                    fetch_info = await self.client.fetch_denom_metadata(denom=native_address)
                    if fetch_info['metadata']['decimals'] == 0:
                        decimal = 18
                    else:
                        decimal = fetch_info['metadata']['decimals']

                amount_Coin = int(amount_Coin) / 10 ** decimal

                if amount_Coin == 0:
                    continue

                data_wallet.append({'key': inj_address, 'value': amount_Coin})

            except (ValueError, json.JSONDecodeError) as e:
                continue

        df_holders_native_coins = pd.DataFrame(data_wallet)
        return df_holders_native_coins
    




    # Merge this two data to one dataframe.
    async def fetch_holders(self, cw20_address, native_address):

        if cw20_address == "no_cw20":
            df_holders_native = await self.fetch_holder_native_token(native_address)

            df_holders_native.rename(columns={'value': 'native_value'}, inplace=True)
            print(df_holders_native)

            # Creating a dummy dataframe for cw20 with the same keys and default values
            df_holders_cw20 = df_holders_native.copy()
            df_holders_cw20['cw20_value'] = 0
            df_holders_cw20 = df_holders_cw20.drop(columns=['native_value'])
            print(df_holders_cw20)

        elif native_address == "no_native":
            df_holders_cw20 = await self.fetch_holders_cw20(cw20_address)

        else:
            df_holders_native = await self.fetch_holder_native_token(native_address)
            df_holders_cw20 = await self.fetch_holders_cw20(cw20_address)

            df_holders_cw20.rename(columns={'value': 'cw20_value'}, inplace=True)
            df_holders_native.rename(columns={'value': 'native_value'}, inplace=True)

        # Merging dataframes
        merged_df = pd.merge(df_holders_native, df_holders_cw20, on='key', how='outer')

        merged_df.fillna(0, inplace=True)

        merged_df['total_value'] = merged_df['native_value'] + merged_df['cw20_value']

        total_supply = merged_df['total_value'].sum()
        merged_df['percentage'] = (merged_df['total_value'] / total_supply) * 100

        merged_df = merged_df.sort_values(by='total_value', ascending=False)

        merged_df = merged_df.round({'total_value': 0, 'percentage': 5, 'native_value': 2, 'cw20_value': 2})

        merged_df = merged_df.reset_index(drop=True)
        merged_df['Top'] = merged_df.index + 1

        dict_holders = merged_df.to_dict('records')

        print(dict_holders)

        return dict_holders
    