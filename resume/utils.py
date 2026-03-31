import json
import re
from pathlib import Path

from models import AppConfig, ResumeData


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
    for key, value in cfg.model_dump().items():
        pth = Path(value)
        if not pth.is_file():
            raise FileNotFoundError(f"Missing file for config key '{key}': {pth}")
    return cfg


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use in filenames."""
    if not name:
        return ""
    # Replace spaces and special characters with underscores, keep alphanumeric
    sanitized = re.sub(r"[^\w\s-]", "", name)
    sanitized = re.sub(r"[-\s]+", "_", sanitized)
    return sanitized.lower().strip("_")


def load_candidate_data(candidate_json_path: str | Path) -> ResumeData:
    """Load and validate candidate data from JSON file using ResumeData model."""
    try:
        with open(candidate_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return ResumeData(**data)
    except FileNotFoundError:
        print(f"Error: Candidate JSON file not found at {candidate_json_path}")
        raise
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in candidate file: {e}")
        raise
    except Exception as e:
        print(f"Error: Invalid candidate data structure: {e}")
        print("Expected format matches ResumeData schema (profile, skills, projects, experiences)")
        raise
