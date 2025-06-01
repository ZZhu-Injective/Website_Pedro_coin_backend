import base64
import json
import backoff
import pandas as pd
from pyinjective.core.network import Network
from pyinjective.async_client import AsyncClient
from pyinjective.client.model.pagination import PaginationOption

"""
Check if you hold our token (100.000) or NFTs (1)!
"""

class PedroLogin:
    
    memecoin = [
        {
            "name": "Pedro",
            "native": "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm",
            "cw20": "inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm"
        }
    ]
    
    def __init__(self, address):
        self.address = address
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)

    def remove_balance_prefix(self, key):
        if isinstance(key, str) and key.startswith('balance'):
            return key[9:]
        return key

    @backoff.on_exception(backoff.expo, Exception, max_tries=5)
    async def fetch_bank_balances_with_retry(self):
        return await self.client.fetch_bank_balances(address=self.address)
    
    async def fetch_native_balance(self) -> float:
        all_bank_balances = await self.fetch_bank_balances_with_retry()
        native_balances = [
            balance for balance in all_bank_balances.get('balances', []) 
            if balance['denom'] in [coin['native'] for coin in self.memecoin]
        ]

        total_native_balance = 0.0
        for balance in native_balances:
            if balance['denom'] == "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm":
                balance['amount'] = float(balance['amount']) / 10**18
                total_native_balance += balance['amount']
        return total_native_balance
    
    async def fetch_holder_nft(self) -> None:
        pagination = PaginationOption(limit=1000)
        
        contract_history = await self.client.fetch_all_contracts_state(address="inj1uq453kp4yda7ruc0axpmd9vzfm0fj62padhe0p", pagination=pagination)
        
        A = contract_history
        
        total_models = len(contract_history['models'])
        
        while contract_history['pagination']['nextKey'] and total_models < 100000:
            pagination = PaginationOption(limit=1000, encoded_page_key=contract_history['pagination']['nextKey'])
            contract_history = await self.client.fetch_all_contracts_state(address="inj1uq453kp4yda7ruc0axpmd9vzfm0fj62padhe0p", pagination=pagination)
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

        df = df.reset_index(drop=True)

        return df[df['owner'] == self.address]        
        

    async def check(self) -> str:
        native_balance = await self.fetch_native_balance()
        native_nft = await self.fetch_holder_nft()

        wallet = native_nft['owner'].values[0]
        nft_hold = int(native_nft['total'].values[0])
        token_hold = round(float(native_balance))
        
        check_status = "yes" if (nft_hold > 0) or (token_hold > 100000) else "no"

        return {
            "wallet": wallet,
            "nft_hold": nft_hold,
            "token_hold": token_hold,
            "check": check_status
        }