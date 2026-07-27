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
Testinfra host, configuration, and remote clone/sync utilities.

Handles:
- test_config.yml and test_creds.yml loading
- Ansible Vault encryption for credentials
- Testinfra host connection (local or remote SSH)
- Remote repo clone and dataset sync
- Local vs remote execution detection
"""

import os
import subprocess
import tempfile
from typing import Dict, Any

import yaml
import testinfra

from ..vars.common_vars import (
    MODULE_ROOT,
    TEST_CONFIG_FILE,
    TEST_CREDENTIALS_FILE,
    TEST_CREDENTIALS_KEY,
    DEFAULT_CLONE_URL,
    DEFAULT_CLONE_PATH,
    SSH_OPTS,
)


def get_module_root() -> str:
    """Get the module root directory (test/)."""
    return MODULE_ROOT


# =============================================================================
# CONFIG LOADING
# =============================================================================

def _get_config_path() -> str:
    """Get the test_config.yml path."""
    return os.path.join(MODULE_ROOT, TEST_CONFIG_FILE)


def _get_credentials_paths() -> tuple:
    """Get credentials file and key file paths."""
    creds_path = os.path.join(MODULE_ROOT, TEST_CREDENTIALS_FILE)
    key_path = os.path.join(MODULE_ROOT, TEST_CREDENTIALS_KEY)
    return creds_path, key_path


def load_test_config() -> Dict[str, Any]:
    """Load test configuration from test_config.yml.

    Returns:
        Dict containing the configuration.
    """
    config_path = _get_config_path()
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


# =============================================================================
# VAULT ENCRYPTION
# =============================================================================

def _is_vault_encrypted(file_path: str) -> bool:
    """Check if file is ansible-vault encrypted."""
    if not os.path.exists(file_path):
        return False
    with open(file_path, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()
    return first_line.startswith("$ANSIBLE_VAULT")


def _create_vault_key(key_path: str) -> None:
    """Create a new vault key file with random 32-char password."""
    import secrets
    key = secrets.token_urlsafe(32)[:32]
    with open(key_path, "w", encoding="utf-8") as f:
        f.write(key)
    os.chmod(key_path, 0o600)


def _decrypt_vault_file(config_path: str, key_path: str) -> Dict:
    """Decrypt ansible-vault encrypted file and return as dict."""
    try:
        result = subprocess.run(
            [
                "ansible-vault", "view", config_path,
                "--vault-password-file", key_path,
            ],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return yaml.safe_load(result.stdout) or {}
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            f"Failed to decrypt {config_path}: {exc.stderr}"
        ) from exc
    except FileNotFoundError:
        raise ValueError(
            "ansible-vault not found. Install ansible."
        ) from None


def _encrypt_vault_file(config_path: str, key_path: str) -> bool:
    """Encrypt file with ansible-vault."""
    try:
        subprocess.run(
            [
                "ansible-vault", "encrypt", config_path,
                "--vault-password-file", key_path,
            ],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return True
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            f"Failed to encrypt {config_path}: {exc.stderr}"
        ) from exc
    except FileNotFoundError:
        raise ValueError(
            "ansible-vault not found. Install ansible."
        ) from None


def load_test_credentials() -> Dict[str, Any]:
    """Load test credentials with automatic vault encryption.

    Behavior:
    - Encrypted + key exists: decrypt and return
    - Encrypted + key missing: raise error
    - Plain: read, create key, encrypt, return
    - Not found: return empty dict
    """
    creds_path, key_path = _get_credentials_paths()

    if not os.path.exists(creds_path):
        return {}

    if _is_vault_encrypted(creds_path):
        if os.path.exists(key_path):
            return _decrypt_vault_file(creds_path, key_path)
        raise ValueError(
            f"Credentials encrypted but key not found: {key_path}"
        )

    with open(creds_path, "r", encoding="utf-8") as f:
        creds = yaml.safe_load(f) or {}

    if not os.path.exists(key_path):
        _create_vault_key(key_path)

    _encrypt_vault_file(creds_path, key_path)
    return creds


def encrypt_test_credentials() -> bool:
    """Encrypt test_creds.yml if not already encrypted."""
    creds_path, key_path = _get_credentials_paths()

    if not os.path.exists(creds_path):
        return False
    if _is_vault_encrypted(creds_path):
        return True
    if not os.path.exists(key_path):
        _create_vault_key(key_path)

    _encrypt_vault_file(creds_path, key_path)
    return True


# =============================================================================
# LOCAL / REMOTE DETECTION
# =============================================================================

def _is_local_ip(ip: str) -> bool:
    """Check if IP belongs to this machine."""
    if ip in ("localhost", "127.0.0.1", ""):
        return True
    try:
        result = subprocess.run(
            ["hostname", "-I"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        return ip in result.stdout.strip().split()
    except (OSError, subprocess.SubprocessError):
        return False


def is_local_execution() -> bool:
    """Determine if tests run locally on the target host.

    Returns True when:
    - oim_server_ip is empty/not set
    - oim_server_ip matches a local IP address
    """
    config = load_test_config()
    oim_ip = config.get("oim_server_ip", "").strip()
    if not oim_ip:
        return True
    return _is_local_ip(oim_ip)


# =============================================================================
# TESTINFRA HOST CONNECTION
# =============================================================================

def get_testinfra_host():
    """Get testinfra host connected to the target server.

    When oim_server_ip is empty or local, runs in local mode.
    When oim_server_ip is remote, connects via SSH.

    Returns:
        testinfra Host object.
    """
    config = load_test_config()
    credentials = load_test_credentials()
    oim_ip = config.get("oim_server_ip", "").strip()

    # Local execution
    if not oim_ip or _is_local_ip(oim_ip):
        return testinfra.get_host("local://")

    # Remote — SSH
    ssh_user = config.get("oim_ssh_user", "root")
    ssh_port = config.get("oim_ssh_port", 22)
    ssh_password = credentials.get("oim_password", "")

    inventory_dir = os.path.join(
        tempfile.gettempdir(), "ibm_testinfra"
    )
    os.makedirs(inventory_dir, exist_ok=True)
    inventory_path = os.path.join(inventory_dir, "inventory.ini")

    ssh_args = (
        "-o StrictHostKeyChecking=no "
        "-o UserKnownHostsFile=/dev/null"
    )

    with open(inventory_path, "w", encoding="utf-8") as f:
        f.write("[all]\n")
        f.write(
            f"target ansible_host={oim_ip} "
            f"ansible_user={ssh_user} "
            f"ansible_port={ssh_port} "
            f"ansible_ssh_pass={ssh_password} "
            f"ansible_connection=ssh "
            f"ansible_ssh_common_args='{ssh_args}'\n"
        )

    return testinfra.get_host(
        "ansible://target", ansible_inventory=inventory_path
    )


def run_on_host(host, cmd: str):
    """Run command on the target host (OIM server).

    Args:
        host: Testinfra host object
        cmd: Command to execute

    Returns:
        Result with stdout, stderr, rc attributes.
    """
    return host.run(cmd)


# =============================================================================
# REMOTE CLONE AND DATASET SYNC
# =============================================================================

def clone_repo_on_remote(host) -> Dict[str, Any]:
    """Clone the image-build-manager repo on the remote target.

    Reads clone_url, clone_path, force_clone from test_config.yml.

    Returns:
        Dict with 'success', 'details', 'error'.
    """
    config = load_test_config()
    clone_url = config.get("clone_url", DEFAULT_CLONE_URL)
    clone_path = config.get("clone_path", DEFAULT_CLONE_PATH)
    force_clone = config.get("force_clone", False)

    result = {"success": False, "details": "", "error": ""}

    # Check if repo already exists
    check = host.run(f"test -d {clone_path}/.git && echo YES || echo NO")
    repo_exists = check.rc == 0 and "YES" in check.stdout

    if repo_exists and force_clone:
        rm_cmd = host.run(f"rm -rf {clone_path}")
        if rm_cmd.rc != 0:
            result["error"] = (
                f"Failed to remove {clone_path}: {rm_cmd.stderr}"
            )
            return result
        repo_exists = False

    if not repo_exists:
        clone_cmd = host.run(
            f"git clone {clone_url} {clone_path} 2>&1"
        )
        if clone_cmd.rc != 0:
            result["error"] = (
                f"git clone failed: {clone_cmd.stdout}"
            )
            return result
        result["details"] = f"Cloned {clone_url} to {clone_path}"
    else:
        # Pull latest
        host.run(
            f"cd {clone_path} && git pull 2>&1"
        )
        result["details"] = (
            f"Repo exists at {clone_path}, pulled latest"
        )

    result["success"] = True
    return result


def sync_image_build_input(host) -> Dict[str, Any]:  # pylint: disable=unused-argument
    """Push image_build input files from local dataset to target.

    Syncs: test/datasets/<dataset>/input/
        -> <clone_path>/src/input/<project_name>/

    Returns:
        Dict with 'success', 'details', 'error'.
    """
    config = load_test_config()
    dataset = config.get("dataset", "project_default")
    clone_path = config.get("clone_path", DEFAULT_CLONE_PATH)
    project_name = config.get("project_name", "project_default")
    oim_ip = config.get("oim_server_ip", "").strip()
    ssh_user = config.get("oim_ssh_user", "root")

    result = {"success": False, "details": "", "error": ""}

    local_input = os.path.join(
        MODULE_ROOT, "datasets", dataset, "input"
    )
    if not os.path.isdir(local_input):
        result["error"] = f"Dataset input not found: {local_input}"
        return result

    remote_input = (
        f"{clone_path}/src/input/{project_name}/"
    )

    if is_local_execution():
        rsync_result = subprocess.run(
            [
                "rsync", "-avz",
                f"{local_input}/",
                remote_input,
            ],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if rsync_result.returncode != 0:
            result["error"] = (
                f"rsync failed: {rsync_result.stderr}"
            )
            return result
    else:
        rsync_result = subprocess.run(
            [
                "rsync", "-avz",
                "-e", f"ssh {SSH_OPTS}",
                f"{local_input}/",
                f"{ssh_user}@{oim_ip}:{remote_input}",
            ],
            capture_output=True, text=True, timeout=120, check=False,
        )
        if rsync_result.returncode != 0:
            result["error"] = (
                f"rsync to remote failed: {rsync_result.stderr}"
            )
            return result

    result["success"] = True
    result["details"] = (
        f"Synced input {local_input} -> {remote_input}"
    )
    return result


def sync_config_to_remote(host) -> Dict[str, Any]:  # pylint: disable=unused-argument
    """Sync config.yml from dataset to remote clone root.

    Returns:
        Dict with 'success', 'details', 'error'.
    """
    config = load_test_config()
    dataset = config.get("dataset", "project_default")
    clone_path = config.get("clone_path", DEFAULT_CLONE_PATH)
    oim_ip = config.get("oim_server_ip", "").strip()
    ssh_user = config.get("oim_ssh_user", "root")

    result = {"success": False, "details": "", "error": ""}

    local_config = os.path.join(
        MODULE_ROOT, "datasets", dataset, "config.yml"
    )
    if not os.path.isfile(local_config):
        result["error"] = (
            f"config.yml not found in dataset: {dataset}"
        )
        return result

    remote_config = f"{clone_path}/config.yml"

    if is_local_execution():
        cp_result = subprocess.run(
            ["cp", local_config, remote_config],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if cp_result.returncode != 0:
            result["error"] = f"cp failed: {cp_result.stderr}"
            return result
    else:
        scp_result = subprocess.run(
            [
                "scp", *SSH_OPTS.split(),
                local_config,
                f"{ssh_user}@{oim_ip}:{remote_config}",
            ],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if scp_result.returncode != 0:
            result["error"] = (
                f"scp to remote failed: {scp_result.stderr}"
            )
            return result

    result["success"] = True
    result["details"] = f"Synced config.yml -> {remote_config}"
    return result
