import logging
from typing import Dict, List, Optional, Any, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import users

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# User command handlers
async def plans_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View available subscription plans."""
    plans = users.get_subscription_plans()
    
    # Get user's current plan
    user = users.get_user(update.effective_user.id)
    current_plan = None
    
    if user:
        subscription = user.get("subscription", {})
        if subscription.get("active", False):
            current_plan = subscription.get("plan")
    
    # Create keyboard for plans
    keyboard = []
    
    for plan_id, plan_data in plans.items():
        # Skip trial plan in display
        if plan_id == "trial":
            continue
        
        if plan_id == current_plan:
            button_text = f"✅ {plan_data.get('name')} (Current)"
        else:
            button_text = f"{plan_data.get('name')} - {plan_data.get('price')} {plan_data.get('currency')}"
        
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"plan:{plan_id}")])
    
    keyboard.append([InlineKeyboardButton("💳 Payment Instructions", callback_data="payment_info")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📦 Available Subscription Plans:\n\n"
        "Select a plan to view details:",
        reply_markup=reply_markup
    )

async def subscription_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View current subscription details."""
    user_id = update.effective_user.id
    user = users.get_user(user_id)
    
    if not user:
        # Add the user if they don't exist
        users.add_user(
            user_id,
            update.effective_user.username or "Unknown",
            update.effective_user.first_name or "Unknown"
        )
        user = users.get_user(user_id)
    
    subscription = user.get("subscription", {})
    
    if not subscription.get("active", False):
        keyboard = [[InlineKeyboardButton("📦 View Plans", callback_data="view_plans")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "❌ You don't have an active subscription.\n\n"
            "Purchase a subscription to use the bot's attack features.",
            reply_markup=reply_markup
        )
        return
    
    # Format subscription info
    import time
    from datetime import datetime
    
    plan_id = subscription.get("plan")
    plan_data = users.get_subscription_plans().get(plan_id, {})
    
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
    
    attacks_used = subscription.get("attacks_used", 0)
    attacks_limit = subscription.get("attacks_limit", 0)
    attacks_remaining = "Unlimited" if attacks_limit <= 0 else str(attacks_limit - attacks_used)
    
    keyboard = [
        [InlineKeyboardButton("📦 Upgrade Plan", callback_data="view_plans")],
        [InlineKeyboardButton("📊 View Attack History", callback_data="attack_history")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📅 Your Subscription\n\n"
        f"Plan: {plan_data.get('name', plan_id)}\n"
        f"Status: Active\n"
        f"Start Date: {start_date_str}\n"
        f"End Date: {end_date_str}\n"
        f"Days Remaining: {days_left}\n\n"
        f"Attacks Used: {attacks_used}\n"
        f"Attacks Remaining: {attacks_remaining}\n\n"
        f"Max Duration: {plan_data.get('max_duration', 0)} seconds per attack\n"
        f"Max Threads: {plan_data.get('max_threads', 0)} threads per attack",
        reply_markup=reply_markup
    )

async def payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View payment options and instructions."""
    # Show payment options with inline keyboard
    keyboard = [
        [InlineKeyboardButton("💰 Cryptocurrency", callback_data="payment:crypto")],
        [InlineKeyboardButton("💳 UPI", callback_data="payment:upi")],
        [InlineKeyboardButton("🎁 Gift Card", callback_data="payment:giftcard")],
        [InlineKeyboardButton("🔑 Redeem Code", callback_data="payment:redeem")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💵 Payment Options\n\n"
        "Select a payment method to see instructions:",
        reply_markup=reply_markup
    )

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Redeem a subscription code."""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Please provide a redeem code.\nUsage: /redeem [code]"
        )
        return
    
    code = context.args[0].strip()
    user_id = update.effective_user.id
    
    # Make sure the user exists
    user = users.get_user(user_id)
    if not user:
        users.add_user(
            user_id,
            update.effective_user.username or "Unknown",
            update.effective_user.first_name or "Unknown"
        )
    
    # Try to redeem the code
    success = users.redeem_code(user_id, code)
    
    if success:
        # Get updated user info
        user = users.get_user(user_id)
        subscription = user.get("subscription", {})
        plan_id = subscription.get("plan")
        plan_data = users.get_subscription_plans().get(plan_id, {})
        
        await update.message.reply_text(
            f"✅ Redeem code successfully applied!\n\n"
            f"You now have the {plan_data.get('name', plan_id)} plan.\n"
            f"Type /subscription to view your updated subscription details."
        )
    else:
        await update.message.reply_text(
            "❌ Invalid or already used redeem code.\n\n"
            "Please check the code and try again."
        )

async def purchase_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Record a purchase and notify admins."""
    if not context.args or len(context.args) < 3:
        await update.message.reply_text(
            "❌ Invalid format. Use:\n"
            "/purchase [plan_id] [payment_method] [payment_id/reference]\n\n"
            "Example: /purchase premium crypto TX123456789"
        )
        return
    
    plan_id = context.args[0].lower()
    payment_method = context.args[1].lower()
    payment_id = " ".join(context.args[2:])
    
    # Validate plan ID
    plans = users.get_subscription_plans()
    if plan_id not in plans:
        available_plans = ", ".join(plans.keys())
        await update.message.reply_text(
            f"❌ Invalid plan ID. Available plans: {available_plans}"
        )
        return
    
    # Validate payment method
    valid_methods = ["crypto", "upi", "giftcard", "amazon", "flipkart"]
    if payment_method not in valid_methods:
        methods = ", ".join(valid_methods)
        await update.message.reply_text(
            f"❌ Invalid payment method. Available methods: {methods}"
        )
        return
    
    plan_data = plans[plan_id]
    user_id = update.effective_user.id
    
    # Make sure the user exists
    user = users.get_user(user_id)
    if not user:
        users.add_user(
            user_id,
            update.effective_user.username or "Unknown",
            update.effective_user.first_name or "Unknown"
        )
    
    # Record the transaction
    transaction_id = users.add_transaction(
        user_id,
        plan_id,
        plan_data.get("price", 0),
        plan_data.get("currency", "USD"),
        payment_method,
        payment_id
    )
    
    # Notify the user
    await update.message.reply_text(
        f"✅ Purchase request submitted!\n\n"
        f"Plan: {plan_data.get('name')}\n"
        f"Price: {plan_data.get('price')} {plan_data.get('currency')}\n"
        f"Payment Method: {payment_method}\n"
        f"Payment ID: {payment_id}\n"
        f"Transaction ID: {transaction_id}\n\n"
        f"An admin will verify your payment and activate your subscription shortly. "
        f"You'll be notified when your subscription is active."
    )
    
    # TODO: Notify admins about the new transaction

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View attack history."""
    user_id = update.effective_user.id
    user = users.get_user(user_id)
    
    if not user:
        await update.message.reply_text("No attack history found.")
        return
    
    attack_history = user.get("attack_history", [])
    
    if not attack_history:
        await update.message.reply_text("No attack history found.")
        return
    
    from datetime import datetime
    
    # Get the last 10 attacks
    recent_attacks = attack_history[-10:]
    
    attack_list = []
    for attack in reversed(recent_attacks):
        date_str = datetime.fromtimestamp(attack.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M")
        
        attack_list.append(
            f"🚀 {date_str}\n"
            f"Target: {attack.get('target', 'N/A')}\n"
            f"Method: {attack.get('method', 'N/A')}\n"
            f"Duration: {attack.get('duration', 0)} seconds\n"
            f"Threads: {attack.get('threads', 0)}"
        )
    
    message = f"📋 Your Attack History (Last {len(recent_attacks)}):\n\n"
    message += "\n\n".join(attack_list)
    
    await update.message.reply_text(message)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks for user commands."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = update.effective_user.id
    
    if callback_data == "view_plans":
        # Show plans
        await query.message.delete()
        await plans_command(update, context)
        return
    
    if callback_data == "payment_info":
        # Show general payment instructions
        await query.edit_message_text(
            "💳 Payment Instructions\n\n"
            "To purchase a subscription, use one of the following methods:\n\n"
            "1. Send payment using your preferred method\n"
            "2. Use the /purchase command with your payment details\n\n"
            "Example: /purchase premium crypto TX123456789\n\n"
            "An admin will verify your payment and activate your subscription.\n\n"
            "For more details on payment options, use /payment"
        )
        return
    
    if callback_data == "attack_history":
        # Show attack history
        await query.message.delete()
        await history_command(update, context)
        return
    
    if callback_data.startswith("plan:"):
        # Show plan details
        plan_id = callback_data.split(":")[1]
        plans = users.get_subscription_plans()
        
        if plan_id not in plans:
            await query.edit_message_text("Plan not found.")
            return
        
        plan_data = plans[plan_id]
        
        # Create purchase button
        keyboard = [[InlineKeyboardButton("💳 Purchase This Plan", callback_data=f"purchase:{plan_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📦 Plan: {plan_data.get('name')}\n\n"
            f"Description: {plan_data.get('description')}\n"
            f"Price: {plan_data.get('price')} {plan_data.get('currency')}\n"
            f"Duration: {plan_data.get('duration_days')} days\n\n"
            f"Features:\n"
            f"• Max Attacks: {plan_data.get('max_attacks')} per subscription\n"
            f"• Max Duration: {plan_data.get('max_duration')} seconds per attack\n"
            f"• Max Threads: {plan_data.get('max_threads')} threads per attack",
            reply_markup=reply_markup
        )
        return
    
    if callback_data.startswith("purchase:"):
        # Show purchase instructions for a specific plan
        plan_id = callback_data.split(":")[1]
        plans = users.get_subscription_plans()
        
        if plan_id not in plans:
            await query.edit_message_text("Plan not found.")
            return
        
        plan_data = plans[plan_id]
        
        keyboard = [
            [InlineKeyboardButton("💰 Crypto", callback_data=f"payment:crypto:{plan_id}")],
            [InlineKeyboardButton("💳 UPI", callback_data=f"payment:upi:{plan_id}")],
            [InlineKeyboardButton("🎁 Gift Card", callback_data=f"payment:giftcard:{plan_id}")],
            [InlineKeyboardButton("🔑 Redeem Code", callback_data="payment:redeem")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"💳 Purchase {plan_data.get('name')}\n\n"
            f"Price: {plan_data.get('price')} {plan_data.get('currency')}\n\n"
            f"Select a payment method:",
            reply_markup=reply_markup
        )
        return
    
    if callback_data.startswith("payment:"):
        parts = callback_data.split(":")
        payment_method = parts[1]
        plan_id = parts[2] if len(parts) > 2 else None
        
        plan_info = ""
        if plan_id:
            plans = users.get_subscription_plans()
            if plan_id in plans:
                plan_data = plans[plan_id]
                plan_info = f"Plan: {plan_data.get('name')}\nPrice: {plan_data.get('price')} {plan_data.get('currency')}\n\n"
        
        if payment_method == "crypto":
            instructions = (
                f"{plan_info}"
                "💰 Cryptocurrency Payment\n\n"
                "We accept Bitcoin, Ethereum, and USDT.\n\n"
                "Bitcoin: bc1q...\n"
                "Ethereum: 0x...\n"
                "USDT (TRC20): T...\n\n"
                "After sending payment, use this command:\n"
                f"/purchase {plan_id if plan_id else 'plan_id'} crypto YOUR_TRANSACTION_ID\n\n"
                "Replace YOUR_TRANSACTION_ID with your cryptocurrency transaction ID."
            )
        elif payment_method == "upi":
            instructions = (
                f"{plan_info}"
                "💳 UPI Payment\n\n"
                "UPI ID: example@upi\n\n"
                "After sending payment, use this command:\n"
                f"/purchase {plan_id if plan_id else 'plan_id'} upi YOUR_UPI_REFERENCE\n\n"
                "Replace YOUR_UPI_REFERENCE with your UPI reference number or ID."
            )
        elif payment_method == "giftcard":
            instructions = (
                f"{plan_info}"
                "🎁 Gift Card Payment\n\n"
                "We accept Amazon and Flipkart gift cards.\n\n"
                "After purchasing a gift card, use this command:\n"
                f"/purchase {plan_id if plan_id else 'plan_id'} amazon GIFT_CARD_CODE\n"
                "OR\n"
                f"/purchase {plan_id if plan_id else 'plan_id'} flipkart GIFT_CARD_CODE\n\n"
                "Replace GIFT_CARD_CODE with your gift card code."
            )
        elif payment_method == "redeem":
            instructions = (
                "🔑 Redeem Code\n\n"
                "If you have a redeem code, use this command:\n"
                "/redeem YOUR_CODE\n\n"
                "Replace YOUR_CODE with your redeem code."
            )
        else:
            instructions = "Invalid payment method."
        
        await query.edit_message_text(instructions)
        return

# Dictionary of user command handlers
user_handlers = {
    "plans": CommandHandler("plans", plans_command),
    "subscription": CommandHandler("subscription", subscription_command),
    "payment": CommandHandler("payment", payment_command),
    "redeem": CommandHandler("redeem", redeem_command),
    "purchase": CommandHandler("purchase", purchase_command),
    "history": CommandHandler("history", history_command),
    "callback": CallbackQueryHandler(button_callback)
} 