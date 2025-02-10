import asyncio
import pandas as pd
import base64
import json

from pyinjective.async_client import AsyncClient
from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import Network
from django.http import JsonResponse

class NFTDrop:

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
        df = df[['owner', 'total']]
        df = df[df["owner"] != "inj1l9nh9wv24fktjvclc4zgrgyzees7rwdtx45f54"]

        total_supply = df['total'].sum()
        df['percentage'] = (df['total'] / total_supply) * 100

        dict_holders = {
            "holders": df.to_dict(orient='records')
        }

        print(dict_holders)

        return dict_holders
