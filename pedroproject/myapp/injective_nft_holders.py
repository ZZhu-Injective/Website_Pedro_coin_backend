import pandas as pd
import base64
import json
from datetime import datetime

from pyinjective.async_client import AsyncClient
from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import Network

class InjectiveHolders2:

    def __init__(self):
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)

    def remove_balance_prefix(self, key):
        if isinstance(key, str) and key.startswith('balance'):
            return key[9:]
        return key

    async def fetch_holder_nft(self, cw20_address) -> None:
        limit = 1000
        pagination = PaginationOption(limit=limit)
        
        contract_history = await self.client.fetch_all_contracts_state(address=cw20_address, pagination=pagination)
        A = contract_history
        
        total_models = len(contract_history['models'])
        
        while contract_history['pagination']['nextKey'] and total_models < 100000:
            pagination = PaginationOption(limit=limit, encoded_page_key=contract_history['pagination']['nextKey'])
            contract_history = await self.client.fetch_all_contracts_state(address=cw20_address, pagination=pagination)
            A['models'] += contract_history['models']
            A['pagination'] = contract_history['pagination']
            
            total_models += len(contract_history['models'])
        

        decoded_values = []
        for item in A['models']:
            try:
                if isinstance(item['key'], str) and isinstance(item['value'], str):
                    decoded_value = base64.b64decode(item['value']).decode('utf-8')
                    decoded_dict = json.loads(decoded_value)
                    decoded_dict['key'] = self.remove_balance_prefix(item['key'])
                    decoded_values.append(decoded_dict)
            except Exception as e:
                continue

        df = pd.DataFrame(decoded_values)    
        df = df.dropna(subset=['token_id'])
        df['total'] = df.groupby('owner')['owner'].transform('count')
        df = df.drop_duplicates(subset=['owner'])        
        df['percentage'] = (df['total'] / df['total'].sum()) * 100
        
        df_filtered = df[['token_id', 'owner', 'total', 'percentage']]
        df_filtered = df_filtered.sort_values(by='percentage', ascending=False)

        df_filtered = df_filtered.reset_index(drop=True)
        df_filtered['Top'] = df_filtered.index + 1

        df_filtered = df_filtered.round({'total': 0, 'percentage': 5})


        burn_addresses = [
            'inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49',
        ]

        creator_addresses = {
            'inj1rlyp66l2macpfqer2tg57a6alvgv7ydvrlfwrh': 'Creator Ninja',
            'inj1mtg6q37hscvq2f5slywh0x72x3t20gu3lrh4l9': 'Creator Culd ob Nonja',
            'inj1whx0q7mcqj2c9w3apw336wpfwsplf934ra0gnl': 'Creator Paradyze', 
            'inj1nv8xeg4g0tcg9nejfy9q94wjcqlfkckh4ahe3n': 'Creator Cult of Anons',
            'inj18xsczx27lanjt40y9v79q0v57d76j2s8ctj85x': 'Creator Hobos',
            'inj1luaw0t5y9lqczcmt4msejvyk5zz55e25wv3zj7': 'Creator Injective Quants',
            'inj1lkue0nc46ct8kcztq5d8akq8dmmksrp4w288rs': 'Creator Injective Pepes',
            'inj15faahsvwuedx7mtt4gcysusu2ll3lc2wv9dler': 'Creator B Side',
            'inj1xdt094h46d5vhw0xa2n3av8j2lhrksdpnfh75a': 'Creator Warrior Panda'
        }

        pool_addresses = {
            'inj1l9nh9wv24fktjvclc4zgrgyzees7rwdtx45f54': 'Talis Marketplace',
        }

        df_filtered['info'] = df_filtered['owner'].apply(
            lambda x: 'Burn Address' if x in burn_addresses else creator_addresses.get(x, pool_addresses.get(x, '-'))
        )

        df_filtered2 = df_filtered[~df_filtered['owner'].isin(burn_addresses + list(pool_addresses.keys()))]

        top_10_sum = round(df_filtered2['percentage'].nlargest(10).sum())
        top_20_sum = round(df_filtered2['percentage'].nlargest(20).sum())
        top_50_sum = round(df_filtered2['percentage'].nlargest(50).sum())

        current_time = datetime.now().strftime('%d-%m-%Y %H:%M')
        total_holders = len(df_filtered)
        dict_holders = {
            "timestamp": current_time,
            "totalholders": total_holders,
            "top_10": top_10_sum,
            "top_20": top_20_sum,
            "top_50": top_50_sum,
            "holders": df_filtered.to_dict('records')
        }

        return dict_holders