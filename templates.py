"""
Attack templates for MHDDoS Telegram Bot

This module provides functionality for creating, storing, and executing
attack templates. Templates are predefined attack configurations that
can be easily launched with a simple command.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any

# Configure logging
logger = logging.getLogger("mhddos_bot.templates")

# Default templates file path
TEMPLATES_FILE = "attack_templates.json"

# Example template format
# {
#     "template_name": {
#         "target": "https://example.com",
#         "method": "GET",
#         "threads": 100,
#         "duration": 60,
#         "proxy_type": "http",
#         "description": "Example attack template"
#     }
# }

def load_templates(file_path: str = TEMPLATES_FILE) -> Dict[str, Dict[str, Any]]:
    """Load attack templates from file"""
    try:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading templates: {str(e)}")
        return {}

def save_templates(templates: Dict[str, Dict[str, Any]], file_path: str = TEMPLATES_FILE) -> bool:
    """Save attack templates to file"""
    try:
        with open(file_path, "w") as f:
            json.dump(templates, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving templates: {str(e)}")
        return False

def create_template(name: str, target: str, method: str, threads: int, 
                    duration: int, description: str = "", 
                    proxy_type: Optional[str] = None) -> Dict[str, Any]:
    """Create a new attack template"""
    template = {
        "target": target,
        "method": method.upper(),
        "threads": threads,
        "duration": duration,
        "description": description
    }
    
    if proxy_type:
        template["proxy_type"] = proxy_type.lower()
    
    return template

def add_template(name: str, template: Dict[str, Any]) -> bool:
    """Add a template to the templates file"""
    templates = load_templates()
    
    # Validate template format
    if not all(k in template for k in ["target", "method", "threads", "duration"]):
        logger.error(f"Invalid template format: {template}")
        return False
    
    templates[name] = template
    return save_templates(templates)

def get_template(name: str) -> Optional[Dict[str, Any]]:
    """Get a template by name"""
    templates = load_templates()
    return templates.get(name)

def delete_template(name: str) -> bool:
    """Delete a template by name"""
    templates = load_templates()
    
    if name in templates:
        del templates[name]
        return save_templates(templates)
    
    return False

def list_templates() -> List[Dict[str, Any]]:
    """List all available templates"""
    templates = load_templates()
    return [{"name": name, **template} for name, template in templates.items()]

def format_template_for_display(template: Dict[str, Any]) -> str:
    """Format a template for display in Telegram"""
    lines = [
        f"Target: {template['target']}",
        f"Method: {template['method']}",
        f"Threads: {template['threads']}",
        f"Duration: {template['duration']} seconds"
    ]
    
    if "proxy_type" in template:
        lines.append(f"Proxy: {template['proxy_type']}")
    
    if "description" in template and template["description"]:
        lines.append(f"Description: {template['description']}")
    
    return "\n".join(lines)

# Create some default templates
def initialize_default_templates():
    """Initialize default templates if none exist"""
    if not os.path.exists(TEMPLATES_FILE) or os.path.getsize(TEMPLATES_FILE) == 0:
        default_templates = {
            "http_flood": create_template(
                "http_flood",
                "https://example.com",
                "GET",
                100,
                60,
                "Basic HTTP flood attack with GET requests",
                "http"
            ),
            "tcp_flood": create_template(
                "tcp_flood",
                "192.168.1.1:80",
                "TCP",
                200,
                60,
                "Basic TCP flood attack"
            ),
            "slow_loris": create_template(
                "slow_loris",
                "https://example.com",
                "SLOW",
                50,
                120,
                "SlowLoris attack keeping connections open",
                "http"
            )
        }
        
        save_templates(default_templates)
        logger.info("Created default attack templates")
        
        return default_templates
    
    return load_templates() 