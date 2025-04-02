import os
import random
import requests
import time
from datetime import datetime, timedelta
import logging
import signal
import sys

WEBHOOK_URL = "https://discord.com/api/webhooks/1357004853259403416/SHndHHoJJA5qe_XSlEUQjk7oPf0FmnLPhjB3uzWfLcxhhvAQB_fOLPIaJZYz8Q2wlalH"
FOLDER_PATH = "/root/Website_Pedro_coin_backend/pedroproject/myapp/art"
POST_INTERVAL = 3 * 60 * 60

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ArtBot:
    def __init__(self):
        self.running = True
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def handle_signal(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def get_random_file(self):
        """Get a random file from the specified folder"""
        try:
            files = [f for f in os.listdir(FOLDER_PATH) 
                     if os.path.isfile(os.path.join(FOLDER_PATH, f))]
            if not files:
                logger.warning("No files found in the specified folder")
                return None
            return random.choice(files)
        except Exception as e:
            logger.error(f"Error accessing art folder: {str(e)}")
            return None

    def send_to_discord(self, file_path):
        """Send file to Discord via webhook"""
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            files = {'file': (os.path.basename(file_path), file_data)}
            payload = {
                "content": "Random Raccoon Art For You",
                "username": "Art Bot"
            }
            
            response = requests.post(WEBHOOK_URL, data=payload, files=files, timeout=30)
            if response.status_code == 204:
                return True
            logger.error(f"Discord API error: {response.status_code} - {response.text}")
            return False
        except Exception as e:
            logger.error(f"Error sending to Discord: {str(e)}")
            return False

    def run(self):
        logger.info("Starting Art Bot service")
        logger.info(f"Art folder: {FOLDER_PATH}")
        logger.info(f"Post interval: {POST_INTERVAL/3600} hours")
        
        while self.running:
            try:
                next_post = datetime.now() + timedelta(seconds=POST_INTERVAL)
                logger.info(f"Next post scheduled for {next_post.strftime('%Y-%m-%d %H:%M:%S')}")
                
                random_file = self.get_random_file()
                if random_file:
                    file_path = os.path.join(FOLDER_PATH, random_file)
                    if self.send_to_discord(file_path):
                        logger.info(f"Successfully posted {random_file} to Discord")
                    else:
                        logger.warning(f"Failed to post {random_file}")
                
                for _ in range(POST_INTERVAL):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {str(e)}")
                time.sleep(60) 
        
        logger.info("Art Bot service stopped gracefully")

if __name__ == "__main__":
    if not os.path.exists(FOLDER_PATH):
        logger.error(f"Art folder does not exist: {FOLDER_PATH}")
        sys.exit(1)
    
    if not os.listdir(FOLDER_PATH):
        logger.error(f"Art folder is empty: {FOLDER_PATH}")
        sys.exit(1)
    
    bot = ArtBot()
    bot.run()