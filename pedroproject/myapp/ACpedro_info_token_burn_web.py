import base64
from datetime import datetime
from pyinjective.client.model.pagination import PaginationOption
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network

#This info is very important in the $PEDRO website for burn page.
class PedroTokenInfo:
    memecoin = [
        {
            "name": "Pedro",
            "native": "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm",
            "cw20": "inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm",
            "denom": "inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm",
            "pool": "inj15ckgh6kdqg0x5p7curamjvqrsdw4cdzz5ky9v6",
            "creator": "inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk",
            "decimal": 18,
        }
    ]

    def __init__(self):
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)

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
            unique_holders = set()
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

                    if inj_address not in ["inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49", token['cw20']]:
                        unique_holders.add(inj_address)
                    
                    if inj_address == "inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49" or inj_address == token['cw20']:
                        burn_coin += amount_coin

            token['total_supply_cw20'] = total_supply
            token['total_burn_cw20'] = burn_coin

    async def circulation_supply(self):
        await self.burn_supply_native()
        await self.total_and_burn_supply_cw20()

        result = []
        for token in self.memecoin:
            total_burn_native = float(token.get('total_burn_native', 0))
            total_burn_cw20 = float(token.get('total_burn_cw20', 0))
            total_supply_cw20 = float(token.get('total_supply_cw20', 0))

            result.append({
                'total_burn_native': total_burn_native,
                'total_supply_cw20': total_supply_cw20,
                'total_burn_cw20': total_burn_cw20,
                'total_burn': total_burn_native + total_burn_cw20,
                'total_supply': total_supply_cw20,
                'circulation_supply': total_supply_cw20 - (total_burn_native + total_burn_cw20),
                'time': datetime.now().strftime('%d-%m-%Y %H:%M')
            })
        
        return result
    
async def main():
    pedro_token = PedroTokenInfo()
    result = await pedro_token.circulation_supply()
    print(result)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())