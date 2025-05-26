#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# 0. Prepare keyrings directory
sudo mkdir -p /etc/apt/keyrings

# ─────────────────────────────────────────────────────────────────────────────
# 1. NVIDIA CUDA repository (Ubuntu 24.04)
curl -fsSL \
  https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-ubuntu2404-keyring.gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/cuda-archive-keyring.gpg

echo \
  "deb [signed-by=/etc/apt/keyrings/cuda-archive-keyring.gpg] \
   https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/ /" \
  | sudo tee /etc/apt/sources.list.d/cuda.list

# ─────────────────────────────────────────────────────────────────────────────
# 2. Google Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub \
  | sudo gpg --dearmor -o /etc/apt/keyrings/google-linux-signing-keyring.gpg

echo \
  "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-linux-signing-keyring.gpg] \
   http://dl.google.com/linux/chrome/deb/ stable main" \
  | sudo tee /etc/apt/sources.list.d/google-chrome.list

# ─────────────────────────────────────────────────────────────────────────────
# 3. NVIDIA Container Toolkit (for Docker)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -sL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# ─────────────────────────────────────────────────────────────────────────────
# 4. PostgreSQL 17 + pgvector
curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
  | sudo gpg --dearmor -o /etc/apt/keyrings/pgdg-keyring.gpg

echo \
  "deb [signed-by=/etc/apt/keyrings/pgdg-keyring.gpg] \
   http://apt.postgresql.org/pub/repos/apt noble-pgdg main" \
  | sudo tee /etc/apt/sources.list.d/pgdg.list

# ─────────────────────────────────────────────────────────────────────────────
# 5. Update & upgrade core OS packages
sudo apt update && sudo apt -y upgrade

# ─────────────────────────────────────────────────────────────────────────────
# 6. Install your manual APT list (skipping missing ones)
echo "🔍 Installing APT packages from apt-manual.txt" 
while IFS= read -r pkg; do
  # skip blanks and comments
  [[ -z "$pkg" || "$pkg" == \#* ]] && continue

  if apt-cache show "$pkg" > /dev/null 2>&1; then
    echo "✔️  $pkg"
    sudo apt install -y "$pkg"
  else
    echo "⚠️  skipping unavailable: $pkg"
  fi
done < apt-manual.txt  # :contentReference[oaicite:0]{index=0}

# ─────────────────────────────────────────────────────────────────────────────
# 7. Ollama model pulls
if ! command -v ollama &>/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
ollama pull llama3.2
ollama pull gemma3
ollama pull nomic-embed-text

# ─────────────────────────────────────────────────────────────────────────────
# 8. Docker Redis
docker pull redis:7.2.3-alpine

# ─────────────────────────────────────────────────────────────────────────────
# 9. Python 3.11 virtualenv
python3.11 -m venv .venv
# shellcheck source=/dev/null
source .venv/bin/activate

# ─────────────────────────────────────────────────────────────────────────────
# 10. Hugging Face & model downloads
pip install --upgrade pip setuptools wheel
pip install huggingface_hub

if [ -n "${HF_API_TOKEN:-}" ]; then
  huggingface-cli login --token "$HF_API_TOKEN"

  echo "⏬ Downloading local_models…"
  python3 - <<'PYCODE'
import os
from huggingface_hub import snapshot_download
token = os.getenv("HF_API_TOKEN")

for repo, path in [
    ("vidore/colSmol-256M", "local_models/colSmol-256M"),
    ("tsystems/colqwen2.5-3b-multilingual-v1.0", "local_models/colqwen2.5-3b-multilingual-v1.0"),
    ("facebook/opt-1.3b", "local_models/opt-1.3b"),
    ("BAAI/bge-reranker-large", "local_models/reranker/BAAI_bge-reranker-large"),
]:
    print(f"⬇️  {repo} → {path}")
    snapshot_download(repo_id=repo, local_dir=path, token=token, resume_download=True)
PYCODE

else
  echo "⚠️  HF_API_TOKEN not set; skipping model downloads."
fi

# ─────────────────────────────────────────────────────────────────────────────
# 11. Python requirements
pip install -r requirements.txt --use-deprecated=legacy-resolver

echo "✔️  Setup complete! Activate with: source .venv/bin/activate"
