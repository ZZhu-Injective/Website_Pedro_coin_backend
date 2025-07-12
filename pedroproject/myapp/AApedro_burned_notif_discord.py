import os
import base64
import discord
import logging
from typing import Dict, Any
from decimal import Decimal, InvalidOperation
from pyinjective.client.model.pagination import PaginationOption
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network
from dotenv import load_dotenv

"""
The $PEDRO dapps are actively being used to monitor token burns. Its a great indicator of engagement and transparency across the ecosystem.

These webhook display:
- Burned Amount of $PEDRO tokens
- Remaining Supply in circulation
- Reason for Burn and detailed Burner Information

All this data is streamed live through a Discord webhook, giving real-time insights into dapp activity and burn events.
"""

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PedroTokenBurnNotifier:
    def __init__(self):
        self.network = Network.mainnet()
        self.client = AsyncClient(self.network)
        self.discord_webhook_url = os.getenv("DISCORD_BURN_WEBHOOK")
        self.role_id = "1362554186574594248"
        self.explorer_base_url = "https://explorer.injective.network/transaction"

    def _format_amount(self, amount: str) -> str:
        try:
            amount_decimal = Decimal(amount)
            return "{:,.2f}".format(amount_decimal)
        except (InvalidOperation, TypeError, ValueError):
            logger.warning(f"Failed to format amount: {amount}")
            return amount
        
    async def pedro_token_burned_native_cw20(self):
        burn_coin = 0
        total_supply = 0

        all_bank_balance = await self.client.fetch_bank_balances(address="inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49")
        
        pedro_denom = "factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm"
        for balance in all_bank_balance['balances']:
            if balance['denom'] == pedro_denom:
                burn_coin += float(balance['amount']) / 10 ** 18

        holders = await self.client.fetch_all_contracts_state(
            address="inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm", 
            pagination=PaginationOption(limit=1000)
        )

        first_fetch = holders
        while holders['pagination']['nextKey']:
            pagination = PaginationOption(limit=1000, encoded_page_key=holders['pagination']['nextKey'])
            holders = await self.client.fetch_all_contracts_state(
                address="inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm", 
                pagination=pagination
            )
            first_fetch['models'] += holders['models']
            first_fetch['pagination'] = holders['pagination']

        for model in first_fetch['models']:
            value_decoded = base64.b64decode(model['value']).decode('utf-8').strip('"')

            if value_decoded.isdigit():
                amount_coin = float(value_decoded) / 10 ** 18
                total_supply += amount_coin
                
                inj_address = base64.b64decode(model['key']).decode('utf-8')[9:]

                if inj_address == "inj1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqe2hm49":
                    burn_coin += amount_coin
                    break

        return burn_coin

    async def _create_embed(self, burn_data: Dict[str, Any]) -> discord.Embed:
        burned_amount = burn_data.get('baseAmount', '0')
        burner_address = burn_data.get('srcInjectiveAddress', 'Unknown')
        burn_reason = burn_data.get('reason', 'Not specified')
        tx_hash = burn_data.get('txHash', 'Unknown')
        
        burned_amount_total = await self.pedro_token_burned_native_cw20()
        remaining_supply = str(1000000000 - burned_amount_total)

        embed = discord.Embed(
            title="🔥 $PEDRO TOKEN BURN EXECUTED",
            description="A new PEDRO token burn has been successfully processed!",
            color=0xFF4500
        )
        
        embed.add_field(
            name="📊 Burn Details",
            value=(
                f"• **Burned Amount:** {self._format_amount(burned_amount)} $PEDRO\n"
                f"• **Remaining Supply:** {self._format_amount(remaining_supply)} $PEDRO\n"
                f"• **Reason:** {burn_reason}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🧑‍💼 Burner Information",
            value=f"```{burner_address}```",
            inline=False
        )
        
        embed.add_field(
            name="🔗 Transaction Details",
            value=f"[View on Explorer]({self.explorer_base_url}/{tx_hash})",
            inline=False
        )
        
        embed.set_footer(
            text="Pedro Injective Burn System",
        )
        
        embed.timestamp = discord.utils.utcnow()
        
        return embed

    async def process_burn_transaction(
        self,
        burn_data: Dict[str, Any],
    ) -> str:
        try:
            if not all(key in burn_data for key in ('baseAmount', 'srcInjectiveAddress', 'txHash')):
                raise ValueError("Missing required burn data fields")

            embed = await self._create_embed(burn_data)
            
            webhook = discord.SyncWebhook.from_url(self.discord_webhook_url)
            
            webhook.send(
                content=f"🔥 **NEW $PEDRO BURN ALERT** 🔥 <@&{self.role_id}>",
                embed=embed,
                username="Pedro Burn Bot",
            )
            
            logger.info(f"Successfully notified about burn transaction: {burn_data.get('txHash')}")
            return "OK"
        
        except discord.DiscordException as e:
            error_msg = f"Discord API error: {str(e)}"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg

#async def test_burn_notification():
#    notifier = PedroTokenBurnNotifier()
#    
#    example_burn_data = {
#        'baseAmount': '500000',
#        'srcInjectiveAddress': 'inj1exampleaddress1234567890',
#        'txHash': 'A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0',
#        'reason': 'Monthly token burn as per project tokenomics'
#    }
#    
#    result = await notifier.process_burn_transaction(example_burn_data)
#    print(f"Notification result: {result}")
#
#import asyncio
#asyncio.run(test_burn_notification())