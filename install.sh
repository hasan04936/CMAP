#!/bin/bash

# Define colors for terminal output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}===================================================${NC}"
echo -e "${GREEN}      C-MAP ENTERPRISE - LINUX AUTOMATED SETUP     ${NC}"
echo -e "${GREEN}===================================================${NC}"
echo ""

echo "Step 1: Checking for Python 3..."
if ! command -v python3 &> /dev/null
then
    echo -e "${RED}[ERROR] Python 3 is not installed on this machine!${NC}"
    echo "Please install it by running: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

echo ""
echo "Step 2: Creating an isolated Virtual Environment..."
python3 -m venv venv

echo ""
echo "Step 3: Activating Environment and Installing Dependencies..."
# Linux uses source and forward slashes instead of Windows backslashes
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Step 4: Preparing the Enterprise Database..."
python3 manage.py migrate

echo ""
echo -e "${GREEN}===================================================${NC}"
echo -e "${GREEN}   SETUP COMPLETE! LETS CREATE YOUR ADMIN ACCOUNT  ${NC}"
echo -e "${GREEN}===================================================${NC}"
python3 manage.py createsuperuser

echo ""
echo -e "${GREEN}===================================================${NC}"
echo -e "${GREEN}   STARTING THE C-MAP SERVER...                    ${NC}"
echo -e "${GREEN}===================================================${NC}"
echo "To stop the server, press CTRL+C."
python3 manage.py runserver