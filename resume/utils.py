import json
import logging
import re
from pathlib import Path

from models import AppConfig, CandidateProfile

logger = logging.getLogger(__name__)


def save_output_file(filename: str, data: bytes, prefix: str) -> Path:
    """
    Save a file to output storage, first removing any existing files with the same prefix.
    Returns the path of the saved file.

    Swap this implementation for Blob Storage when moving to Azure.
    """
    output_dir = Path("static/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_file in output_dir.glob(f"{prefix}*"):
        old_file.unlink()
    path = output_dir / filename
    path.write_bytes(data)
    return path


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