"""
Scheduler module for MHDDoS Telegram Bot

This module provides functionality for scheduling attacks to run at specific times.
"""

import os
import json
import time
import datetime
import logging
import threading
import subprocess
from typing import Dict, List, Optional, Any, Tuple, Callable

# Configure logging
logger = logging.getLogger("mhddos_bot.scheduler")

# Default schedule file path
SCHEDULE_FILE = "attack_schedule.json"

# Schedule format
# {
#     "schedule_id": {
#         "target": "https://example.com",
#         "method": "GET",
#         "threads": 100,
#         "duration": 60,
#         "proxy_type": null,
#         "description": "Scheduled attack",
#         "time": "2023-05-15T14:30:00",  # ISO format datetime
#         "repeat": null,  # null, "daily", "weekly"
#         "completed": false,
#         "template": null  # template name, if using a template
#     }
# }

# Store scheduled tasks
scheduled_tasks: Dict[str, Tuple[threading.Timer, Dict[str, Any]]] = {}

# Attack callback function type
AttackCallback = Callable[[str, str, int, int, Optional[str]], None]

def load_schedule(file_path: str = SCHEDULE_FILE) -> Dict[str, Dict[str, Any]]:
    """Load scheduled attacks from file"""
    try:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading schedule: {str(e)}")
        return {}

def save_schedule(schedule: Dict[str, Dict[str, Any]], file_path: str = SCHEDULE_FILE) -> bool:
    """Save scheduled attacks to file"""
    try:
        with open(file_path, "w") as f:
            json.dump(schedule, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving schedule: {str(e)}")
        return False

def schedule_attack(target: str, method: str, threads: int, duration: int,
                   scheduled_time: str, description: str = "", 
                   proxy_type: Optional[str] = None, repeat: Optional[str] = None,
                   template: Optional[str] = None) -> Optional[str]:
    """Schedule a new attack
    
    Args:
        target: Target URL or IP
        method: Attack method
        threads: Number of threads
        duration: Attack duration in seconds
        scheduled_time: ISO format datetime string
        description: Attack description
        proxy_type: Type of proxy to use (http, socks4, socks5)
        repeat: Repeat schedule (daily, weekly)
        template: Template name if using a template
        
    Returns:
        Schedule ID if successful, None otherwise
    """
    schedule = load_schedule()
    
    # Generate a unique ID for this schedule
    schedule_id = f"schedule-{int(time.time())}"
    
    # Create schedule entry
    schedule_entry = {
        "target": target,
        "method": method.upper(),
        "threads": threads,
        "duration": duration,
        "description": description,
        "time": scheduled_time,
        "repeat": repeat,
        "completed": False,
        "template": template
    }
    
    if proxy_type:
        schedule_entry["proxy_type"] = proxy_type.lower()
    
    schedule[schedule_id] = schedule_entry
    
    if save_schedule(schedule):
        logger.info(f"Attack scheduled with ID: {schedule_id}")
        return schedule_id
    
    return None

def cancel_schedule(schedule_id: str) -> bool:
    """Cancel a scheduled attack"""
    schedule = load_schedule()
    
    if schedule_id in schedule:
        del schedule[schedule_id]
        
        # Also cancel the timer if it's running
        if schedule_id in scheduled_tasks:
            timer, _ = scheduled_tasks[schedule_id]
            timer.cancel()
            del scheduled_tasks[schedule_id]
        
        return save_schedule(schedule)
    
    return False

def list_schedules() -> List[Dict[str, Any]]:
    """List all scheduled attacks"""
    schedule = load_schedule()
    return [{"id": id, **entry} for id, entry in schedule.items()]

def format_schedule_for_display(schedule: Dict[str, Any]) -> str:
    """Format a schedule for display in Telegram"""
    # Convert time string to datetime
    try:
        schedule_time = datetime.datetime.fromisoformat(schedule["time"])
        time_str = schedule_time.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, KeyError):
        time_str = schedule.get("time", "Unknown")
    
    lines = [
        f"Target: {schedule.get('target', 'Unknown')}",
        f"Method: {schedule.get('method', 'Unknown')}",
        f"Scheduled Time: {time_str}",
        f"Threads: {schedule.get('threads', 0)}",
        f"Duration: {schedule.get('duration', 0)} seconds"
    ]
    
    if "proxy_type" in schedule:
        lines.append(f"Proxy: {schedule['proxy_type']}")
    
    if "description" in schedule and schedule["description"]:
        lines.append(f"Description: {schedule['description']}")
    
    if "template" in schedule and schedule["template"]:
        lines.append(f"Using Template: {schedule['template']}")
    
    if "repeat" in schedule and schedule["repeat"]:
        lines.append(f"Repeat: {schedule['repeat'].capitalize()}")
    
    if "completed" in schedule:
        status = "Completed" if schedule["completed"] else "Pending"
        lines.append(f"Status: {status}")
    
    return "\n".join(lines)

def setup_scheduler(attack_callback: AttackCallback, template_callback: Optional[Callable[[str], Dict[str, Any]]] = None) -> None:
    """Initialize the scheduler and load scheduled attacks
    
    Args:
        attack_callback: Function to call when an attack should be executed
        template_callback: Function to call to get template details
    """
    schedule = load_schedule()
    now = datetime.datetime.now()
    
    for schedule_id, entry in schedule.items():
        if entry.get("completed", False):
            continue
        
        try:
            # Parse the scheduled time
            scheduled_time = datetime.datetime.fromisoformat(entry["time"])
            
            # If the time has passed, mark as completed if not repeating
            if scheduled_time < now:
                # If it's a repeating schedule, reschedule
                if entry.get("repeat") in ["daily", "weekly"]:
                    if entry["repeat"] == "daily":
                        # Reschedule for tomorrow at the same time
                        new_time = scheduled_time.replace(
                            year=now.year, month=now.month, day=now.day
                        ) + datetime.timedelta(days=1)
                    else:  # weekly
                        # Reschedule for next week at the same time
                        new_time = scheduled_time.replace(
                            year=now.year, month=now.month, day=now.day
                        ) + datetime.timedelta(days=7)
                    
                    # Update the schedule
                    entry["time"] = new_time.isoformat()
                    scheduled_time = new_time
                else:
                    # Mark as completed
                    entry["completed"] = True
                    continue
            
            # Calculate delay in seconds
            delay = (scheduled_time - now).total_seconds()
            
            if delay > 0:
                # Set up a timer to run the attack
                _schedule_timer(schedule_id, entry, delay, attack_callback, template_callback)
        
        except (ValueError, KeyError) as e:
            logger.error(f"Error scheduling {schedule_id}: {str(e)}")
    
    # Save any changes we made
    save_schedule(schedule)

def _schedule_timer(schedule_id: str, schedule: Dict[str, Any], delay: float, 
                  attack_callback: AttackCallback, 
                  template_callback: Optional[Callable[[str], Dict[str, Any]]] = None) -> None:
    """Create a timer to execute a scheduled attack"""
    timer = threading.Timer(
        delay, 
        _execute_scheduled_attack, 
        args=[schedule_id, schedule, attack_callback, template_callback]
    )
    timer.daemon = True
    timer.start()
    
    # Store the timer so we can cancel it if needed
    scheduled_tasks[schedule_id] = (timer, schedule)
    
    logger.info(f"Scheduled attack {schedule_id} in {delay:.2f} seconds")

def _execute_scheduled_attack(schedule_id: str, schedule: Dict[str, Any], 
                            attack_callback: AttackCallback,
                            template_callback: Optional[Callable[[str], Dict[str, Any]]] = None) -> None:
    """Execute a scheduled attack
    
    This function is called by the timer when it's time to run the attack.
    """
    logger.info(f"Executing scheduled attack {schedule_id}")
    
    try:
        # If this is a template-based attack, get the template details
        if schedule.get("template") and template_callback:
            template = template_callback(schedule["template"])
            if not template:
                logger.error(f"Template '{schedule['template']}' not found for scheduled attack {schedule_id}")
                return
            
            target = template.get("target", "")
            method = template.get("method", "")
            threads = template.get("threads", 0)
            duration = template.get("duration", 0)
            proxy_type = template.get("proxy_type")
        else:
            # Get attack parameters from the schedule
            target = schedule.get("target", "")
            method = schedule.get("method", "")
            threads = schedule.get("threads", 0)
            duration = schedule.get("duration", 0)
            proxy_type = schedule.get("proxy_type")
        
        # Execute the attack
        attack_callback(target, method, threads, duration, proxy_type)
        
        # Update schedule
        _update_schedule_after_execution(schedule_id, schedule, attack_callback, template_callback)
        
    except Exception as e:
        logger.error(f"Error executing scheduled attack {schedule_id}: {str(e)}")

def _update_schedule_after_execution(schedule_id: str, schedule: Dict[str, Any],
                                    attack_callback: AttackCallback,
                                    template_callback: Optional[Callable[[str], Dict[str, Any]]] = None) -> None:
    """Update the schedule after an attack has been executed"""
    # Load the latest schedule to avoid conflicts
    all_schedules = load_schedule()
    
    if schedule_id not in all_schedules:
        logger.warning(f"Schedule {schedule_id} not found in schedule file")
        return
    
    # If it's a repeating schedule, update the next run time
    if schedule.get("repeat") in ["daily", "weekly"]:
        try:
            # Parse the current scheduled time
            current_time = datetime.datetime.fromisoformat(schedule["time"])
            
            if schedule["repeat"] == "daily":
                # Set for tomorrow at the same time
                next_time = current_time + datetime.timedelta(days=1)
            else:  # weekly
                # Set for next week at the same time
                next_time = current_time + datetime.timedelta(days=7)
            
            # Update the schedule
            all_schedules[schedule_id]["time"] = next_time.isoformat()
            
            # Set up the next timer
            _schedule_timer(
                schedule_id, 
                all_schedules[schedule_id], 
                (next_time - datetime.datetime.now()).total_seconds(),
                attack_callback,
                template_callback
            )
            
        except (ValueError, KeyError) as e:
            logger.error(f"Error updating repeating schedule {schedule_id}: {str(e)}")
            all_schedules[schedule_id]["completed"] = True
    else:
        # Mark as completed
        all_schedules[schedule_id]["completed"] = True
    
    # Save the updated schedule
    save_schedule(all_schedules)

def _get_callback_from_schedules() -> AttackCallback:
    """Dummy callback function for _update_schedule_after_execution"""
    def dummy_callback(target: str, method: str, threads: int, duration: int, proxy_type: Optional[str] = None) -> None:
        pass
    
    return dummy_callback 