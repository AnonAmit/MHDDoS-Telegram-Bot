#!/usr/bin/env python3
"""
Proxy Updater for MHDDoS Telegram Bot
Automatically updates proxy lists from various sources
"""

import os
import time
import requests
import logging
import schedule
from datetime import datetime
from config import MHDDOS_PATH, PROXY_PATH

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("proxy_updater.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("proxy_updater")

# Proxy sources
PROXY_SOURCES = {
    "http": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    ],
    "socks4": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
    ],
    "socks5": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    ]
}

def download_proxies(proxy_type):
    """Download proxies from sources and save to file"""
    if proxy_type not in PROXY_SOURCES:
        logger.error(f"Invalid proxy type: {proxy_type}")
        return False
    
    sources = PROXY_SOURCES[proxy_type]
    proxies = set()  # Use a set to avoid duplicates
    
    for source in sources:
        try:
            logger.info(f"Downloading {proxy_type} proxies from {source}")
            response = requests.get(source, timeout=30)
            
            if response.status_code == 200:
                # Add valid proxies to the set
                for line in response.text.splitlines():
                    line = line.strip()
                    if line and ":" in line:  # Simple validation
                        proxies.add(line)
                logger.info(f"Downloaded {len(response.text.splitlines())} proxies from {source}")
            else:
                logger.warning(f"Failed to download from {source}: Status code {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error downloading from {source}: {str(e)}")
    
    # Save proxies to file
    if proxies:
        filename = f"{proxy_type}_{int(time.time())}.txt"
        proxy_file_path = os.path.join(MHDDOS_PATH, filename)
        
        with open(proxy_file_path, "w") as f:
            f.write("\n".join(proxies))
        
        # Create/update symlink or copy to standard location
        proxy_path = os.path.join(MHDDOS_PATH, PROXY_PATH)
        if os.path.exists(proxy_path):
            os.remove(proxy_path)
        
        # On Windows, symlinks might not work, so copy the file
        if os.name == 'nt':
            import shutil
            shutil.copy2(proxy_file_path, proxy_path)
        else:
            os.symlink(filename, proxy_path)
        
        logger.info(f"Saved {len(proxies)} {proxy_type} proxies to {proxy_path}")
        return True
    
    logger.warning(f"No {proxy_type} proxies found from any source")
    return False

def update_all_proxies():
    """Update all proxy types"""
    logger.info("Starting proxy update job")
    
    success = False
    for proxy_type in PROXY_SOURCES:
        if download_proxies(proxy_type):
            success = True
    
    if success:
        logger.info("Proxy update completed successfully")
    else:
        logger.error("Failed to update any proxy lists")
    
    return success

def main():
    """Main function"""
    logger.info("Proxy Updater Started")
    
    # Update immediately on start
    update_all_proxies()
    
    # Schedule updates every 6 hours
    schedule.every(6).hours.do(update_all_proxies)
    
    # Run the scheduler
    logger.info("Scheduler running. Press Ctrl+C to exit.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Proxy Updater stopped")

if __name__ == "__main__":
    main() 