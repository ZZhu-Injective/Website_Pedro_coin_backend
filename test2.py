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
        start_time = time.time()

        async def fetch_page(pagination_key=None):
            pagination = PaginationOption(limit=2000, encoded_page_key=pagination_key)  # Increase limit for fewer API calls
            return await self.client.fetch_denom_owners(denom=native_address, pagination=pagination)

        holders = await fetch_page()
        if holders is None or 'denomOwners' not in holders:
            return pd.DataFrame()

        denom_owners = holders['denomOwners']
        next_key = holders['pagination'].get('nextKey')

        # Fetch additional pages concurrently
        tasks = []
        while next_key:
            tasks.append(fetch_page(next_key))
            if len(tasks) >= 5:  # Batch size for concurrent fetch
                results = await asyncio.gather(*tasks)
                for result in results:
                    denom_owners.extend(result['denomOwners'])
                    next_key = result['pagination'].get('nextKey')
                tasks = []
        
        # Process remaining tasks
        if tasks:
            results = await asyncio.gather(*tasks)
            for result in results:
                denom_owners.extend(result['denomOwners'])

        # Determine decimal points
        decimal = 6 if native_address in [
            "factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt",
            "factory/inj1xy3kvlr4q4wdd6lrelsrw2fk2ged0any44hhwq/KIRA",
            "factory/inj1cw3733laj4zj3ep5ndx2sfz0aed0u03kwt6ucc/ffi",
            "factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS"
        ] else 18

        # Filter and transform data
        data_wallet = [
            {'key': owner['address'], 'value': int(owner['balance']['amount']) / 10 ** decimal}
            for owner in denom_owners
            if int(owner['balance']['amount']) > 0
        ]

        df = pd.DataFrame(data_wallet)

        end_time = time.time()
        print(f"Function runtime: {end_time - start_time} seconds")
        print(df)
        return df

async def main():
    token_info = InjectiveHolders()
    await token_info.fetch_holder_native_token("factory/inj127l5a2wmkyvucxdlupqyac3y0v6wqfhq03ka64/qunt")


asyncio.run(main())