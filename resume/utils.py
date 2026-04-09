import json
import re
from pathlib import Path

from models import AppConfig, CandidateProfile


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
        print(f"Error: Candidate JSON file not found at {candidate_json_path}")
        raise
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in candidate file: {e}")
        raise
    except Exception as e:
        print(f"Error: Invalid candidate data structure: {e}")
        print("Expected format matches CandidateProfile schema.")
        raise