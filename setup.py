#!/usr/bin/env python3
"""
Setup script for MHDDoS Telegram Bot
This script helps configure the bot and install required dependencies.
"""

import os
import sys
import subprocess
import shutil
import re

def check_python_version():
    """Check if Python version is 3.7+"""
    if sys.version_info < (3, 7):
        print("Error: Python 3.7 or higher is required")
        sys.exit(1)
    print("✅ Python version check passed")

def install_dependencies():
    """Install required Python packages"""
    print("Installing required dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        sys.exit(1)

def configure_bot():
    """Configure the bot settings"""
    print("\nBot Configuration\n" + "-" * 20)
    
    # Check if MHDDoS is installed
    mhddos_path = input("Enter the path to MHDDoS directory: ").strip()
    while not os.path.exists(os.path.join(mhddos_path, "start.py")):
        print("❌ Invalid path. Could not find start.py in the directory.")
        mhddos_path = input("Enter the path to MHDDoS directory: ").strip()
    
    # Get Telegram bot token
    token = input("Enter your Telegram bot token (from @BotFather): ").strip()
    while not re.match(r'^\d+:[a-zA-Z0-9_-]+$', token):
        print("❌ Invalid token format. Please enter a valid bot token.")
        token = input("Enter your Telegram bot token (from @BotFather): ").strip()
    
    # Get authorized user ID
    user_id = input("Enter your Telegram user ID (from @userinfobot): ").strip()
    while not user_id.isdigit():
        print("❌ Invalid user ID. Please enter a numeric user ID.")
        user_id = input("Enter your Telegram user ID (from @userinfobot): ").strip()
    
    # Update config.py
    with open("config.py", "r") as f:
        config = f.read()
    
    config = config.replace('TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"', f'TOKEN = "{token}"')
    config = config.replace('AUTHORIZED_USER_ID = 0000000000', f'AUTHORIZED_USER_ID = {user_id}')
    config = config.replace('MHDDOS_PATH = "PATH_TO_MHDDOS_DIRECTORY"', f'MHDDOS_PATH = "{mhddos_path.replace("\\", "\\\\")}"')
    
    with open("config.py", "w") as f:
        f.write(config)
    
    print("✅ Configuration completed successfully")

def create_launcher():
    """Create a launcher script"""
    is_windows = os.name == 'nt'
    
    if is_windows:
        # Create batch file for Windows
        with open("run_bot.bat", "w") as f:
            f.write('@echo off\n')
            f.write('echo Starting MHDDoS Telegram Bot...\n')
            f.write(f'"{sys.executable}" mhddos_telegram_bot_enhanced.py\n')
            f.write('pause\n')
        print("✅ Created Windows launcher: run_bot.bat")
    else:
        # Create shell script for Unix
        with open("run_bot.sh", "w") as f:
            f.write('#!/bin/bash\n')
            f.write('echo "Starting MHDDoS Telegram Bot..."\n')
            f.write(f'python3 mhddos_telegram_bot_enhanced.py\n')
        
        # Make it executable
        os.chmod("run_bot.sh", 0o755)
        print("✅ Created Unix launcher: run_bot.sh")

def main():
    """Main setup function"""
    print("MHDDoS Telegram Bot Setup\n" + "=" * 30)
    
    check_python_version()
    install_dependencies()
    configure_bot()
    create_launcher()
    
    print("\n" + "=" * 30)
    print("✅ Setup completed successfully!")
    print("You can now run the bot using:")
    if os.name == 'nt':
        print("   run_bot.bat")
    else:
        print("   ./run_bot.sh")
    print("\nMake sure the MHDDoS tool is properly installed and configured.")

if __name__ == "__main__":
    main() 