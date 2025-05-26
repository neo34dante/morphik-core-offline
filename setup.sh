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
sudo apt install -y python3.12 python3.12-venv python3.12-dev

# 2. Install PostgreSQL 14 and pgvector
echo_msg "Installing PostgreSQL 14 and pgvector"
sudo apt install -y postgresql-14 postgresql-server-dev-14
sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 3. Start PostgreSQL service
echo_msg "Starting PostgreSQL service"
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 4. Create Morphik database and user
echo_msg "Creating Morphik database and user"
sudo -u postgres psql <<EOF
CREATE DATABASE morphik;
CREATE USER morphik_user WITH PASSWORD 'morphik_pass';
GRANT ALL PRIVILEGES ON DATABASE morphik TO morphik_user;
EOF

# 5. Install Ollama
echo_msg "Installing Ollama"
curl -fsSL https://ollama.com/install.sh | sh

# 6. Clone Morphik repository
echo_msg "Cloning Morphik repository"
git clone https://github.com/neo34dante/morphik-core-offline.git
cd morphik-core-offline
git checkout update-local-models

# 7. Set up Python virtual environment
echo_msg "Setting up Python virtual environment"
python3.12 -m venv venv
source venv/bin/activate

# 8. Install Python dependencies
echo_msg "Installing Python dependencies"
pip install --upgrade pip
pip install -r requirements.txt --use-deprecated=legacy-resolver

# 9. Configure environment variables
echo_msg "Configuring environment variables"
cp .env.local.example .env.local
sed -i 's|^#*POSTGRES_URL=.*|POSTGRES_URL=postgresql://morphik_user:morphik_pass@localhost:5432/morphik|' .env.local
sed -i 's|^#*OLLAMA_BASE_URL=.*|OLLAMA_BASE_URL=http://localhost:11434|' .env.local

# 10. Initialize database schema
echo_msg "Initializing database schema"
python scripts/init_db.py

# 11. Launch Morphik server
echo_msg "Launching Morphik server"
python start_server.py
