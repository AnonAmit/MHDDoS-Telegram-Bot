@echo off
echo MHDDoS Telegram Bot Deployment Script
echo ====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo X Python is not installed. Please install Python before continuing.
    exit /b 1
) else (
    echo √ Python is installed
)

REM Check if pip is installed
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo X pip is not installed. Please install pip before continuing.
    exit /b 1
) else (
    echo √ pip is installed
)

REM Create necessary directories
echo Creating directories...
if not exist data mkdir data
if not exist templates mkdir templates
echo √ Directories created

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo X Failed to install dependencies
    exit /b 1
) else (
    echo √ Dependencies installed successfully
)

REM Configure the bot
echo.
echo Bot Configuration
echo ================
echo You need to configure the bot with your Telegram bot token and user ID.
echo.

REM Check if the bot file exists
if not exist mhddos_telegram_bot_enhanced.py (
    echo X mhddos_telegram_bot_enhanced.py not found. Make sure you're in the correct directory.
    exit /b 1
)

REM Ask for bot token
set /p bot_token=Enter your Telegram bot token (from @BotFather): 

REM Ask for user ID
set /p user_id=Enter your Telegram user ID (from @userinfobot): 

REM Ask for MHDDoS path
set /p mhddos_path=Enter the full path to MHDDoS directory (use double backslashes \\): 

REM Create a temporary file with modifications
type mhddos_telegram_bot_enhanced.py | powershell -Command "$input | ForEach-Object { $_ -replace 'TOKEN = \"YOUR_TELEGRAM_BOT_TOKEN\"', 'TOKEN = \"%bot_token%\"' -replace 'AUTHORIZED_USER_ID = 0000000000', 'AUTHORIZED_USER_ID = %user_id%' -replace 'MHDDOS_PATH = \"PATH_TO_MHDDOS_DIRECTORY\"', 'MHDDOS_PATH = \"%mhddos_path%\"' }" > mhddos_telegram_bot_enhanced.py.tmp

REM Replace the original file with the modified one
move /y mhddos_telegram_bot_enhanced.py.tmp mhddos_telegram_bot_enhanced.py

echo √ Bot configured successfully

REM Create a startup script
echo @echo off > run_bot.bat
echo echo Starting MHDDoS Telegram Bot... >> run_bot.bat
echo python mhddos_telegram_bot_enhanced.py >> run_bot.bat
echo pause >> run_bot.bat

echo.
echo Setup Complete!
echo ==============
echo A startup script run_bot.bat has been created.
echo.
echo To make yourself an admin, you need to:
echo 1. Run the bot using run_bot.bat
echo 2. Send /start to your bot in Telegram
echo 3. Edit data/users.json to change your role to "admin"
echo 4. Restart the bot
echo.
echo Thank you for deploying the MHDDoS Telegram Bot!

pause 