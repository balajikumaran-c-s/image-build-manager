# Copyright 2026 Dell Inc. or its subsidiaries. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Config validation for image_build_manager test framework.

Validates test_config.yml fields: IP format, paths, dataset existence.
"""

import os
import re
from typing import Dict, Any, List

import yaml

IPV4_PATTERN = re.compile(
    r'^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}'
    r'(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$'
)

# Module root: functions/ -> validation/ -> library/ -> test/
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(_THIS_DIR))
)


class ConfigValidationError(Exception):
    """Raised when config validation fails."""


def _validate_ip(value: str, field: str) -> List[str]:
    """Validate IPv4 address format."""
    errors = []
    if value and not IPV4_PATTERN.match(value):
        errors.append(f"{field}: invalid IPv4 format '{value}'")
    return errors


def validate_test_config() -> Dict[str, Any]:
    """Validate test_config.yml.

    Returns:
        Dict with 'valid', 'errors', 'warnings'.
    """
    config_path = os.path.join(_MODULE_ROOT, "test_config.yml")
    errors = []
    warnings = []

    if not os.path.exists(config_path):
        return {
            "valid": False,
            "errors": ["test_config.yml not found"],
            "warnings": [],
        }

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Validate OIM IP (optional — empty means local)
    oim_ip = config.get("oim_server_ip", "")
    if oim_ip:
        errors.extend(_validate_ip(oim_ip, "oim_server_ip"))

    # Validate dataset exists
    dataset = config.get("dataset", "project_default")
    dataset_path = os.path.join(_MODULE_ROOT, "datasets", dataset)
    if not os.path.isdir(dataset_path):
        errors.append(
            f"Dataset directory not found: datasets/{dataset}"
        )

    # Validate dataset input directory
    input_path = os.path.join(dataset_path, "input")
    if os.path.isdir(dataset_path) and not os.path.isdir(input_path):
        errors.append(
            f"Dataset input dir not found: datasets/{dataset}/input/"
        )

    # Validate image_build_config.yml in dataset input
    ib_config = os.path.join(
        input_path, "image_build_config.yml"
    )
    if os.path.isdir(input_path) and not os.path.isfile(ib_config):
        warnings.append(
            "image_build_config.yml not found in dataset input"
        )

    # Validate clone_url
    clone_url = config.get("clone_url", "")
    if clone_url and not (
        clone_url.startswith("http") or clone_url.startswith("git@")
    ):
        warnings.append(
            f"clone_url doesn't look like a valid URL: {clone_url}"
        )

    # Validate clone_path
    clone_path = config.get("clone_path", "")
    if clone_path and not os.path.isabs(clone_path):
        errors.append(
            f"clone_path must be absolute: {clone_path}"
        )


    # Validate shared_path
    shared_path = config.get("shared_path", "")
    if shared_path and not os.path.isabs(shared_path):
        errors.append(
            f"shared_path must be absolute: {shared_path}"
        )

    # Validate report_path
    report_path = config.get("report_path", "")
    if report_path and " " in report_path:
        errors.append("report_path must not contain spaces")

    # Validate report_name
    report_name = config.get("report_name", "")
    if report_name and not re.match(
        r'^[a-zA-Z0-9_-]+$', report_name
    ):
        errors.append(
            "report_name must contain only letters, numbers, "
            "underscores, hyphens"
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def validate_all() -> Dict[str, Any]:
    """Run all validation checks.

    Returns:
        Dict with 'valid', 'errors', 'warnings'.

    Raises:
        ConfigValidationError if validation fails.
    """
    result = validate_test_config()

    if not result["valid"]:
        errors = "\n".join(f"  - {err}" for err in result["errors"])
        msg = f"Config validation failed:\n{errors}"
        raise ConfigValidationError(msg)

    return result
