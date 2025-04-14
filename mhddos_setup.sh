#!/bin/bash

# Text colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}    MHDDoS Telegram Bot Auto Setup      ${NC}"
echo -e "${BLUE}========================================${NC}"
echo

# Check for required tools
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 could not be found${NC}"
        echo -e "${YELLOW}Installing $1...${NC}"
        
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y $1
        elif command -v yum &> /dev/null; then
            sudo yum install -y $1
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y $1
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm $1
        else
            echo -e "${RED}❌ Could not install $1. Please install it manually.${NC}"
            exit 1
        fi
        
        if ! command -v $1 &> /dev/null; then
            echo -e "${RED}❌ Failed to install $1. Please install it manually.${NC}"
            exit 1
        fi
    fi
    echo -e "${GREEN}✅ $1 is installed${NC}"
}

check_command git
check_command python3
check_command pip3

# Create a base directory
BASE_DIR="$HOME/mhddos-telegram-setup"
mkdir -p "$BASE_DIR"
cd "$BASE_DIR"

echo
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}         Downloading repositories       ${NC}"
echo -e "${BLUE}========================================${NC}"

# Clone MHDDoS repository
echo -e "${YELLOW}Downloading MHDDoS...${NC}"
if [ -d "MHDDoS" ]; then
    echo -e "${YELLOW}MHDDoS directory already exists. Updating...${NC}"
    cd MHDDoS
    git pull
    cd ..
else
    git clone https://github.com/MatrixTM/MHDDoS.git
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Failed to clone MHDDoS repository${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✅ MHDDoS downloaded successfully${NC}"

# Get Telegram bot token
echo
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}         Telegram Bot Configuration     ${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}You need a Telegram bot token. If you don't have one, please create a bot by talking to @BotFather on Telegram.${NC}"
echo
read -p "Enter your Telegram bot token: " BOT_TOKEN

# Get Telegram user ID
echo
echo -e "${YELLOW}You need your Telegram user ID. If you don't know it, please talk to @userinfobot on Telegram.${NC}"
echo
read -p "Enter your Telegram user ID: " USER_ID

# Clone MHDDoS-Telegram-Bot repository using default URL
echo
echo -e "${YELLOW}Using default MHDDoS-Telegram-Bot repository: https://github.com/AnonAmit/MHDDoS-Telegram-Bot.git${NC}"
BOT_REPO="https://github.com/AnonAmit/MHDDoS-Telegram-Bot.git"

echo -e "${YELLOW}Downloading Telegram Bot...${NC}"
BOT_DIR="MHDDoS-Telegram-Bot"
if [ -d "$BOT_DIR" ]; then
    echo -e "${YELLOW}$BOT_DIR directory already exists. Updating...${NC}"
    cd "$BOT_DIR"
    git pull
    cd ..
else
    git clone "$BOT_REPO" "$BOT_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Failed to clone bot repository${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✅ Telegram Bot downloaded successfully${NC}"

# Install MHDDoS dependencies
echo
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}          Installing Dependencies       ${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "${YELLOW}Installing MHDDoS dependencies...${NC}"
cd "$BASE_DIR/MHDDoS"
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to install MHDDoS dependencies${NC}"
    exit 1
fi
echo -e "${GREEN}✅ MHDDoS dependencies installed successfully${NC}"

# Set up the bot
echo -e "${YELLOW}Installing Telegram Bot dependencies...${NC}"
cd "$BASE_DIR/$BOT_DIR"
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to install Telegram Bot dependencies${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Telegram Bot dependencies installed successfully${NC}"

# Create necessary directories
mkdir -p data templates

# Update bot configuration
echo -e "${YELLOW}Configuring Telegram Bot...${NC}"
MHDDOS_PATH="$BASE_DIR/MHDDoS"

# Check which file exists
BOT_FILE=""
if [ -f "mhddos_telegram_bot_enhanced.py" ]; then
    BOT_FILE="mhddos_telegram_bot_enhanced.py"
elif [ -f "mhddos_bot_standalone.py" ]; then
    BOT_FILE="mhddos_bot_standalone.py"
else
    echo -e "${RED}❌ Could not find the main bot file. Please check your repository.${NC}"
    exit 1
fi

# Replace configuration values
sed -i "s|TOKEN = \"YOUR_TELEGRAM_BOT_TOKEN\"|TOKEN = \"$BOT_TOKEN\"|g" "$BOT_FILE"
sed -i "s|AUTHORIZED_USER_ID = 0000000000|AUTHORIZED_USER_ID = $USER_ID|g" "$BOT_FILE"
sed -i "s|MHDDOS_PATH = \"PATH_TO_MHDDOS_DIRECTORY\"|MHDDOS_PATH = \"$MHDDOS_PATH\"|g" "$BOT_FILE"

echo -e "${GREEN}✅ Telegram Bot configured successfully${NC}"

echo
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}          Setting Up Admin Access       ${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}Starting the bot temporarily to generate initial files...${NC}"

# Run the bot briefly to generate user file
echo "Starting bot for 10 seconds to generate user file..."
python3 "$BOT_FILE" &
BOT_PID=$!
echo "Bot started with PID: $BOT_PID"

# Wait a bit to let it initialize
sleep 10

# Kill the bot process
kill $BOT_PID
echo "Bot stopped."

# Wait for the process to terminate completely
sleep 2

# Check if users.json was created
if [ -f "data/users.json" ]; then
    echo -e "${GREEN}✅ User file was created${NC}"
    
    # Add user as admin if needed
    if [ -s "data/users.json" ]; then
        # Check if the file has content and modify it
        sed -i "s|\"role\": \"trial\"|\"role\": \"admin\"|g" "data/users.json"
        echo -e "${GREEN}✅ User role updated to admin${NC}"
    else
        # Create a basic users.json with admin user
        echo "{\"$USER_ID\": {\"username\": \"admin\", \"first_name\": \"Admin\", \"role\": \"admin\", \"created_at\": $(date +%s), \"subscription\": {\"plan\": null, \"start_date\": null, \"end_date\": null, \"attacks_used\": 0, \"attacks_limit\": 0, \"active\": false}, \"payment_history\": [], \"attack_history\": []}}" > data/users.json
        echo -e "${GREEN}✅ Admin user created in users.json${NC}"
    fi
else
    echo -e "${YELLOW}⚠️ data/users.json not found. You'll need to create it manually later.${NC}"
fi

echo
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}            Setting Up Service          ${NC}"
echo -e "${BLUE}========================================${NC}"

# Ask if user wants to set up a systemd service
echo -e "${YELLOW}Would you like to set up the bot as a system service? (y/n)${NC}"
read -p "" SETUP_SERVICE

if [[ $SETUP_SERVICE == "y" || $SETUP_SERVICE == "Y" ]]; then
    # Get the current directory and username
    CURRENT_DIR="$(pwd)"
    CURRENT_USER="$(whoami)"
    
    # Create service file content
    SERVICE_CONTENT="[Unit]
Description=MHDDoS Telegram Bot
After=network.target

[Service]
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
ExecStart=/usr/bin/python3 $CURRENT_DIR/$BOT_FILE
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target"
    
    # Create service file
    echo "$SERVICE_CONTENT" > "mhddos-bot.service"
    
    # Check if we have permission to write to /etc/systemd/system
    if [ -w "/etc/systemd/system/" ]; then
        sudo mv "mhddos-bot.service" "/etc/systemd/system/"
        sudo systemctl daemon-reload
        sudo systemctl enable mhddos-bot.service
        sudo systemctl start mhddos-bot.service
        echo -e "${GREEN}✅ Service enabled and started${NC}"
        
        echo -e "${YELLOW}Service status:${NC}"
        sudo systemctl status mhddos-bot.service --no-pager
    else
        echo -e "${YELLOW}⚠️ You don't have permission to create the service file directly.${NC}"
        echo -e "${YELLOW}The service file has been created at: $CURRENT_DIR/mhddos-bot.service${NC}"
        echo
        echo -e "${YELLOW}To install it, run these commands with root privileges:${NC}"
        echo "sudo mv $CURRENT_DIR/mhddos-bot.service /etc/systemd/system/"
        echo "sudo systemctl daemon-reload"
        echo "sudo systemctl enable mhddos-bot.service"
        echo "sudo systemctl start mhddos-bot.service"
    fi
else
    # Create a run script instead
    RUN_SCRIPT="#!/bin/bash
cd \"$CURRENT_DIR\"
python3 \"$BOT_FILE\"
"
    echo "$RUN_SCRIPT" > "run_bot.sh"
    chmod +x "run_bot.sh"
    
    echo -e "${GREEN}✅ Created run_bot.sh script${NC}"
    echo -e "${YELLOW}You can run the bot with: ./run_bot.sh${NC}"
fi

echo
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}            Setup Complete!            ${NC}"
echo -e "${GREEN}========================================${NC}"
echo
echo -e "${YELLOW}Your MHDDoS Telegram Bot has been set up successfully!${NC}"
echo
echo -e "${YELLOW}Installation details:${NC}"
echo -e "  MHDDoS directory: ${BLUE}$MHDDOS_PATH${NC}"
echo -e "  Bot directory: ${BLUE}$BASE_DIR/$BOT_DIR${NC}"
echo -e "  Bot file: ${BLUE}$BOT_FILE${NC}"
echo

if [[ $SETUP_SERVICE == "y" || $SETUP_SERVICE == "Y" ]]; then
    echo -e "${YELLOW}The bot is running as a system service and will start automatically on boot.${NC}"
    echo -e "${YELLOW}You can manage it with these commands:${NC}"
    echo -e "  ${BLUE}sudo systemctl status mhddos-bot.service${NC} - Check bot status"
    echo -e "  ${BLUE}sudo systemctl stop mhddos-bot.service${NC} - Stop the bot"
    echo -e "  ${BLUE}sudo systemctl start mhddos-bot.service${NC} - Start the bot"
    echo -e "  ${BLUE}sudo systemctl restart mhddos-bot.service${NC} - Restart the bot"
    echo -e "  ${BLUE}sudo journalctl -u mhddos-bot.service -f${NC} - View logs"
else
    echo -e "${YELLOW}You can start the bot by running: ${BLUE}./run_bot.sh${NC}"
fi

echo
echo -e "${YELLOW}Send ${BLUE}/start${YELLOW} to your bot on Telegram to get started.${NC}"
echo -e "${YELLOW}That's it! Your MHDDoS Telegram Bot is ready to use.${NC}" 