import asyncio
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
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise

        if holders is None:
            print("Failed to fetch holders after multiple attempts")
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
        wallet_count = df_holders_cw20.shape[0]
        print(df_holders_cw20)
        print(f"Total number of wallets: {wallet_count}")

        return df_holders_cw20


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
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise

        if holders is None:
            print("Failed to fetch holders after multiple attempts")
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

                fetch_info = await self.client.fetch_denom_metadata(denom=native_address)

                if fetch_info['metadata']['decimals'] == 0:
                    amount_Coin = int(amount_Coin) / 10 ** 18
                else:
                    amount_Coin = int(amount_Coin) / 10 ** fetch_info['metadata']['decimals']

                if amount_Coin == 0:
                    continue

                data_wallet.append({'key': inj_address, 'value': amount_Coin})

            except (ValueError, json.JSONDecodeError) as e:
                continue

        df_holders_native_coins = pd.DataFrame(data_wallet)
        wallet_count = df_holders_native_coins.shape[0]
        print(df_holders_native_coins)
        print(f"Total number of wallets: {wallet_count}")

        return df_holders_native_coins

    async def fetch_holders(self, cw20_address, native_address):
        print(cw20_address)

        df_holders_native =  await self.fetch_holder_native_token(native_address)
        df_holders_cw20 = await self.fetch_holders_cw20(cw20_address)

        # Rename the columns to distinguish between native and CW20 values
        df_holders_cw20.rename(columns={'value': 'cw20_value'}, inplace=True)
        df_holders_native.rename(columns={'value': 'native_value'}, inplace=True)

        # Merge the two dataframes on the 'key' column
        merged_df = pd.merge(df_holders_native, df_holders_cw20, on='key', how='outer')

        # Fill NaN values with 0
        merged_df.fillna(0, inplace=True)

        # Calculate the total value
        merged_df['total_value'] = merged_df['native_value'] + merged_df['cw20_value']

        # Calculate the percentage of each holder's total value
        total_supply = merged_df['total_value'].sum()
        merged_df['percentage'] = (merged_df['total_value'] / total_supply) * 100

        # Sort the merged dataframe by 'total_value' from high to low
        merged_df = merged_df.sort_values(by='total_value', ascending=False)

        # Round the values to two decimal places
        merged_df = merged_df.round({'total_value': 2, 'percentage': 2, 'native_value': 2, 'cw20_value': 2})

        # Add an ID column for the top holders starting from 1
        merged_df = merged_df.reset_index(drop=True)
        merged_df['Top'] = merged_df.index + 1

        # Print the merged dataframe
        print(merged_df)

        # Create a dictionary from the merged dataframe
        dict_holders = merged_df.to_dict('records')

        print(dict_holders)

        return dict_holders