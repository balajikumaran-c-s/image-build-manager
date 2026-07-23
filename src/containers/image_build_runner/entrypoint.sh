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
