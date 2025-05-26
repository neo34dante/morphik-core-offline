import os

# Absolute path to your local_models folder
LOCAL_MODEL_ROOT = os.path.abspath(
    os.getenv("MORPHIK_LOCAL_MODELS", "local_models")
)

def local_model_path(repo_id: str) -> str:
    """
    Given a HF repo_id like "vidore/colSmol-256M", returns:
       "<project_root>/local_models/colSmol-256M"
    """
    # take the part after the last slash
    name = repo_id.split("/")[-1]
    return os.path.join(LOCAL_MODEL_ROOT, name)
