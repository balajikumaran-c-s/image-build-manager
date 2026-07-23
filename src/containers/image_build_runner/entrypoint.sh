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

# entrypoint.sh — Keeps container alive (same pattern as omnia_core)
# The container starts sshd and then waits indefinitely.
# Users run playbooks via: podman exec -it <cid> ansible-playbook image_build_manager.yml --tags <tag>

mkdir -p /image_build_manager/log

# ---------------------------------------------------------------------------
# SSH Key Setup — enables container → host SSH (same pattern as omnia_core)
# ---------------------------------------------------------------------------
# If host SSH keys are mounted at /host_ssh (via -v /root/.ssh:/host_ssh:ro),
# copy them into the container's /root/.ssh for passwordless SSH to the host.
# Otherwise, generate a new key pair and print instructions.
# ---------------------------------------------------------------------------
SSH_DIR="/root/.ssh"
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

if [ -d "/host_ssh" ]; then
    echo "[SSH] Found mounted host SSH keys at /host_ssh — copying all keys..."
    # Copy ALL files from /host_ssh into container's .ssh
    # This handles id_rsa, id_ed25519, oim_rsa, or any key the host uses.
    for f in /host_ssh/*; do
        [ -f "$f" ] || continue
        fname=$(basename "$f")
        cp "$f" "$SSH_DIR/$fname" 2>/dev/null || true
    done
    # Fix permissions: private keys 600, public keys / config 644
    for key in "$SSH_DIR"/id_* "$SSH_DIR"/oim_rsa "$SSH_DIR"/*_key; do
        [ -f "$key" ] || continue
        case "$key" in
            *.pub) chmod 644 "$key" 2>/dev/null || true ;;
            *)     chmod 600 "$key" 2>/dev/null || true ;;
        esac
    done
    chmod 600 "$SSH_DIR/authorized_keys" 2>/dev/null || true
    chmod 644 "$SSH_DIR/config" 2>/dev/null || true
    chmod 644 "$SSH_DIR/known_hosts" 2>/dev/null || true
    # Use oim_rsa as default identity if id_rsa doesn't exist
    if [ ! -f "$SSH_DIR/id_rsa" ] && [ -f "$SSH_DIR/oim_rsa" ]; then
        cp "$SSH_DIR/oim_rsa" "$SSH_DIR/id_rsa"
        cp "$SSH_DIR/oim_rsa.pub" "$SSH_DIR/id_rsa.pub" 2>/dev/null || true
        chmod 600 "$SSH_DIR/id_rsa"
        echo "[SSH] Copied oim_rsa → id_rsa as default identity."
    fi
    echo "[SSH] Host SSH keys imported successfully."
    ls -la "$SSH_DIR/" 2>/dev/null
else
    echo "[SSH] No host SSH keys mounted at /host_ssh."
    if [ ! -f "$SSH_DIR/id_rsa" ]; then
        echo "[SSH] Generating new key pair..."
        ssh-keygen -t rsa -b 4096 -C "image_build_runner" -q -N '' -f "$SSH_DIR/id_rsa"
        echo ""
        echo "========================================================"
        echo " ACTION REQUIRED: Copy this public key to the build host"
        echo "========================================================"
        cat "$SSH_DIR/id_rsa.pub"
        echo ""
        echo "Or mount host SSH keys:"
        echo "  podman run -d ... -v /root/.ssh:/host_ssh:ro ..."
        echo "========================================================"
    fi
fi

# Read admin_nic_ip from config.yml if ADMIN_NIC_IP env not set
ADMIN_IP="${ADMIN_NIC_IP:-}"
if [ -z "$ADMIN_IP" ] && [ -f "/image_build_manager/config.yml" ]; then
    ADMIN_IP=$(grep -A5 'build_host:' /image_build_manager/config.yml | grep 'admin_nic_ip' | head -1 | awk -F'"' '{print $2}' | tr -d ' ')
fi

# Add host to known_hosts and disable strict checking
if [ -n "$ADMIN_IP" ]; then
    ssh-keyscan "$ADMIN_IP" >> "$SSH_DIR/known_hosts" 2>/dev/null || true
    echo "[SSH] Added $ADMIN_IP to known_hosts."
fi
# Disable strict host key checking to avoid first-connect prompts
if ! grep -q 'StrictHostKeyChecking' "$SSH_DIR/config" 2>/dev/null; then
    echo -e "\nHost *\n    StrictHostKeyChecking no\n    UserKnownHostsFile /dev/null" >> "$SSH_DIR/config"
    chmod 644 "$SSH_DIR/config"
fi

# Start sshd
/usr/sbin/sshd 2>/dev/null || true

echo "============================================"
echo " image_build_manager container ready"
echo " SSH port: ${SSH_PORT:-2230}"
echo "============================================"
echo ""
echo "Run playbooks via:"
echo "  podman exec -it <container> ansible-playbook image_build_manager.yml --tags validate"
echo "  podman exec -it <container> ansible-playbook image_build_manager.yml --tags prepare"
echo "  podman exec -it <container> ansible-playbook image_build_manager.yml --tags build"
echo "  podman exec -it <container> ansible-playbook image_build_manager.yml --tags cleanup"
echo ""
echo "Or open a shell:"
echo "  podman exec -it <container> bash"
echo ""

exec tail -f /dev/null
