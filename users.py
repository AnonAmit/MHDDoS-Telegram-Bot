import json
import os
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# File paths
USERS_FILE = "data/users.json"
TRANSACTIONS_FILE = "data/transactions.json"
PLANS_FILE = "data/subscription_plans.json"

# User roles
ROLE_ADMIN = "admin"
ROLE_PREMIUM = "premium"
ROLE_STANDARD = "standard"
ROLE_TRIAL = "trial"

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# Default subscription plans
DEFAULT_PLANS = {
    "trial": {
        "name": "Trial",
        "description": "Free trial access",
        "duration_days": 1,
        "max_attacks": 5,
        "max_duration": 300,  # 5 minutes
        "max_threads": 100,
        "price": 0,
        "currency": "USD"
    },
    "basic": {
        "name": "Basic",
        "description": "Basic DDoS capabilities",
        "duration_days": 7,
        "max_attacks": 20,
        "max_duration": 1800,  # 30 minutes
        "max_threads": 300,
        "price": 10,
        "currency": "USD"
    },
    "premium": {
        "name": "Premium",
        "description": "Advanced DDoS capabilities",
        "duration_days": 30,
        "max_attacks": 100,
        "max_duration": 3600,  # 1 hour
        "max_threads": 500,
        "price": 30,
        "currency": "USD"
    },
    "enterprise": {
        "name": "Enterprise",
        "description": "Maximum DDoS capabilities",
        "duration_days": 30,
        "max_attacks": -1,  # unlimited
        "max_duration": 7200,  # 2 hours
        "max_threads": 1000,
        "price": 80,
        "currency": "USD"
    }
}

# Initialize users, transactions and plans data
users_data = {}
transactions_data = []
plans_data = DEFAULT_PLANS

def initialize():
    """Initialize the users module, load existing data or create defaults."""
    global users_data, transactions_data, plans_data
    
    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    
    # Load or create users data
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            users_data = json.load(f)
    else:
        # Create default admin user
        users_data = {}
        save_users()
    
    # Load or create transactions data
    if os.path.exists(TRANSACTIONS_FILE):
        with open(TRANSACTIONS_FILE, 'r') as f:
            transactions_data = json.load(f)
    else:
        transactions_data = []
        save_transactions()
    
    # Load or create subscription plans
    if os.path.exists(PLANS_FILE):
        with open(PLANS_FILE, 'r') as f:
            plans_data = json.load(f)
    else:
        plans_data = DEFAULT_PLANS
        save_plans()
    
    logger.info("Users module initialized")

def save_users():
    """Save users data to file."""
    with open(USERS_FILE, 'w') as f:
        json.dump(users_data, f, indent=2)

def save_transactions():
    """Save transactions data to file."""
    with open(TRANSACTIONS_FILE, 'w') as f:
        json.dump(transactions_data, f, indent=2)

def save_plans():
    """Save subscription plans to file."""
    with open(PLANS_FILE, 'w') as f:
        json.dump(plans_data, f, indent=2)

def add_user(user_id: int, username: str, first_name: str, role: str = ROLE_TRIAL) -> bool:
    """Add a new user to the system."""
    if str(user_id) in users_data:
        return False  # User already exists
    
    current_time = int(time.time())
    
    # Create new user with a trial subscription
    users_data[str(user_id)] = {
        "username": username,
        "first_name": first_name,
        "role": role,
        "created_at": current_time,
        "subscription": {
            "plan": "trial" if role == ROLE_TRIAL else None,
            "start_date": current_time if role == ROLE_TRIAL else None,
            "end_date": current_time + (86400 * plans_data["trial"]["duration_days"]) if role == ROLE_TRIAL else None,
            "attacks_used": 0,
            "attacks_limit": plans_data["trial"]["max_attacks"] if role == ROLE_TRIAL else 0,
            "active": True if role == ROLE_TRIAL else False
        },
        "payment_history": [],
        "attack_history": []
    }
    
    save_users()
    return True

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user data by ID."""
    return users_data.get(str(user_id))

def get_all_users() -> Dict[str, Dict[str, Any]]:
    """Get all users."""
    return users_data

def is_user_admin(user_id: int) -> bool:
    """Check if a user is an admin."""
    user = get_user(user_id)
    return user is not None and user.get("role") == ROLE_ADMIN

def is_user_authorized(user_id: int) -> bool:
    """Check if a user has an active subscription."""
    user = get_user(user_id)
    if not user:
        return False
    
    # Admins always have access
    if user.get("role") == ROLE_ADMIN:
        return True
    
    # Check if subscription is active
    subscription = user.get("subscription", {})
    current_time = int(time.time())
    
    if not subscription.get("active", False):
        return False
    
    end_date = subscription.get("end_date")
    if not end_date or current_time > end_date:
        # Subscription expired, deactivate it
        subscription["active"] = False
        save_users()
        return False
    
    # Check if attack limit reached
    attacks_used = subscription.get("attacks_used", 0)
    attacks_limit = subscription.get("attacks_limit", 0)
    
    if attacks_limit > 0 and attacks_used >= attacks_limit:
        return False
    
    return True

def get_user_plan_limits(user_id: int) -> Dict[str, Any]:
    """Get the user's plan limits."""
    user = get_user(user_id)
    default_limits = {
        "max_duration": 0,
        "max_threads": 0,
        "attacks_remaining": 0
    }
    
    if not user:
        return default_limits
    
    # Admins have no limits
    if user.get("role") == ROLE_ADMIN:
        return {
            "max_duration": -1,  # unlimited
            "max_threads": -1,   # unlimited
            "attacks_remaining": -1  # unlimited
        }
    
    subscription = user.get("subscription", {})
    if not subscription.get("active", False):
        return default_limits
    
    plan_name = subscription.get("plan")
    if not plan_name or plan_name not in plans_data:
        return default_limits
    
    plan = plans_data[plan_name]
    attacks_used = subscription.get("attacks_used", 0)
    attacks_limit = subscription.get("attacks_limit", 0)
    
    return {
        "max_duration": plan.get("max_duration", 0),
        "max_threads": plan.get("max_threads", 0),
        "attacks_remaining": attacks_limit - attacks_used if attacks_limit > 0 else -1
    }

def record_attack(user_id: int, attack_id: str, target: str, method: str, threads: int, duration: int) -> bool:
    """Record an attack in the user's history and update their attack usage."""
    user = get_user(user_id)
    if not user:
        return False
    
    current_time = int(time.time())
    
    # Add to attack history
    attack_info = {
        "attack_id": attack_id,
        "target": target,
        "method": method,
        "threads": threads,
        "duration": duration,
        "timestamp": current_time
    }
    
    user["attack_history"].append(attack_info)
    
    # Update attacks used count for subscription
    if user.get("role") != ROLE_ADMIN:
        subscription = user.get("subscription", {})
        if subscription.get("active", False):
            subscription["attacks_used"] = subscription.get("attacks_used", 0) + 1
    
    save_users()
    return True

def add_transaction(user_id: int, plan_id: str, amount: float, currency: str, 
                    payment_method: str, payment_id: str, status: str = "pending") -> str:
    """Add a new payment transaction."""
    current_time = int(time.time())
    transaction_id = f"TRX-{current_time}-{len(transactions_data) + 1}"
    
    transaction = {
        "id": transaction_id,
        "user_id": user_id,
        "plan_id": plan_id,
        "amount": amount,
        "currency": currency,
        "payment_method": payment_method,
        "payment_id": payment_id,
        "status": status,
        "created_at": current_time,
        "updated_at": current_time,
        "notes": []
    }
    
    transactions_data.append(transaction)
    
    # Add to user's payment history
    user = get_user(user_id)
    if user:
        user["payment_history"].append(transaction_id)
        save_users()
    
    save_transactions()
    return transaction_id

def get_transaction(transaction_id: str) -> Optional[Dict[str, Any]]:
    """Get transaction details."""
    for transaction in transactions_data:
        if transaction.get("id") == transaction_id:
            return transaction
    return None

def get_user_transactions(user_id: int) -> List[Dict[str, Any]]:
    """Get all transactions for a user."""
    return [t for t in transactions_data if t.get("user_id") == user_id]

def approve_transaction(transaction_id: str, admin_id: int, notes: str = "") -> bool:
    """Approve a transaction and activate the user's subscription."""
    if not is_user_admin(admin_id):
        return False
    
    transaction = get_transaction(transaction_id)
    if not transaction or transaction.get("status") != "pending":
        return False
    
    user_id = transaction.get("user_id")
    plan_id = transaction.get("plan_id")
    
    user = get_user(user_id)
    if not user or plan_id not in plans_data:
        return False
    
    # Update transaction status
    transaction["status"] = "approved"
    transaction["updated_at"] = int(time.time())
    if notes:
        transaction["notes"].append({
            "admin_id": admin_id,
            "text": notes,
            "timestamp": int(time.time())
        })
    
    # Update user's subscription
    plan = plans_data[plan_id]
    current_time = int(time.time())
    
    # If user already has an active subscription, extend it
    current_subscription = user.get("subscription", {})
    if current_subscription.get("active", False) and current_subscription.get("end_date", 0) > current_time:
        end_date = current_subscription.get("end_date", current_time)
    else:
        end_date = current_time
    
    # Activate new subscription
    user["subscription"] = {
        "plan": plan_id,
        "start_date": current_time,
        "end_date": end_date + (86400 * plan["duration_days"]),
        "attacks_used": 0,
        "attacks_limit": plan["max_attacks"],
        "active": True
    }
    
    # Update role based on plan
    if plan_id == "premium" or plan_id == "enterprise":
        user["role"] = ROLE_PREMIUM
    else:
        user["role"] = ROLE_STANDARD
    
    save_users()
    save_transactions()
    return True

def reject_transaction(transaction_id: str, admin_id: int, reason: str = "") -> bool:
    """Reject a transaction."""
    if not is_user_admin(admin_id):
        return False
    
    transaction = get_transaction(transaction_id)
    if not transaction or transaction.get("status") != "pending":
        return False
    
    # Update transaction status
    transaction["status"] = "rejected"
    transaction["updated_at"] = int(time.time())
    if reason:
        transaction["notes"].append({
            "admin_id": admin_id,
            "text": reason,
            "timestamp": int(time.time())
        })
    
    save_transactions()
    return True

def add_admin_note(transaction_id: str, admin_id: int, note: str) -> bool:
    """Add an admin note to a transaction."""
    if not is_user_admin(admin_id) or not note:
        return False
    
    transaction = get_transaction(transaction_id)
    if not transaction:
        return False
    
    transaction["notes"].append({
        "admin_id": admin_id,
        "text": note,
        "timestamp": int(time.time())
    })
    
    save_transactions()
    return True

def get_pending_transactions() -> List[Dict[str, Any]]:
    """Get all pending transactions."""
    return [t for t in transactions_data if t.get("status") == "pending"]

def get_subscription_plans() -> Dict[str, Any]:
    """Get all subscription plans."""
    return plans_data

def add_or_update_plan(plan_id: str, plan_data: Dict[str, Any], admin_id: int) -> bool:
    """Add or update a subscription plan."""
    if not is_user_admin(admin_id):
        return False
    
    # Validate required fields
    required_fields = ["name", "description", "duration_days", "max_attacks", 
                      "max_duration", "max_threads", "price", "currency"]
    
    for field in required_fields:
        if field not in plan_data:
            return False
    
    # Add or update the plan
    plans_data[plan_id] = plan_data
    save_plans()
    return True

def delete_plan(plan_id: str, admin_id: int) -> bool:
    """Delete a subscription plan."""
    if not is_user_admin(admin_id) or plan_id not in plans_data:
        return False
    
    # Don't delete plans that are in use
    for user_id, user in users_data.items():
        subscription = user.get("subscription", {})
        if subscription.get("plan") == plan_id and subscription.get("active", False):
            return False
    
    del plans_data[plan_id]
    save_plans()
    return True

def generate_redeem_code(admin_id: int, plan_id: str, count: int = 1) -> List[str]:
    """Generate redeem codes for a subscription plan."""
    if not is_user_admin(admin_id) or plan_id not in plans_data:
        return []
    
    # Load existing redeem codes or create new
    redeem_file = "data/redeem_codes.json"
    redeem_codes = {}
    
    if os.path.exists(redeem_file):
        with open(redeem_file, 'r') as f:
            redeem_codes = json.load(f)
    
    # Generate new codes
    import random
    import string
    
    new_codes = []
    for _ in range(count):
        # Generate a random 16-character code
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        code = f"{plan_id[:3].upper()}-{code[:4]}-{code[4:8]}-{code[8:12]}-{code[12:]}"
        
        redeem_codes[code] = {
            "plan_id": plan_id,
            "created_by": admin_id,
            "created_at": int(time.time()),
            "used_by": None,
            "used_at": None
        }
        
        new_codes.append(code)
    
    # Save updated codes
    with open(redeem_file, 'w') as f:
        json.dump(redeem_codes, f, indent=2)
    
    return new_codes

def redeem_code(user_id: int, code: str) -> bool:
    """Redeem a subscription code."""
    redeem_file = "data/redeem_codes.json"
    if not os.path.exists(redeem_file):
        return False
    
    with open(redeem_file, 'r') as f:
        redeem_codes = json.load(f)
    
    if code not in redeem_codes or redeem_codes[code].get("used_by") is not None:
        return False
    
    # Mark code as used
    redeem_codes[code]["used_by"] = user_id
    redeem_codes[code]["used_at"] = int(time.time())
    
    # Get the plan
    plan_id = redeem_codes[code]["plan_id"]
    if plan_id not in plans_data:
        return False
    
    # Activate the subscription
    user = get_user(user_id)
    if not user:
        return False
    
    plan = plans_data[plan_id]
    current_time = int(time.time())
    
    # If user already has an active subscription, extend it
    current_subscription = user.get("subscription", {})
    if current_subscription.get("active", False) and current_subscription.get("end_date", 0) > current_time:
        end_date = current_subscription.get("end_date", current_time)
    else:
        end_date = current_time
    
    # Activate new subscription
    user["subscription"] = {
        "plan": plan_id,
        "start_date": current_time,
        "end_date": end_date + (86400 * plan["duration_days"]),
        "attacks_used": 0,
        "attacks_limit": plan["max_attacks"],
        "active": True
    }
    
    # Update role based on plan
    if plan_id == "premium" or plan_id == "enterprise":
        user["role"] = ROLE_PREMIUM
    else:
        user["role"] = ROLE_STANDARD
    
    # Save changes
    with open(redeem_file, 'w') as f:
        json.dump(redeem_codes, f, indent=2)
    
    save_users()
    return True

# Initialize the module
if __name__ != "__main__":
    initialize() 