#!/usr/bin/env bash
set -euo pipefail

sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring.gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/cuda-archive-keyring.gpg
echo "deb [signed-by=/etc/apt/keyrings/cuda-archive-keyring.gpg] \
  https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/ /" \
  | sudo tee /etc/apt/sources.list.d/cuda.list

# Add Google Chrome repo
curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
  | sudo gpg --dearmor -o /etc/apt/keyrings/google-linux-signing-keyring.gpg
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-linux-signing-keyring.gpg] \
  http://dl.google.com/linux/chrome/deb/ stable main" \
  | sudo tee /etc/apt/sources.list.d/google-chrome.list

# Add PostgreSQL 17 (if you really need it)
curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
  | sudo gpg --dearmor -o /etc/apt/keyrings/pgdg-keyring.gpg
echo "deb [signed-by=/etc/apt/keyrings/pgdg-keyring.gpg] \
  http://apt.postgresql.org/pub/repos/apt/ noble-pgdg main" \
  | sudo tee /etc/apt/sources.list.d/pgdg.list

# 1. System update & core dependencies
sudo apt update && sudo apt -y upgrade
# 2. Install every package listed in apt-manual.txt
xargs -a apt-manual.txt sudo apt install -y

# 2. Ollama model pulls
if ! command -v ollama &>/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
ollama pull llama3.2
ollama pull gemma3
ollama pull nomic-embed-text

# 3. Docker Redis
docker pull redis:7.2.3-alpine

# 4. Python 3.11 virtualenv setup
python3.11 -m venv .venv
# shellcheck source=/dev/null
source .venv/bin/activate

# 5. Hugging Face authentication & model downloads
pip install --upgrade pip setuptools wheel
pip install huggingface_hub

if [ -z "${HF_API_TOKEN:-}" ]; then
  echo "⚠️  HF_API_TOKEN not set; skipping Hugging Face model downloads."
else
  huggingface-cli login --token "$HF_API_TOKEN"

  echo "⏬ Downloading local_models…"

  python3 - <<'PYCODE'
import os
from huggingface_hub import snapshot_download

token = os.getenv("HF_API_TOKEN")

# 5.1 ColSmol-256M
print("⬇️  vidore/colSmol-256M → local_models/colSmol-256M")
snapshot_download(
    repo_id="vidore/colSmol-256M",
    local_dir="local_models/colSmol-256M",
    token=token,
    resume_download=True
)

# 5.2 ColQwen2.5 (adapter + base) — equivalent to download_colpali_full.py :contentReference[oaicite:0]{index=0}
print("⬇️  tsystems/colqwen2.5-3b-multilingual-v1.0 → local_models/colqwen2.5-3b-multilingual-v1.0")
snapshot_download(
    repo_id="tsystems/colqwen2.5-3b-multilingual-v1.0",
    local_dir="local_models/colqwen2.5-3b-multilingual-v1.0",
    token=token,
    resume_download=True
)

# 5.3 OPT-1.3B base model
print("⬇️  facebook/opt-1.3b → local_models/opt-1.3b")
snapshot_download(
    repo_id="facebook/opt-1.3b",
    local_dir="local_models/opt-1.3b",
    token=token,
    resume_download=True
)

# 5.4 BGE Reranker — equivalent to download_reranker.py :contentReference[oaicite:1]{index=1}
print("⬇️  BAAI/bge-reranker-large → local_models/reranker/BAAI_bge-reranker-large")
snapshot_download(
    repo_id="BAAI/bge-reranker-large",
    local_dir="local_models/reranker/BAAI_bge-reranker-large",
    token=token,
    resume_download=True
)
PYCODE

fi

# 6. Install Python dependencies
pip install -r requirements.txt --use-deprecated=legacy-resolver

echo "✔️  Setup complete!  Activate with: source .venv/bin/activate"
