import re
import json
from models import ResumeData


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use in filenames."""
    if not name:
        return ""
    # Replace spaces and special characters with underscores, keep alphanumeric
    sanitized = re.sub(r'[^\w\s-]', '', name)
    sanitized = re.sub(r'[-\s]+', '_', sanitized)
    return sanitized.lower().strip('_')


def load_candidate_data(candidate_json_path: str) -> ResumeData:
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

