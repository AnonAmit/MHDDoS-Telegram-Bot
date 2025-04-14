@echo off
setlocal enabledelayedexpansion

echo ========================================
echo     MHDDoS Telegram Bot Auto Setup
echo ========================================
echo.

:: Check if required tools are installed
echo Checking required tools...

:: Check for Git
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo X Git is not installed. Please install Git from https://git-scm.com/downloads
    pause
    exit /b 1
) else (
    echo ✓ Git is installed
)

:: Check for Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo X Python is not installed. Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
) else (
    echo ✓ Python is installed
)

:: Check for pip
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo X pip is not installed. It should come with Python.
    pause
    exit /b 1
) else (
    echo ✓ pip is installed
)

:: Create base directory
set BASE_DIR=%USERPROFILE%\mhddos-telegram-setup
if not exist "%BASE_DIR%" mkdir "%BASE_DIR%"
cd /d "%BASE_DIR%"

echo.
echo ========================================
echo         Downloading repositories
echo ========================================

:: Clone MHDDoS repository
echo Downloading MHDDoS...
if exist MHDDoS (
    echo MHDDoS directory already exists. Updating...
    cd MHDDoS
    git pull
    cd ..
) else (
    git clone https://github.com/MatrixTM/MHDDoS.git
    if %errorlevel% neq 0 (
        echo X Failed to clone MHDDoS repository
        pause
        exit /b 1
    )
)
echo ✓ MHDDoS downloaded successfully

:: Get Telegram bot token
echo.
echo ========================================
echo         Telegram Bot Configuration
echo ========================================
echo You need a Telegram bot token. If you don't have one, please create a bot by talking to @BotFather on Telegram.
echo.
set /p BOT_TOKEN=Enter your Telegram bot token: 

:: Get Telegram user ID
echo.
echo You need your Telegram user ID. If you don't know it, please talk to @userinfobot on Telegram.
echo.
set /p USER_ID=Enter your Telegram user ID: 

:: Clone MHDDoS-Telegram-Bot repository using default URL
echo.
echo Using default MHDDoS-Telegram-Bot repository: https://github.com/AnonAmit/MHDDoS-Telegram-Bot.git
set BOT_REPO=https://github.com/AnonAmit/MHDDoS-Telegram-Bot.git

echo Downloading Telegram Bot...
set BOT_DIR=MHDDoS-Telegram-Bot
if exist "%BOT_DIR%" (
    echo %BOT_DIR% directory already exists. Updating...
    cd "%BOT_DIR%"
    git pull
    cd ..
) else (
    git clone "%BOT_REPO%" "%BOT_DIR%"
    if %errorlevel% neq 0 (
        echo X Failed to clone bot repository
        pause
        exit /b 1
    )
)
echo ✓ Telegram Bot downloaded successfully

:: Install dependencies
echo.
echo ========================================
echo          Installing Dependencies
echo ========================================

echo Installing MHDDoS dependencies...
cd /d "%BASE_DIR%\MHDDoS"
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo X Failed to install MHDDoS dependencies
    pause
    exit /b 1
)
echo ✓ MHDDoS dependencies installed successfully

:: Set up the bot
echo Installing Telegram Bot dependencies...
cd /d "%BASE_DIR%\%BOT_DIR%"
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo X Failed to install Telegram Bot dependencies
    pause
    exit /b 1
)
echo ✓ Telegram Bot dependencies installed successfully

:: Create necessary directories
if not exist data mkdir data
if not exist templates mkdir templates

:: Update bot configuration
echo Configuring Telegram Bot...
set MHDDOS_PATH=%BASE_DIR%\MHDDoS
set MHDDOS_PATH_ESCAPED=%MHDDOS_PATH:\=\\%

:: Check which file exists
set BOT_FILE=
if exist mhddos_telegram_bot_enhanced.py (
    set BOT_FILE=mhddos_telegram_bot_enhanced.py
) else if exist mhddos_bot_standalone.py (
    set BOT_FILE=mhddos_bot_standalone.py
) else (
    echo X Could not find the main bot file. Please check your repository.
    pause
    exit /b 1
)

:: Create a temporary file and replace the configuration
type "%BOT_FILE%" > temp_file.py
powershell -Command "(Get-Content temp_file.py) -replace 'TOKEN = \"YOUR_TELEGRAM_BOT_TOKEN\"', 'TOKEN = \"%BOT_TOKEN%\"' -replace 'AUTHORIZED_USER_ID = 0000000000', 'AUTHORIZED_USER_ID = %USER_ID%' -replace 'MHDDOS_PATH = \"PATH_TO_MHDDOS_DIRECTORY\"', 'MHDDOS_PATH = r\"%MHDDOS_PATH_ESCAPED%\"' | Set-Content temp_file.py"
move /y temp_file.py "%BOT_FILE%"

echo ✓ Telegram Bot configured successfully

echo.
echo ========================================
echo          Setting Up Admin Access
echo ========================================
echo Starting the bot temporarily to generate initial files...

:: Run the bot briefly to generate user file
echo Starting bot for 10 seconds to generate user file...
start /b python "%BOT_FILE%"

:: Wait a bit
timeout /t 10 /nobreak > nul

:: Kill the bot process
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq python.exe" /fi "windowtitle eq %BOT_FILE%" ^| find "python.exe"') do (
    taskkill /pid %%a /f > nul 2>&1
)
echo Bot stopped.

:: Wait for the process to terminate completely
timeout /t 2 /nobreak > nul

:: Check if users.json was created
if exist data\users.json (
    echo ✓ User file was created
    
    :: Check if the file has content
    for %%A in (data\users.json) do set filesize=%%~zA
    if !filesize! gtr 0 (
        :: Modify users.json to make the user an admin
        powershell -Command "(Get-Content data\users.json) -replace '\"role\": \"trial\"', '\"role\": \"admin\"' | Set-Content data\users.json"
        echo ✓ User role updated to admin
    ) else (
        :: Create a basic users.json with admin user
        set timestamp=%time:~0,2%%time:~3,2%%time:~6,2%
        set timestamp=%timestamp: =0%
        powershell -Command "$json = @{""$env:USER_ID"" = @{""username"" = ""admin""; ""first_name"" = ""Admin""; ""role"" = ""admin""; ""created_at"" = [int][double]::Parse($(Get-Date -UFormat %%s)); ""subscription"" = @{""plan"" = $null; ""start_date"" = $null; ""end_date"" = $null; ""attacks_used"" = 0; ""attacks_limit"" = 0; ""active"" = $false}; ""payment_history"" = @(); ""attack_history"" = @()}}; $json | ConvertTo-Json -Depth 10 > data\users.json"
        echo ✓ Admin user created in users.json
    )
) else (
    echo ⚠️ data\users.json not found. You'll need to create it manually later.
)

echo.
echo ========================================
echo         Creating Startup Script
echo ========================================

:: Create a startup batch file
echo @echo off > run_bot.bat
echo echo Starting MHDDoS Telegram Bot... >> run_bot.bat
echo cd /d "%BASE_DIR%\%BOT_DIR%" >> run_bot.bat
echo python "%BOT_FILE%" >> run_bot.bat
echo pause >> run_bot.bat

echo ✓ Created run_bot.bat script

:: Create shortcut on desktop
echo Creating desktop shortcut...
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut([System.IO.Path]::Combine($WshShell.SpecialFolders.Item('Desktop'), 'MHDDoS Telegram Bot.lnk')); $Shortcut.TargetPath = '%BASE_DIR%\%BOT_DIR%\run_bot.bat'; $Shortcut.WorkingDirectory = '%BASE_DIR%\%BOT_DIR%'; $Shortcut.Description = 'Start MHDDoS Telegram Bot'; $Shortcut.Save()"
echo ✓ Desktop shortcut created

echo.
echo ========================================
echo            Setup Complete!
echo ========================================
echo.
echo Your MHDDoS Telegram Bot has been set up successfully!
echo.
echo Installation details:
echo   MHDDoS directory: %MHDDOS_PATH%
echo   Bot directory: %BASE_DIR%\%BOT_DIR%
echo   Bot file: %BOT_FILE%
echo.
echo You can start the bot by:
echo   1. Double-clicking the desktop shortcut
echo   2. Running run_bot.bat in %BASE_DIR%\%BOT_DIR%
echo.
echo Send /start to your bot on Telegram to get started.
echo That's it! Your MHDDoS Telegram Bot is ready to use.

pause 