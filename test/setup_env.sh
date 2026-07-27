#!/bin/bash
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

# =============================================================================
# Image Build Manager — Test Environment Setup
# =============================================================================
# One-time setup script. Creates a Python virtual environment, installs all
# dependencies, and prints the exact steps to configure and run tests.
#
# Usage:
#   bash setup_env.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
REQUIREMENTS="${SCRIPT_DIR}/requirements.txt"

echo ""
echo "================================================================="
echo "  Image Build Manager — Test Environment Setup"
echo "================================================================="
echo ""

# -----------------------------------------------
# Step 1: Check Python 3.12+
# -----------------------------------------------
PYTHON_CMD=""
for cmd in python3.12 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+')
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 12 ]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "  [ERROR] Python 3.12+ is required but not found."
    echo "          Install: dnf install python3.12 python3.12-pip"
    exit 1
fi

echo "  [OK] Python: $($PYTHON_CMD --version)"

# -----------------------------------------------
# Step 2: Create virtual environment
# -----------------------------------------------
if [ -d "$VENV_DIR" ]; then
    echo "  [OK] Virtual environment already exists: .venv/"
else
    echo "  [...] Creating virtual environment: .venv/"
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    echo "  [OK] Virtual environment created"
fi

# -----------------------------------------------
# Step 3: Activate and install dependencies
# -----------------------------------------------
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

echo "  [...] Upgrading pip"
pip install --upgrade pip --quiet

echo "  [...] Installing dependencies from requirements.txt"
pip install -r "$REQUIREMENTS" --quiet

# pytest-order for test ordering
if ! pip show pytest-order &>/dev/null; then
    echo "  [...] Installing pytest-order"
    pip install pytest-order --quiet
fi

echo "  [OK] All dependencies installed"

echo ""
echo "================================================================="
echo "  Environment Ready — Follow the steps below"
echo "================================================================="
echo ""
echo "  STEP 1: Activate the virtual environment"
echo "  ─────────────────────────────────────────"
echo "    source .venv/bin/activate"
echo ""
echo "  STEP 2: Configure target server"
echo "  ────────────────────────────────"
echo "    Edit test_config.yml:"
echo ""
echo "    LOCAL MODE (running on the target server itself):"
echo "      oim_server_ip: \"\"          ← leave empty (default)"
echo "      No other connection settings needed."
echo ""
echo "    REMOTE MODE (running against a remote OIM server):"
echo "      oim_server_ip: \"<IP>\"      ← MANDATORY: IP of the OIM server"
echo "      oim_ssh_user: root          ← SSH user (default: root)"
echo ""
echo "      Optional (only if repo is not already on the target):"
echo "        clone_url:  \"<git_url>\"  ← Git URL to clone on target"
echo "        clone_path: \"/root/...\"  ← Where to clone on target"
echo ""
echo "    vi test_config.yml"
echo ""
echo "  STEP 3: Configure SSH credentials (REMOTE MODE only)"
echo "  ─────────────────────────────────────────────────────"
echo "    Only needed when oim_server_ip is set."
echo ""
echo "    Edit test_creds.yml and set:"
echo "      oim_password     — SSH password for the OIM server"
echo ""
echo "    vi test_creds.yml"
echo ""
echo "    Note: test_creds.yml is auto-encrypted with Ansible Vault on"
echo "    first run. The vault key is stored in .test_creds.key (gitignored)."
echo "    If using passwordless SSH, set oim_password to any dummy value."
echo ""
echo "  STEP 4: Configure datasets (OPTIONAL)"
echo "  ──────────────────────────────────────"
echo "    Datasets are in: datasets/project_default/input/"
echo ""
echo "    If the target already has the input files deployed:"
echo "      → Set sync_image_build_input: false in test_config.yml"
echo ""
echo "    If you want to push input files from this machine to target:"
echo "      → Set sync_image_build_input: true (default)"
echo "      → Edit the files under datasets/project_default/input/:"
echo "          image_build_config.yml       — Domain input config"
echo "          image_build_credentials.yml  — Vault-encrypted creds"
echo "          repo_manager_output/         — Upstream dependency output"
echo ""
echo "  STEP 5: Run tests"
echo "  ─────────────────"
echo "    # Verify existing deployment (no playbook execution):"
echo "    ./run_validation.sh image_builder verify --marker sanity"
echo ""
echo "    # Deploy + verify a specific tag:"
echo "    ./run_validation.sh image_build_prepare test"
echo ""
echo "    # Run all enabled suites from test_run_config.yml:"
echo "    ./run_validation.sh --config"
echo ""
echo "    # For full usage and examples:"
echo "    ./run_validation.sh --help"
echo ""
echo "  STEP 6: View reports"
echo "  ────────────────────"
echo "    Reports are generated in reports/ after each run."
echo "    Open HTML: python3 -m http.server 8899 --directory reports/"
echo ""
echo "================================================================="
echo ""
