@echo off
title C-MAP Enterprise Installer
color 0A

echo ===================================================
echo       C-MAP ENTERPRISE - AUTOMATED SETUP
echo ===================================================
echo.
echo Step 1: Checking for Python...
python --version
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed on this PC! 
    echo Please install Python 3.10+ and check the "Add to PATH" box.
    pause
    exit
)

echo.
echo Step 2: Creating an isolated Virtual Environment...
python -m venv venv

echo.
echo Step 3: Activating Environment and Installing Dependencies...
call venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Step 4: Preparing the Enterprise Database...
python manage.py migrate

echo.
echo ===================================================
echo    SETUP COMPLETE! LETS CREATE YOUR ADMIN ACCOUNT
echo ===================================================
python manage.py createsuperuser

echo.
echo ===================================================
echo    STARTING THE C-MAP SERVER...
echo ===================================================
echo Keep this black window open. To stop the server, press CTRL+C.
python manage.py runserver

pause