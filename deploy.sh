#!/bin/bash

echo "MHDDoS Telegram Bot Deployment Script"
echo "===================================="
echo

# Check if Python 3 is installed
if command -v python3 &>/dev/null; then
    echo "✅ Python 3 is installed"
else
    echo "❌ Python 3 is not installed. Please install Python 3 before continuing."
    exit 1
fi

# Check if pip is installed
if command -v pip3 &>/dev/null; then
    echo "✅ pip is installed"
else
    echo "❌ pip is not installed. Please install pip before continuing."
    exit 1
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p data templates
echo "✅ Directories created"

# Install dependencies
echo "Installing dependencies..."
pip3 install -r requirements.txt
if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Configure the bot
echo
echo "Bot Configuration"
echo "================="
echo "You need to configure the bot with your Telegram bot token and user ID."
echo

# Check if the bot file exists
if [ ! -f "mhddos_telegram_bot_enhanced.py" ]; then
    echo "❌ mhddos_telegram_bot_enhanced.py not found. Make sure you're in the correct directory."
    exit 1
fi

# Ask for bot token
echo -n "Enter your Telegram bot token (from @BotFather): "
read bot_token

# Ask for user ID
echo -n "Enter your Telegram user ID (from @userinfobot): "
read user_id

# Ask for MHDDoS path
echo -n "Enter the full path to MHDDoS directory: "
read mhddos_path

# Update the configuration in the bot file
sed -i "s|TOKEN = \"YOUR_TELEGRAM_BOT_TOKEN\"|TOKEN = \"$bot_token\"|g" mhddos_telegram_bot_enhanced.py
sed -i "s|AUTHORIZED_USER_ID = 0000000000|AUTHORIZED_USER_ID = $user_id|g" mhddos_telegram_bot_enhanced.py
sed -i "s|MHDDOS_PATH = \"PATH_TO_MHDDOS_DIRECTORY\"|MHDDOS_PATH = \"$mhddos_path\"|g" mhddos_telegram_bot_enhanced.py

echo "✅ Bot configured successfully"

# Create a service file
echo
echo "System Service Setup"
echo "=================="
echo "Would you like to set up the bot as a system service? (y/n)"
read setup_service

if [[ $setup_service == "y" || $setup_service == "Y" ]]; then
    echo "Creating systemd service file..."
    
    # Get current directory and username
    current_dir=$(pwd)
    current_user=$(whoami)
    
    # Create service file content
    service_content="[Unit]
Description=MHDDoS Telegram Bot
After=network.target

[Service]
User=$current_user
WorkingDirectory=$current_dir
ExecStart=/usr/bin/python3 $current_dir/mhddos_telegram_bot_enhanced.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target"
    
    # Check if we have permission to write to /etc/systemd/system
    if [ -w "/etc/systemd/system/" ]; then
        echo "$service_content" > /etc/systemd/system/mhddos-bot.service
        echo "✅ Service file created at /etc/systemd/system/mhddos-bot.service"
        
        # Enable and start the service
        systemctl enable mhddos-bot.service
        systemctl start mhddos-bot.service
        echo "✅ Service enabled and started"
        
        # Check service status
        echo "Service status:"
        systemctl status mhddos-bot.service
    else
        # Create the service file locally and provide instructions
        echo "$service_content" > mhddos-bot.service
        echo "✅ Service file created at $current_dir/mhddos-bot.service"
        echo
        echo "To install the service, run these commands with root privileges:"
        echo "sudo mv $current_dir/mhddos-bot.service /etc/systemd/system/"
        echo "sudo systemctl enable mhddos-bot.service"
        echo "sudo systemctl start mhddos-bot.service"
    fi
else
    echo "Skipping service setup."
    echo "You can run the bot manually with: python3 mhddos_telegram_bot_enhanced.py"
fi

echo
echo "Setup Complete!"
echo "==============="
echo "To make yourself an admin, you need to manually edit data/users.json after"
echo "you've started the bot and registered by sending /start to the bot."
echo
echo "Thank you for deploying the MHDDoS Telegram Bot!" 