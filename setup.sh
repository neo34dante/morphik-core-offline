#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Function to display messages
function echo_msg() {
    echo -e "\n==== $1 ====\n"
}

# 1. Install Python 3.12
echo_msg "Installing Python 3.12"
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update && sudo apt -y upgrade
sudo apt install -y python3.12 python3.12-venv python3.12-dev

# 9. Set up Python virtual environment
echo_msg "Setting up Python virtual environment"
python3.12 -m venv venv
source venv/bin/activate

# 10. Install Python dependencies
echo_msg "Installing Python dependencies"
pip install --upgrade pip
pip install pytest pytest-cov flake8 black isort mypy

# 11. Configure environment variables
echo_msg "Setup completed"
