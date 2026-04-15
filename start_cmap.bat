@echo off
title C-MAP Enterprise Server
color 0B

echo ===================================================
echo       STARTING C-MAP ENTERPRISE SERVER...
echo ===================================================
echo Please keep this black window open while working.
echo.

:: Activate the virtual environment
call venv\Scripts\activate

:: Automatically open the default web browser to the app
start http://localhost:8000

:: Start the Django server
python manage.py runserver