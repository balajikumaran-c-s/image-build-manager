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

if [ -d "/host_ssh" ] && [ -f "/host_ssh/id_rsa" ]; then
    echo "[SSH] Found mounted host SSH keys at /host_ssh — copying..."
    cp /host_ssh/id_rsa "$SSH_DIR/id_rsa" 2>/dev/null || true
    cp /host_ssh/id_rsa.pub "$SSH_DIR/id_rsa.pub" 2>/dev/null || true
    cp /host_ssh/authorized_keys "$SSH_DIR/authorized_keys" 2>/dev/null || true
    cp /host_ssh/known_hosts "$SSH_DIR/known_hosts" 2>/dev/null || true
    # Also copy any config file
    cp /host_ssh/config "$SSH_DIR/config" 2>/dev/null || true
    chmod 600 "$SSH_DIR/id_rsa" 2>/dev/null || true
    chmod 644 "$SSH_DIR/id_rsa.pub" 2>/dev/null || true
    chmod 600 "$SSH_DIR/authorized_keys" 2>/dev/null || true
    echo "[SSH] Host SSH keys imported successfully."
elif [ ! -f "$SSH_DIR/id_rsa" ]; then
    echo "[SSH] No host SSH keys mounted. Generating new key pair..."
    ssh-keygen -t rsa -b 4096 -C "image_build_runner" -q -N '' -f "$SSH_DIR/id_rsa"
    echo ""
    echo "========================================================"
    echo " ACTION REQUIRED: Copy this public key to the build host"
    echo "========================================================"
    echo ""
    cat "$SSH_DIR/id_rsa.pub"
    echo ""
    echo "Run on the host:"
    echo "  cat >> /root/.ssh/authorized_keys << 'EOF'"
    cat "$SSH_DIR/id_rsa.pub"
    echo "EOF"
    echo ""
    echo "Or mount host SSH keys when starting the container:"
    echo "  podman run -d ... -v /root/.ssh:/host_ssh:ro ..."
    echo "========================================================"
fi

# Add host to known_hosts (suppress host key checking for first connect)
ADMIN_IP="${ADMIN_NIC_IP:-}"
if [ -n "$ADMIN_IP" ]; then
    ssh-keyscan "$ADMIN_IP" >> "$SSH_DIR/known_hosts" 2>/dev/null || true
    echo "[SSH] Added $ADMIN_IP to known_hosts."
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
