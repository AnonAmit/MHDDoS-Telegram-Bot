import logging
from typing import Dict, List, Optional, Any, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler

import users

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Admin command handlers
async def admin_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin help commands."""
    if not users.is_user_admin(update.effective_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    await update.message.reply_text(
        "🔐 Admin Commands:\n\n"
        "/admin_users - List all users\n"
        "/admin_user [user_id] - View user details\n"
        "/admin_make_admin [user_id] - Make a user an admin\n"
        "/admin_transactions - View pending transactions\n"
        "/admin_approve [transaction_id] [optional_note] - Approve a transaction\n"
        "/admin_reject [transaction_id] [reason] - Reject a transaction\n"
        "/admin_plans - List all subscription plans\n"
        "/admin_plan [plan_id] - View plan details\n"
        "/admin_generate_codes [plan_id] [count] - Generate redeem codes\n"
        "/admin_stats - View system statistics"
    )

async def admin_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all users."""
    if not users.is_user_admin(update.effective_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    all_users = users.get_all_users()
    if not all_users:
        await update.message.reply_text("No users found.")
        return
    
    # Create user list with basic info
    user_list = []
    for user_id, user_data in all_users.items():
        subscription = user_data.get("subscription", {})
        status = "Active" if subscription.get("active", False) else "Inactive"
        plan = subscription.get("plan", "None")
        
        user_list.append(
            f"👤 User ID: {user_id}\n"
            f"Username: {user_data.get('username', 'N/A')}\n"
            f"Role: {user_data.get('role', 'N/A')}\n"
            f"Plan: {plan}\n"
            f"Status: {status}\n"
        )
    
    # Split into chunks if too many users
    user_chunks = [user_list[i:i + 10] for i in range(0, len(user_list), 10)]
    
    for i, chunk in enumerate(user_chunks):
        message = f"📋 Users List (Page {i+1}/{len(user_chunks)}):\n\n"
        message += "\n---\n".join(chunk)
        await update.message.reply_text(message)

async def admin_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View user details."""
    if not users.is_user_admin(update.effective_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Please provide a user ID. Usage: /admin_user [user_id]")
        return
    
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID. Please provide a numeric ID.")
        return
    
    user_data = users.get_user(user_id)
    if not user_data:
        await update.message.reply_text(f"User with ID {user_id} not found.")
        return
    
    # Format subscription info
    subscription = user_data.get("subscription", {})
    if subscription.get("active", False):
        import time
        from datetime import datetime
        
        start_date = subscription.get("start_date")
        end_date = subscription.get("end_date")
        
        if start_date:
            start_date_str = datetime.fromtimestamp(start_date).strftime("%Y-%m-%d")
        else:
            start_date_str = "N/A"
            
        if end_date:
            end_date_str = datetime.fromtimestamp(end_date).strftime("%Y-%m-%d")
            days_left = max(0, (end_date - int(time.time())) // 86400)
        else:
            end_date_str = "N/A"
            days_left = 0
        
        subscription_info = (
            f"🔹 Plan: {subscription.get('plan', 'N/A')}\n"
            f"🔹 Start Date: {start_date_str}\n"
            f"🔹 End Date: {end_date_str}\n"
            f"🔹 Days Left: {days_left}\n"
            f"🔹 Attacks Used: {subscription.get('attacks_used', 0)}\n"
            f"🔹 Attacks Limit: {subscription.get('attacks_limit', 0)}\n"
            f"🔹 Status: Active"
        )
    else:
        subscription_info = "No active subscription"
    
    # Get recent attack history
    attack_history = user_data.get("attack_history", [])
    recent_attacks = attack_history[-5:] if attack_history else []
    
    attack_info = ""
    if recent_attacks:
        from datetime import datetime
        
        attack_list = []
        for attack in reversed(recent_attacks):
            date_str = datetime.fromtimestamp(attack.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M")
            attack_list.append(
                f"• {date_str}: {attack.get('method', 'N/A')} on {attack.get('target', 'N/A')}"
            )
        
        attack_info = "Recent Attacks:\n" + "\n".join(attack_list)
    else:
        attack_info = "No recent attacks"
    
    # Format payment history
    payment_history = user_data.get("payment_history", [])
    payment_info = f"Payment History: {len(payment_history)} transactions"
    
    # Put it all together
    user_info = (
        f"👤 User Profile - ID: {user_id}\n\n"
        f"Username: {user_data.get('username', 'N/A')}\n"
        f"Name: {user_data.get('first_name', 'N/A')}\n"
        f"Role: {user_data.get('role', 'N/A')}\n"
        f"Created: {datetime.fromtimestamp(user_data.get('created_at', 0)).strftime('%Y-%m-%d')}\n\n"
        f"📅 Subscription:\n{subscription_info}\n\n"
        f"🚀 {attack_info}\n\n"
        f"💳 {payment_info}"
    )
    
    await update.message.reply_text(user_info)

async def admin_make_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Make a user an admin."""
    if not users.is_user_admin(update.effective_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Please provide a user ID. Usage: /admin_make_admin [user_id]")
        return
    
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID. Please provide a numeric ID.")
        return
    
    user_data = users.get_user(user_id)
    if not user_data:
        await update.message.reply_text(f"User with ID {user_id} not found.")
        return
    
    if user_data.get("role") == users.ROLE_ADMIN:
        await update.message.reply_text(f"User with ID {user_id} is already an admin.")
        return
    
    # Update user role
    user_data["role"] = users.ROLE_ADMIN
    users.save_users()
    
    await update.message.reply_text(f"User with ID {user_id} has been made an admin.")

async def admin_transactions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View pending transactions."""
    if not users.is_user_admin(update.effective_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    pending_transactions = users.get_pending_transactions()
    if not pending_transactions:
        await update.message.reply_text("No pending transactions found.")
        return
    
    # Create transaction list
    from datetime import datetime
    
    transaction_list = []
    for transaction in pending_transactions:
        user_id = transaction.get("user_id")
        user_data = users.get_user(user_id)
        username = user_data.get("username", "Unknown") if user_data else "Unknown"
        
        created_at = datetime.fromtimestamp(transaction.get("created_at", 0)).strftime("%Y-%m-%d %H:%M")
        
        transaction_list.append(
            f"🧾 Transaction ID: {transaction.get('id')}\n"
            f"User: {username} (ID: {user_id})\n"
            f"Plan: {transaction.get('plan_id')}\n"
            f"Amount: {transaction.get('amount')} {transaction.get('currency')}\n"
            f"Method: {transaction.get('payment_method')}\n"
            f"Payment ID: {transaction.get('payment_id')}\n"
            f"Date: {created_at}\n"
            f"Status: {transaction.get('status')}"
        )
    
    # Split into chunks if too many transactions
    transaction_chunks = [transaction_list[i:i + 5] for i in range(0, len(transaction_list), 5)]
    
    for i, chunk in enumerate(transaction_chunks):
        message = f"📋 Pending Transactions (Page {i+1}/{len(transaction_chunks)}):\n\n"
        message += "\n\n".join(chunk)
        await update.message.reply_text(message)

async def admin_approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Approve a transaction."""
    if not users.is_user_admin(update.effective_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Please provide a transaction ID. Usage: /admin_approve [transaction_id] [optional_note]")
        return
    
    transaction_id = context.args[0]
    note = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    
    # Try to approve the transaction
    success = users.approve_transaction(transaction_id, update.effective_user.id, note)
    
    if success:
        transaction = users.get_transaction(transaction_id)
        user_id = transaction.get("user_id")
        plan_id = transaction.get("plan_id")
        
        await update.message.reply_text(
            f"✅ Transaction {transaction_id} has been approved.\n"
            f"User ID: {user_id}\n"
            f"Plan: {plan_id}"
        )
    else:
        await update.message.reply_text(f"❌ Failed to approve transaction {transaction_id}. Check the ID and status.")

async def admin_reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reject a transaction."""
    if not users.is_user_admin(update.effective_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Please provide a transaction ID and reason. Usage: /admin_reject [transaction_id] [reason]")
        return
    
    transaction_id = context.args[0]
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
    
    # Try to reject the transaction
    success = users.reject_transaction(transaction_id, update.effective_user.id, reason)
    
    if success:
        await update.message.reply_text(f"❌ Transaction {transaction_id} has been rejected.")
    else:
        await update.message.reply_text(f"❌ Failed to reject transaction {transaction_id}. Check the ID and status.")

async def admin_plans_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all subscription plans."""
    if not users.is_user_admin(update.effective_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    plans = users.get_subscription_plans()
    if not plans:
        await update.message.reply_text("No subscription plans found.")
        return
    
    # Create plan list
    plan_list = []
    for plan_id, plan_data in plans.items():
        plan_list.append(
            f"📦 Plan: {plan_id}\n"
            f"Name: {plan_data.get('name')}\n"
            f"Price: {plan_data.get('price')} {plan_data.get('currency')}\n"
            f"Duration: {plan_data.get('duration_days')} days"
        )
    
    message = "📋 Subscription Plans:\n\n"
    message += "\n\n".join(plan_list)
    
    await update.message.reply_text(message)

async def admin_plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View plan details."""
    if not users.is_user_admin(update.effective_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Please provide a plan ID. Usage: /admin_plan [plan_id]")
        return
    
    plan_id = context.args[0]
    plans = users.get_subscription_plans()
    
    if plan_id not in plans:
        await update.message.reply_text(f"Plan with ID {plan_id} not found.")
        return
    
    plan_data = plans[plan_id]
    
    plan_info = (
        f"📦 Plan: {plan_id}\n\n"
        f"Name: {plan_data.get('name')}\n"
        f"Description: {plan_data.get('description')}\n"
        f"Price: {plan_data.get('price')} {plan_data.get('currency')}\n"
        f"Duration: {plan_data.get('duration_days')} days\n\n"
        f"Max Attacks: {plan_data.get('max_attacks')}\n"
        f"Max Duration: {plan_data.get('max_duration')} seconds\n"
        f"Max Threads: {plan_data.get('max_threads')}"
    )
    
    await update.message.reply_text(plan_info)

async def admin_generate_codes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate redeem codes."""
    if not users.is_user_admin(update.effective_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Please provide a plan ID and count. Usage: /admin_generate_codes [plan_id] [count]")
        return
    
    plan_id = context.args[0]
    count = 1
    
    if len(context.args) > 1:
        try:
            count = int(context.args[1])
            if count < 1 or count > 20:  # Set reasonable limits
                count = 1
        except ValueError:
            count = 1
    
    # Try to generate codes
    codes = users.generate_redeem_code(update.effective_user.id, plan_id, count)
    
    if codes:
        message = f"✅ Generated {len(codes)} redeem codes for plan {plan_id}:\n\n"
        message += "\n".join(codes)
        await update.message.reply_text(message)
    else:
        await update.message.reply_text(f"❌ Failed to generate redeem codes. Check if plan {plan_id} exists.")

async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View system statistics."""
    if not users.is_user_admin(update.effective_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    all_users = users.get_all_users()
    
    # Count users by role
    role_counts = {
        "admin": 0,
        "premium": 0,
        "standard": 0,
        "trial": 0
    }
    
    active_subscriptions = 0
    total_attacks = 0
    
    for user_id, user_data in all_users.items():
        role = user_data.get("role", "trial")
        if role in role_counts:
            role_counts[role] += 1
        
        subscription = user_data.get("subscription", {})
        if subscription.get("active", False):
            active_subscriptions += 1
        
        attack_history = user_data.get("attack_history", [])
        total_attacks += len(attack_history)
    
    # Get transaction stats
    import time
    from datetime import datetime, timedelta
    
    transactions_data = users.transactions_data
    pending_count = len([t for t in transactions_data if t.get("status") == "pending"])
    approved_count = len([t for t in transactions_data if t.get("status") == "approved"])
    rejected_count = len([t for t in transactions_data if t.get("status") == "rejected"])
    
    # Get recent transactions (last 7 days)
    seven_days_ago = int(time.time()) - (7 * 86400)
    recent_transactions = [t for t in transactions_data if t.get("created_at", 0) >= seven_days_ago]
    recent_count = len(recent_transactions)
    
    stats_message = (
        "📊 System Statistics\n\n"
        f"👥 Users:\n"
        f"Total Users: {len(all_users)}\n"
        f"Admins: {role_counts['admin']}\n"
        f"Premium Users: {role_counts['premium']}\n"
        f"Standard Users: {role_counts['standard']}\n"
        f"Trial Users: {role_counts['trial']}\n\n"
        f"📅 Subscriptions:\n"
        f"Active Subscriptions: {active_subscriptions}\n\n"
        f"🚀 Attacks:\n"
        f"Total Attacks: {total_attacks}\n\n"
        f"💳 Transactions:\n"
        f"Total Transactions: {len(transactions_data)}\n"
        f"Pending: {pending_count}\n"
        f"Approved: {approved_count}\n"
        f"Rejected: {rejected_count}\n"
        f"Last 7 Days: {recent_count}"
    )
    
    await update.message.reply_text(stats_message)

# Dictionary of admin command handlers
admin_handlers = {
    "admin_help": CommandHandler("admin_help", admin_help_command),
    "admin_users": CommandHandler("admin_users", admin_users_command),
    "admin_user": CommandHandler("admin_user", admin_user_command),
    "admin_make_admin": CommandHandler("admin_make_admin", admin_make_admin_command),
    "admin_transactions": CommandHandler("admin_transactions", admin_transactions_command),
    "admin_approve": CommandHandler("admin_approve", admin_approve_command),
    "admin_reject": CommandHandler("admin_reject", admin_reject_command),
    "admin_plans": CommandHandler("admin_plans", admin_plans_command),
    "admin_plan": CommandHandler("admin_plan", admin_plan_command),
    "admin_generate_codes": CommandHandler("admin_generate_codes", admin_generate_codes_command),
    "admin_stats": CommandHandler("admin_stats", admin_stats_command)
} 