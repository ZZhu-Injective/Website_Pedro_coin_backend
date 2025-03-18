import os
import discord
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScamChecker:
    def __init__(self):
        self.discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1351537591710650368/8HzPZdfsqDI-X-IDBrcov-j8DrgpDaP1Ujk23fQxXoWK2O8kfDcjTKPyRUHBXDvIUYR1")

    async def _send_to_discord(self, address, project, info, discord_name, user_id_to_tag="everyone"):
        try:
            webhook = discord.SyncWebhook.from_url(self.discord_webhook_url)
            
            tag_message = f"@{user_id_to_tag}" if user_id_to_tag else ""
            
            message = (
                f"{tag_message}\n"
                f"**Scam Submission**:\n"
                f"```\n"
                f"Address: {address}\n"
                f"Project: {project}\n"
                f"Info: {info}\n"
                f"Submitted DiscordName: {discord_name}\n"
                f"```"
            )
            
            webhook.send(message)
            return "OK"
        except Exception as e:
            return "NOT OK"
