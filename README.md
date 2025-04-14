# MHDDoS Telegram Controller Bot

A Telegram bot for controlling the [MHDDoS](https://github.com/MatrixTM/MHDDoS) DDoS attack tool.

## ⚠️ Important Disclaimer

**This tool is provided for EDUCATIONAL and AUTHORIZED TESTING purposes ONLY.**

- Use this tool ONLY on systems and networks you own or have explicit permission to test
- You are solely responsible for complying with applicable laws in your jurisdiction
- The developers assume NO LIABILITY for any misuse of this software
- Unauthorized DDoS attacks are ILLEGAL and may result in severe legal consequences
- By using this software, you agree to use it responsibly and ethically

## Features

- Launch DDoS attacks with various methods
- View attack status and output
- Manage attack templates
- Schedule attacks
- Track attack statistics
- User management with subscription system
- Payment processing and transaction tracking

## Deployment Instructions

### Automatic Setup (Recommended)

#### Linux/Unix Systems

1. Download the automatic setup script:
```bash
wget https://raw.githubusercontent.com/AnonAmit/MHDDoS-Telegram-Bot/main/mhddos_setup.sh
```

2. Make it executable:
```bash
chmod +x mhddos_setup.sh
```

3. Run the script:
```bash
./mhddos_setup.sh
```

4. Follow the prompts to provide:
   - Your Telegram bot token (get from [@BotFather](https://t.me/BotFather))
   - Your Telegram user ID (get from [@userinfobot](https://t.me/userinfobot))

5. The script will automatically:
   - Download MHDDoS and the bot code
   - Install all dependencies
   - Configure the bot
   - Set you up as an admin
   - Create a service or startup script

#### Windows Systems

1. Download the automatic setup script `mhddos_setup.bat` from the repository

2. Run the script by double-clicking it

3. Follow the prompts to provide:
   - Your Telegram bot token (get from [@BotFather](https://t.me/BotFather))
   - Your Telegram user ID (get from [@userinfobot](https://t.me/userinfobot))

4. The script will automatically:
   - Download MHDDoS and the bot code
   - Install all dependencies
   - Configure the bot
   - Set you up as an admin
   - Create a desktop shortcut

### Manual Installation

1. Clone or download this repository:
```bash
git clone https://github.com/AnonAmit/MHDDoS-Telegram-Bot.git
cd MHDDoS-Telegram-Bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the bot:
   - Open `mhddos_telegram_bot_enhanced.py`
   - Replace the following values:
     - `TOKEN` with your Telegram Bot token
     - `AUTHORIZED_USER_ID` with your Telegram user ID (get from [@userinfobot](https://t.me/userinfobot))
     - `MHDDOS_PATH` with the path to your MHDDoS installation

4. Create necessary directories:
```bash
mkdir -p data templates
```

### Running the Bot

```bash
python mhddos_telegram_bot_enhanced.py
```

For production deployment, you may want to use a process manager like systemd or supervisor to ensure the bot stays running.

#### Example systemd service

1. Create a service file:
```bash
sudo nano /etc/systemd/system/mhddos-bot.service
```

2. Add the following content:
```
[Unit]
Description=MHDDoS Telegram Bot
After=network.target

[Service]
User=yourusername
WorkingDirectory=/path/to/mhddos-telegram-bot
ExecStart=/usr/bin/python3 /path/to/mhddos-telegram-bot/mhddos_telegram_bot_enhanced.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:
```bash
sudo systemctl enable mhddos-bot.service
sudo systemctl start mhddos-bot.service
```

### Admin Setup

1. Start the bot and send `/start` to register yourself
2. To make yourself an admin, you need to manually edit the users data file:
   ```bash
   # Open the data/users.json file
   nano data/users.json
   ```
   
3. Find your user entry and change the role to "admin":
   ```json
   "YOUR_USER_ID": {
     "username": "your_username",
     "first_name": "Your Name",
     "role": "admin",
     ...
   }
   ```

4. Restart the bot:
   ```bash
   sudo systemctl restart mhddos-bot.service
   ```

## Usage

### Basic Commands

- `/start` - Get started with the bot
- `/help` - Show help message with all commands
- `/attack [target] [method] [threads] [duration]` - Start an attack
- `/stop` - Stop all running attacks
- `/status` - View running attacks
- `/methods` - List available attack methods

### Templates

- `/templates` - List saved attack templates
- `/template_info [name]` - Show template details
- `/create_template [name] [target] [method] [threads] [duration] [description]` - Create a template
- `/run_template [name]` - Run an attack template
- `/delete_template [name]` - Delete a template

### Scheduling

- `/schedule [target] [method] [threads] [duration] [time]` - Schedule an attack
- `/schedule_template [name] [time]` - Schedule a template attack
- `/schedules` - List scheduled attacks
- `/cancel_schedule [id]` - Cancel a scheduled attack

### Statistics

- `/stats` - View attack statistics
- `/daily_stats` - View daily attack statistics

### User Subscription Commands

- `/plans` - View available subscription plans
- `/subscription` - View your subscription details
- `/payment` - View payment options
- `/redeem [code]` - Redeem a subscription code
- `/purchase [plan_id] [payment_method] [payment_id]` - Record a purchase
- `/history` - View your attack history

### Admin Commands

- `/admin_help` - View admin commands
- `/admin_users` - List all users
- `/admin_user [user_id]` - View user details
- `/admin_make_admin [user_id]` - Make a user an admin
- `/admin_transactions` - View pending transactions
- `/admin_approve [transaction_id] [optional_note]` - Approve a transaction
- `/admin_reject [transaction_id] [reason]` - Reject a transaction
- `/admin_plans` - List all subscription plans
- `/admin_plan [plan_id]` - View plan details
- `/admin_generate_codes [plan_id] [count]` - Generate redeem codes
- `/admin_stats` - View system statistics

## Subscription System

The bot includes a subscription system that allows:
- Different subscription tiers with varying capabilities
- Manual payment verification via crypto, UPI, and gift cards
- Redeem codes for instant activation
- Usage tracking and restrictions based on plan limits

## Security

The bot implements security measures through:
- User authentication
- Role-based access control
- Subscription-based access restrictions

## Disclaimer and Legal Notice

### ⚠️ Legal Warning

The MHDDoS Telegram Bot is designed and provided for educational purposes and legitimate security testing only. Misuse of this tool may violate local, state, national, and international laws. Users are solely responsible for their actions when using this software.

### 🛡️ Permitted Use

This tool may ONLY be used in the following scenarios:
- Testing your own systems or networks
- Testing systems or networks where you have obtained EXPLICIT written permission
- Educational environments for learning about network security
- Authorized security research and penetration testing

### ❌ Prohibited Use

The following uses are strictly prohibited:
- Attacks on systems or networks without explicit permission
- Any activity intended to cause service disruption or damage
- Attempts to compromise the security or functionality of public or private networks
- Any malicious activity targeting individuals, companies, or organizations

### 📜 Liability Disclaimer

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED. The developers and contributors of this project:
- Accept no responsibility for any misuse of the software
- Assume no liability for any damages resulting from the use of this software
- Make no guarantees regarding the suitability, reliability, or accuracy of this software

By downloading, installing, or using this software, you acknowledge that you have read and understood this disclaimer and agree to use the software in accordance with all applicable laws and regulations. 

## License

This project is released under the Creative Commons Attribution-NonCommercial 4.0 International License.

**Key points of this license:**

- **Attribution** — You must give appropriate credit, provide a link to the license, and indicate if changes were made.
- **NonCommercial** — You may not use the material for commercial purposes.
- **No additional restrictions** — You may not apply legal terms or technological measures that legally restrict others from doing anything the license permits.

This means you are free to:
- Share — copy and redistribute the material in any medium or format
- Adapt — remix, transform, and build upon the material

Under the following terms:
- You must give appropriate credit and provide a link to the license
- You may not use the material for commercial purposes
- You may not apply legal terms that legally restrict others from doing anything the license permits

For the full license text, see the [LICENSE](LICENSE) file or visit: [CC BY-NC 4.0](http://creativecommons.org/licenses/by-nc/4.0/)