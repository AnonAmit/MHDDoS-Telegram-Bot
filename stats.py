"""
Statistics module for MHDDoS Telegram Bot

This module provides functionality for tracking and analyzing attack statistics.
"""

import os
import json
import time
import datetime
import logging
from typing import Dict, List, Optional, Any, Tuple, Set

# Configure logging
logger = logging.getLogger("mhddos_bot.stats")

# Default stats file paths
STATS_FILE = "attack_stats.json"
CURRENT_STATS_FILE = "current_stats.json"

# Stats format
# {
#     "total_attacks": 123,
#     "total_duration": 7200,  # seconds
#     "methods": {
#         "GET": 50,
#         "POST": 20,
#         ...
#     },
#     "targets": {
#         "https://example.com": {
#             "attacks": 10,
#             "duration": 600,
#             "last_attack": "2023-05-15T14:30:00",
#             "methods": {
#                 "GET": 5,
#                 "POST": 5
#             }
#         },
#         ...
#     },
#     "daily": {
#         "2023-05-15": {
#             "attacks": 5,
#             "duration": 300
#         },
#         ...
#     }
# }

# Current stats format (for running attacks)
# {
#     "attack_id": {
#         "target": "https://example.com",
#         "method": "GET",
#         "threads": 100,
#         "start_time": "2023-05-15T14:30:00",
#         "planned_duration": 60,
#         "proxy_type": "http",
#     },
#     ...
# }

def load_stats(file_path: str = STATS_FILE) -> Dict[str, Any]:
    """Load statistics from file"""
    try:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        return {
            "total_attacks": 0,
            "total_duration": 0,
            "methods": {},
            "targets": {},
            "daily": {}
        }
    except Exception as e:
        logger.error(f"Error loading stats: {str(e)}")
        return {
            "total_attacks": 0,
            "total_duration": 0,
            "methods": {},
            "targets": {},
            "daily": {}
        }

def save_stats(stats: Dict[str, Any], file_path: str = STATS_FILE) -> bool:
    """Save statistics to file"""
    try:
        with open(file_path, "w") as f:
            json.dump(stats, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving stats: {str(e)}")
        return False

def load_current_stats(file_path: str = CURRENT_STATS_FILE) -> Dict[str, Dict[str, Any]]:
    """Load current attack statistics from file"""
    try:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading current stats: {str(e)}")
        return {}

def save_current_stats(stats: Dict[str, Dict[str, Any]], file_path: str = CURRENT_STATS_FILE) -> bool:
    """Save current attack statistics to file"""
    try:
        with open(file_path, "w") as f:
            json.dump(stats, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving current stats: {str(e)}")
        return False

def record_attack_start(attack_id: str, target: str, method: str, threads: int, 
                      duration: int, proxy_type: Optional[str] = None) -> None:
    """Record the start of an attack"""
    current_stats = load_current_stats()
    
    # Add the attack to current stats
    current_stats[attack_id] = {
        "target": target,
        "method": method,
        "threads": threads,
        "start_time": datetime.datetime.now().isoformat(),
        "planned_duration": duration,
        "proxy_type": proxy_type
    }
    
    save_current_stats(current_stats)

def record_attack_end(attack_id: str, actual_duration: Optional[int] = None) -> None:
    """Record the end of an attack and update statistics"""
    current_stats = load_current_stats()
    
    if attack_id not in current_stats:
        logger.warning(f"Attack {attack_id} not found in current stats")
        return
    
    attack_data = current_stats[attack_id]
    
    # Calculate actual duration
    if actual_duration is None:
        try:
            start_time = datetime.datetime.fromisoformat(attack_data["start_time"])
            end_time = datetime.datetime.now()
            actual_duration = int((end_time - start_time).total_seconds())
        except (ValueError, KeyError) as e:
            logger.error(f"Error calculating duration for {attack_id}: {str(e)}")
            actual_duration = attack_data.get("planned_duration", 0)
    
    # Update overall statistics
    stats = load_stats()
    
    # Increment total attacks
    stats["total_attacks"] += 1
    
    # Add to total duration
    stats["total_duration"] += actual_duration
    
    # Update method count
    method = attack_data["method"]
    stats["methods"][method] = stats["methods"].get(method, 0) + 1
    
    # Update target stats
    target = attack_data["target"]
    if target not in stats["targets"]:
        stats["targets"][target] = {
            "attacks": 0,
            "duration": 0,
            "methods": {}
        }
    
    stats["targets"][target]["attacks"] += 1
    stats["targets"][target]["duration"] += actual_duration
    stats["targets"][target]["last_attack"] = datetime.datetime.now().isoformat()
    
    # Update method count for target
    if "methods" not in stats["targets"][target]:
        stats["targets"][target]["methods"] = {}
    
    stats["targets"][target]["methods"][method] = stats["targets"][target]["methods"].get(method, 0) + 1
    
    # Update daily stats
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if "daily" not in stats:
        stats["daily"] = {}
    
    if today not in stats["daily"]:
        stats["daily"][today] = {
            "attacks": 0,
            "duration": 0
        }
    
    stats["daily"][today]["attacks"] += 1
    stats["daily"][today]["duration"] += actual_duration
    
    # Save updated stats
    save_stats(stats)
    
    # Remove from current stats
    del current_stats[attack_id]
    save_current_stats(current_stats)

def get_attack_stats() -> Dict[str, Any]:
    """Get a summary of attack statistics"""
    stats = load_stats()
    
    # Clean up the stats to avoid overwhelming output
    cleaned_stats = {
        "total_attacks": stats.get("total_attacks", 0),
        "total_duration_hours": round(stats.get("total_duration", 0) / 3600, 2),
        "methods": dict(sorted(stats.get("methods", {}).items(), key=lambda x: x[1], reverse=True)[:5]),
        "recent_targets": {}
    }
    
    # Get top 5 targets by attack count
    top_targets = sorted(
        stats.get("targets", {}).items(), 
        key=lambda x: x[1].get("attacks", 0), 
        reverse=True
    )[:5]
    
    for target, target_stats in top_targets:
        cleaned_stats["recent_targets"][target] = {
            "attacks": target_stats.get("attacks", 0),
            "duration_hours": round(target_stats.get("duration", 0) / 3600, 2),
            "last_attack": target_stats.get("last_attack", "Unknown")
        }
    
    # Add current active attacks
    current_stats = load_current_stats()
    cleaned_stats["active_attacks"] = len(current_stats)
    
    return cleaned_stats

def get_active_attacks() -> Dict[str, Dict[str, Any]]:
    """Get all currently active attacks"""
    return load_current_stats()

def get_target_history(target: str) -> Dict[str, Any]:
    """Get the attack history for a specific target"""
    stats = load_stats()
    
    if target not in stats.get("targets", {}):
        return {}
    
    return stats["targets"][target]

def get_daily_stats(days: int = 7) -> Dict[str, Dict[str, Any]]:
    """Get daily statistics for the last X days"""
    stats = load_stats()
    
    if "daily" not in stats:
        return {}
    
    # Get the last X days
    today = datetime.datetime.now().date()
    days_to_show = {}
    
    for i in range(days):
        day = today - datetime.timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        
        if day_str in stats["daily"]:
            days_to_show[day_str] = stats["daily"][day_str]
        else:
            days_to_show[day_str] = {
                "attacks": 0,
                "duration": 0
            }
    
    return days_to_show

def format_stats_for_display(stats: Dict[str, Any]) -> str:
    """Format statistics for display in Telegram"""
    lines = [
        "📊 Attack Statistics 📊",
        "",
        f"Total Attacks: {stats.get('total_attacks', 0)}",
        f"Total Duration: {stats.get('total_duration_hours', 0)} hours",
        f"Active Attacks: {stats.get('active_attacks', 0)}",
        "",
        "Top Methods:",
    ]
    
    for method, count in stats.get("methods", {}).items():
        lines.append(f"• {method}: {count}")
    
    lines.append("")
    lines.append("Recent Targets:")
    
    for target, target_stats in stats.get("recent_targets", {}).items():
        lines.append(f"• {target}")
        lines.append(f"  Attacks: {target_stats.get('attacks', 0)}")
        lines.append(f"  Duration: {target_stats.get('duration_hours', 0)} hours")
    
    return "\n".join(lines)

def format_daily_stats_for_display(daily_stats: Dict[str, Dict[str, Any]]) -> str:
    """Format daily statistics for display in Telegram"""
    lines = [
        "📅 Daily Attack Statistics 📅",
        ""
    ]
    
    for day, stats in sorted(daily_stats.items(), reverse=True):
        # Format day more nicely
        try:
            day_date = datetime.datetime.strptime(day, "%Y-%m-%d").strftime("%b %d, %Y")
        except ValueError:
            day_date = day
        
        attacks = stats.get("attacks", 0)
        duration_hours = round(stats.get("duration", 0) / 3600, 2)
        
        lines.append(f"• {day_date}: {attacks} attacks, {duration_hours} hours")
    
    return "\n".join(lines)

def clean_up_stats() -> None:
    """Clean up old statistics"""
    stats = load_stats()
    
    # Limit daily stats to last 30 days
    if "daily" in stats:
        today = datetime.datetime.now().date()
        cutoff = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        
        stats["daily"] = {
            day: day_stats for day, day_stats in stats["daily"].items()
            if day >= cutoff
        }
    
    # Limit targets to last 100
    if "targets" in stats and len(stats["targets"]) > 100:
        # Sort targets by last attack time
        sorted_targets = sorted(
            stats["targets"].items(),
            key=lambda x: x[1].get("last_attack", ""),
            reverse=True
        )
        
        # Keep only the 100 most recent
        stats["targets"] = dict(sorted_targets[:100])
    
    save_stats(stats)

def initialize() -> None:
    """Initialize the statistics module"""
    # Load stats to create initial file if needed
    load_stats()
    
    # Clean up any stale statistics
    clean_up_stats()
    
    # Clean up any orphaned current stats
    current_stats = load_current_stats()
    for attack_id, attack_data in list(current_stats.items()):
        try:
            start_time = datetime.datetime.fromisoformat(attack_data["start_time"])
            planned_duration = attack_data.get("planned_duration", 0)
            
            # If the attack should have ended over 1 hour ago, remove it
            end_time = start_time + datetime.timedelta(seconds=planned_duration)
            if datetime.datetime.now() > end_time + datetime.timedelta(hours=1):
                # Move to completed stats
                record_attack_end(attack_id, planned_duration)
        except (ValueError, KeyError) as e:
            logger.error(f"Error cleaning up orphaned stats for {attack_id}: {str(e)}")
            del current_stats[attack_id]
    
    save_current_stats(current_stats) 