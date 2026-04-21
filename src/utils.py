import json
import logging
import os
import re
from pathlib import Path
from uuid import uuid4

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from models import AppConfig, CandidateProfile

logger = logging.getLogger(__name__)


def save_output_file(filename: str, data: bytes, prefix: str) -> str:
    """
    Save a file to Azure Blob Storage and return the blob name.
    Requires AZURE_STORAGE_ACCOUNT_NAME to be set.
    """
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    container_name = "outputs"
    blob_name = f"{uuid4()}-{filename}"

    credential = DefaultAzureCredential()
    account_url = f"https://{account_name}.blob.core.windows.net"
    blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)

    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    blob_client.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type="application/pdf"),
    )

    return blob_name


def load_app_config(config_file: str) -> AppConfig:
    """Load and parse the app config JSON.

    Assumptions:
    - `config_file` is relative to the current working directory.
    - All values inside the JSON are relative to the current working directory.
    """
    cfg_path = Path(config_file)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")
    with open(cfg_path, encoding="utf-8") as f:
        raw = json.load(f)
    return AppConfig.model_validate(raw)


def validate_app_config(config_file: str) -> AppConfig:
    """Load config JSON and verify all configured files exist."""
    cfg = load_app_config(config_file)
    for key in AppConfig.model_fields:
        value = getattr(cfg, key)
        if isinstance(value, Path) and not value.is_file():
            raise FileNotFoundError(f"Missing file for config key '{key}': {value}")
    return cfg


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use in filenames."""
    if not name:
        return ""
    sanitized = re.sub(r"[^\w\s-]", "", name)
    sanitized = re.sub(r"[-\s]+", "_", sanitized)
    return sanitized.lower().strip("_")


def load_candidate_data(candidate_json_path: str | Path) -> CandidateProfile:
    """Load and validate candidate profile JSON."""
    try:
        with open(candidate_json_path, encoding="utf-8") as f:
            data = json.load(f)
            return CandidateProfile.model_validate(data)
    except FileNotFoundError:
        logger.error(f"Candidate JSON file not found at {candidate_json_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in candidate file: {e}")
        raise
    except Exception as e:
        logger.error(f"Invalid candidate data structure: {e}")
        raise