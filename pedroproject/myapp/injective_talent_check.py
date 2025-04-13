import os
import discord
import logging
from typing import Dict, Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TalentNotifier:
    def __init__(self):
        self.discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1361021696391516341/Hw7GTfV6X9HXZiXAR-Um6u7oUI3uHqIRWxHINjIN2OqKVes7G6bEOm0qvRbCUlxIDfjr")

    async def send_talent_submission(
        self,
        form_data: Dict[str, Any],
    ) -> str:

        try:
            webhook = discord.SyncWebhook.from_url(self.discord_webhook_url)
            
            embed = discord.Embed(
                title="🎉 New Talent Submission (URGENT REVIEW NEEDED)",
                description="A new talent has submitted their information!",
                color=0x00ff00
            )
            
            embed.add_field(name="Name", value=form_data.get('name', 'Not provided'), inline=True)
            embed.add_field(name="Role", value=form_data.get('role', 'Not provided'), inline=True)
            embed.add_field(name="Injective Role", value=form_data.get('injectiveRole', 'Not provided'), inline=True)
            
            for field, value in form_data.items():
                if field not in ['name', 'role', 'injectiveRole']:
                    if isinstance(value, list):
                        display_value = ', '.join(value) if value else 'None'
                    else:
                        display_value = str(value) if value else 'None'
                    
                    embed.add_field(
                        name=field.replace('_', ' ').title(),
                        value=display_value[:1000], 
                        inline=False
                    )
            
            webhook.send(
                content=f"{"@everyone"} - **NEW TALENT SUBMISSION** 🚀",
                embed=embed,
            )
            
            logger.info(f"Sent Discord notification for {form_data.get('name')}")
            return "OK"
            
        except Exception as e:
            logger.error(f"Discord notification failed: {str(e)}")
            return "NOT OK"