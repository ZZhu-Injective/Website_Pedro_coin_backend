import base64
import msgpack
import json
import asyncio
import pandas as pd
from datetime import datetime
from pyinjective.core.network import Network
from pyinjective.async_client import AsyncClient
from pyinjective.client.model.pagination import PaginationOption

class InjectiveHolders:

    def __init__(self):
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)

    _SIX_DECIMAL_NATIVES = {
        "factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt",
        "factory/inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq/KIRA",
        "factory/inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc/ffi",
        "factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS",
        "factory/inj18flmwwaxxqj8m8l5zl8xhjrnah98fcjp3gcy3e/XIII",
    }
    # base64-encoded CW20 storage prefix for the "balance" Map. Filtering on this
    # lets us skip non-balance state (token_info, marketing_info, allowances, ...)
    # without paying the cost of base64-decoding every value.
    _CW20_BALANCE_KEY_PREFIX_B64 = "AAdiYWxhbmNl"

    async def fetch_holder_native_token(self, native_address):
        denom_owners = []
        next_key = None
        while True:
            page = await self.client.fetch_denom_owners(
                denom=native_address,
                pagination=PaginationOption(limit=1000, encoded_page_key=next_key),
            )
            if page is None:
                break
            denom_owners += page['denomOwners']
            next_key = page.get('pagination', {}).get('nextKey')
            if not next_key:
                break

        decimal = 6 if native_address in self._SIX_DECIMAL_NATIVES else 18
        scale = 10 ** decimal

        data_wallet = []
        for model in denom_owners:
            value = int(model['balance']['amount']) / scale
            if value > 0:
                data_wallet.append({'key': model['address'], 'value': value})

        return pd.DataFrame(data_wallet)

    async def fetch_holders_cw20_token(self, cw20_address):
        models = []
        next_key = None
        while True:
            page = await self.client.fetch_all_contracts_state(
                address=cw20_address,
                pagination=PaginationOption(limit=1000, encoded_page_key=next_key),
            )
            if page is None:
                break
            models += page['models']
            next_key = page.get('pagination', {}).get('nextKey')
            if not next_key:
                break

        holders_cw20_wallet = []
        for model in models:
            # Cheap filter first: skip anything that isn't a "balance" entry.
            if not model['key'].startswith(self._CW20_BALANCE_KEY_PREFIX_B64):
                continue
            try:
                amount_coin = int(
                    base64.b64decode(model['value']).decode('utf-8').strip('"')
                ) / 1e18
                if amount_coin == 0:
                    continue
                inj_address = base64.b64decode(model['key']).decode('utf-8')[9:]
                holders_cw20_wallet.append({'key': inj_address, 'value': amount_coin})
            except (ValueError, json.JSONDecodeError):
                continue

        return pd.DataFrame(holders_cw20_wallet)

    async def fetch_holders(self, cw20_address, native_address):
        if cw20_address == "no_cw20":
            df_holders_native = await self.fetch_holder_native_token(native_address)
            df_holders_native.rename(columns={'value': 'native_value'}, inplace=True)
            
            df_holders_cw20 = df_holders_native.copy()
            df_holders_cw20['cw20_value'] = 0
            df_holders_cw20 = df_holders_cw20.drop(columns=['native_value'])
            
        else:
            df_holders_native, df_holders_cw20 = await asyncio.gather(
                self.fetch_holder_native_token(native_address),
                self.fetch_holders_cw20_token(cw20_address),
            )
            df_holders_cw20.rename(columns={'value': 'cw20_value'}, inplace=True)
            df_holders_native.rename(columns={'value': 'native_value'}, inplace=True)

        merged_df = pd.merge(df_holders_native, df_holders_cw20, on='key', how='outer')
        merged_df.fillna(0, inplace=True)

        merged_df['total_value'] = merged_df['native_value'] + merged_df['cw20_value']
        total_supply = merged_df['total_value'].sum()
        merged_df['percentage'] = (merged_df['total_value'] / total_supply) * 100

        merged_df = merged_df.sort_values(by='total_value', ascending=False)
        merged_df = merged_df.round({'total_value': 0, 'percentage': 5, 'native_value': 0, 'cw20_value': 0})
        merged_df = merged_df.reset_index(drop=True)
        merged_df['Top'] = merged_df.index + 1

        burn_addresses = [
            'inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49',
            'inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm',
            'inj1300xcg9naqy00fujsr9r8alwk7dh65uqu87xm8',
            'inj1fu5u29slsg2xtsj7v5la22vl4mr4ywl7wlqeck',
        ]

        creator_addresses = {
            'inj1x6u08aa3plhk3utjk7wpyjkurtwnwp6dhudh0j': 'Creator Pedro',
            'inj1y43urcm8w0vzj74ys6pwl422qtd0a278hqchw8': 'Future Pedro',
            'inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64': 'Creator Qunt',
            'inj1pr5lyuez8ak94tpuz9fs7dkpst7pkc9uuhfhvm': 'Creator Shroom',
            'inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq': 'Creator Kira',
            'inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc': 'Creator FFI',
            'inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89': 'Creator Drugs',
            'inj10aa0h5s0xwzv95a8pjhwluxcm5feeqygdk3lkm': 'Creator Sai',
            'inj18flmwwaxxqj8m8l5zl8xhjrnah98fcjp3gcy3e': 'Creator XIII'
        }

        pool_addresses = {
            'inj15ckgh6kdqg0x5p7curamjvqrsdw4cdzz5ky9v6': 'Pool Pedro/Inj',
            'inj13t5f8yvlsxxnwyz9d7fdc9ahduhxcf45qlm8xt': 'Pool Pedro/Dojo',
            'inj1r7ahhyfe35l04ffa5gnzsxjkgmnn9jkd5ds0vg': 'Pool Nonja/Inj',
            'inj1eswdzx773we5zu2mz0zcmm7l5msr8wcss8ek0f': 'Pool Kira/Inj',
            'inj1hrgkrr2fxt4nrp8dqf7acmgrglfarz88qk3sms': 'Pool FFI/Inj',
            'inj1y6x5kfc5m7vhmy8dfry2vdqsvrnqrnwmw4rea0': 'Pool Drugs/Inj',
            'inj18nyltfvkyrx4wxfpdd6sn9l8wmqfr6t63y7nse': 'Pool Sai/Shroom',
            'inj1m35kyjuegq7ruwgx787xm53e5wfwu6n5uadurl': 'Pool Shroom/Inj',
            'inj14vnmw2wee3xtrsqfvpcqg35jg9v7j2vdpzx0kk': 'Pool Mito'
        }

        merged_df['info'] = merged_df['key'].apply(
            lambda x: 'Burn Address' if x in burn_addresses else creator_addresses.get(x, pool_addresses.get(x, '-'))
        )


        filtered_df = merged_df[~merged_df['key'].isin(burn_addresses + list(pool_addresses.keys()))]

        top_10_sum = round(filtered_df['percentage'].nlargest(10).sum())
        top_20_sum = round(filtered_df['percentage'].nlargest(20).sum())
        top_50_sum = round(filtered_df['percentage'].nlargest(50).sum())

        if native_address == "factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt":

            removed_sum_native = merged_df[merged_df['total_value'] <= 2]['native_value'].sum()
            removed_sum_cw20 = merged_df[merged_df['total_value'] <= 2]['cw20_value'].sum()

            total_supply = merged_df['total_value'].sum()
            percentage = (removed_sum_native / total_supply) * 100

            lowest_top = merged_df['Top'].max() + 1

            new_row = pd.DataFrame({
                'key': ['lower than 2 Qunt'],
                'native_value': [removed_sum_native],
                'cw20_value': [removed_sum_cw20],
                'total_value': [removed_sum_native + removed_sum_cw20],
                'percentage': [percentage],
                'Top': [lowest_top],
                'info': ['-']
            })

            merged_df = merged_df[merged_df['total_value'] >= 3]
            merged_df = pd.concat([merged_df, new_row], ignore_index=True)

        current_time = datetime.now().strftime('%d-%m-%Y %H:%M')
        total_holders = len(merged_df)
        dict_holders = {
            "timestamp": current_time,
            "totalholders": total_holders,
            "top_10": top_10_sum,
            "top_20": top_20_sum,
            "top_50": top_50_sum,
            "holders": merged_df.to_dict('records')
        }

        msgpack_data = msgpack.packb(dict_holders, use_bin_type=True)

        return msgpack_data



