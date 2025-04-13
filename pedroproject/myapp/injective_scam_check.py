import os
import discord
import logging
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScamChecker:
    def __init__(self):
        self.discord_webhook_url = os.getenv(
            "DISCORD_WEBHOOK_URL", 
            "https://discord.com/api/webhooks/1351537591710650368/8HzPZdfsqDI-X-IDBrcov-j8DrgpDaP1Ujk23fQxXoWK2O8kfDcjTKPyRUHBXDvIUYR1"
        )

    async def send_scam_report(
        self,
        address: str,
        project: str,
        info: str,
        discord_name: str,
        user_id_to_tag: Optional[str] = "everyone",
        additional_data: Optional[Dict[str, Any]] = None
    ) -> str:
        try:
            webhook = discord.SyncWebhook.from_url(self.discord_webhook_url)
            
            embed = discord.Embed(
                title="🚨 New Scam Report",
                description="A potential scam has been reported!",
                color=0xFF0000 
            )
            
            embed.add_field(name="Wallet Address", value=f"`{address}`", inline=False)
            embed.add_field(name="Project", value=project, inline=True)
            embed.add_field(name="Submitted By", value=discord_name, inline=True)
            
            embed.add_field(
                name="Scam Details", 
                value=f"```\n{info}\n```" if info else "No details provided",
                inline=False
            )
            
            if additional_data:
                for field, value in additional_data.items():
                    if value:  
                        embed.add_field(
                            name=field.replace('_', ' ').title(),
                            value=str(value)[:1024], 
                            inline=False
                        )
            
            embed.set_footer(text="⚠️ Please investigate immediately ⚠️")
        
            
            webhook.send(
                content=f"{''} **URGENT: SCAM REPORT**",
                embed=embed,
            )
            
            logger.info(f"Successfully sent scam report for {project}")
            return "OK"
            
        except Exception as e:
            logger.error(f"Failed to send scam report: {str(e)}")
            return "NOT OK"