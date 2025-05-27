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
sudo apt update
sudo apt install curl ca-certificates gnupg
sudo apt install -y python3.12 python3.12-venv python3.12-dev
curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo gpg --dearmor -o /usr/share/keyrings/postgresql.gpg
echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list
# 2. Install PostgreSQL 17
echo_msg "Installing PostgreSQL 17"
sudo apt update
sudo apt install -y postgresql-17 postgresql-contrib-17

# 3. Install pgvector
echo_msg "Installing pgvector extension"
sudo apt install -y postgresql-17-pgvector

# 7. Install Ollama
echo_msg "Installing Ollama"
curl -fsSL https://ollama.com/install.sh | sh

# 9. Set up Python virtual environment
echo_msg "Setting up Python virtual environment"
python3.12 -m venv venv
source venv/bin/activate

# 10. Install Python dependencies
echo_msg "Installing Python dependencies"
pip install --upgrade pip
pip install -r requirements.txt --use-deprecated=legacy-resolver

# 11. Configure environment variables
echo_msg "Setup completed"
