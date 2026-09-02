import json
import re
from pathlib import Path
from typing import Optional
from uuid import uuid4


def build_blob_object_name(filename: str) -> str:
    sanitized_name = Path(filename).name
    if not sanitized_name:
        raise ValueError("filename must not be empty")
    return f"{uuid4().hex}_{sanitized_name}"


def parse_json_param(param_value: Optional[str], param_name: str) -> Optional[dict]:
    if not param_value or param_value.strip() == "":
        return None
    try:
        return json.loads(param_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {param_name} parameter") from exc


def parse_int_param(param_value: Optional[str], param_name: str) -> Optional[int]:
    if not param_value or param_value.strip() == "":
        return None
    try:
        return int(param_value)
    except ValueError as exc:
        raise ValueError(f"Invalid integer in {param_name} parameter") from exc


def parse_distributors_param(param_value: Optional[str]) -> list[str]:
    distributors = parse_json_param(param_value, "distributors")
    if not distributors:
        raise ValueError("Please provide the distributors in the request body.")
    if not isinstance(distributors, list) or not all(isinstance(item, str) for item in distributors):
        raise ValueError("Distributors must be a JSON array of strings.")
    return distributors


def validate_object_id_param(param_value: Optional[str], param_name: str) -> str:
    if not param_value:
        raise ValueError(f"Please provide the {param_name}.")
    if not re.fullmatch(r"[0-9a-fA-F]{24}", param_value):
        raise ValueError(f"Invalid {param_name}.")
    return param_value
