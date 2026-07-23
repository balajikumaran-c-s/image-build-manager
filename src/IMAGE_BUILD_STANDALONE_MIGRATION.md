# Image Build Manager — Standalone Migration Plan

## Status: DRAFT
## Reference: [STANDALONE_REPO_DESIGN.md](STANDALONE_REPO_DESIGN.md) v3

This document provides a **step-by-step migration plan** to make `image_build_manager`
work as a standalone repository that operates without the Omnia core container.

---

## Migration Overview

```
CURRENT STATE                              TARGET STATE
────────────                               ────────────
  src/image_build_manager/                   image-build-manager/          (standalone repo)
  ├── Runs inside omnia_core container       ├── Mode A: bare-metal (Ansible+Python)
  ├── Reads /opt/omnia/.data/oim_metadata    ├── Mode B: per-domain container (optional)
  ├── Reads /opt/omnia/input/default.yml     ├── Mode C: Omnia mono-repo (backward compat)
  ├── Depends on repo_manager output         ├── config.yml replaces OIM metadata
  ├── Registers in omnia.target              ├── User-provided repo_status.yml (same format)
  └── 62 hardcoded /opt/omnia/ refs          └── Zero hard dependency on /opt/omnia/
```

---

## Phase 0: Pre-Migration Validation (Current Sprint)

**Goal**: Confirm the domain is already self-contained for code dependencies.

| # | Check | Command / Method | Expected Result | Status |
|---|-------|-----------------|-----------------|--------|
| 1 | Zero `../common/` references in tasks | `grep -r '\.\./common/' roles/ playbooks/ --include='*.yml'` | 0 matches | ✅ Done |
| 2 | Zero `../playbooks/utils/` references | `grep -r '\.\./playbooks/utils/' roles/ playbooks/ --include='*.yml'` | 0 matches | ✅ Done |
| 3 | All modules local in `library/modules/` | `ls library/modules/` | 5 .py files | ✅ Done |
| 4 | All module_utils local in `library/module_utils/` | `ls library/module_utils/` | build_image/ + image_build_validation/ | ✅ Done |
| 5 | `ansible.cfg` uses local paths only | Read `ansible.cfg` lines 12-15 | `roles_path = roles`, `library = library/modules` | ✅ Done |
| 6 | Callback plugins local | `ls callback_plugins/` | omnia_default.py | ✅ Done |
| 7 | Credential flow self-contained | Role `collect_build_credentials/` exists with own tasks/vars | Present | ✅ Done |
| 8 | Validation flow self-contained | Role `validate_image_build_input/` + module `validate_image_build_config.py` | Present | ✅ Done |
| 9 | Tag validation in setup role | `grep 'supported_tags' roles/image_build_setup/vars/main.yml` | List of 6 tags | ✅ Done |
| 10 | `common_vars` inlined | `grep 'clone_retry\|file_permissions' roles/image_build_setup/vars/main.yml` | Inlined values | ✅ Done |

---

## Phase 1: Add Standalone Mode to `image_build_setup` Role

**Goal**: Make the setup role detect execution mode and load config from `config.yml` instead of OIM metadata.

### Step 1.1: Add `standalone_mode` Detection

**File**: `roles/image_build_setup/tasks/main.yml`

**What to add** (after tag validation, before upgrade guard):

```yaml
# --- Step 0.5: Detect execution mode ---
- name: Detect standalone mode
  ansible.builtin.set_fact:
    standalone_mode: >-
      {{ standalone_mode | default(false) | bool
         or (lookup('file', playbook_dir + '/../config.yml', errors='ignore')
             | default('') | length > 0
             and not (omnia_input_dir is defined)) }}
    cacheable: true
```

**Detection logic**:
- If `standalone_mode` is explicitly passed via `-e standalone_mode=true` → standalone
- If `config.yml` exists at repo root AND `omnia_input_dir` is NOT defined → standalone
- Otherwise → Omnia mode (existing behavior)

### Step 1.2: Guard Upgrade Check

**File**: `roles/image_build_setup/tasks/main.yml`

**Change**: Wrap existing upgrade guard with `when: not standalone_mode | bool`

```yaml
# BEFORE:
- name: Check upgrade lock file
  ansible.builtin.stat:
    path: "{{ upgrade_lock_path }}"
  register: upgrade_lock

# AFTER:
- name: Check upgrade lock file
  ansible.builtin.stat:
    path: "{{ upgrade_lock_path }}"
  register: upgrade_lock
  when: not standalone_mode | bool

- name: Block playbook while upgrade is in progress
  ansible.builtin.fail:
    msg: "{{ upgrade_in_progress_msg }}"
  when:
    - not standalone_mode | bool
    - upgrade_lock.stat.exists
    - not (upgrade_mode | default(false) | bool)
```

### Step 1.3: Add Standalone Config Loading Branch

**File**: `roles/image_build_setup/tasks/main.yml`

**What to add** (after existing Omnia config loading block):

```yaml
# --- Step 2b: Load standalone config ---
- name: Load standalone config
  when: standalone_mode | bool
  block:
    - name: Include standalone config.yml
      ansible.builtin.include_vars:
        file: "{{ playbook_dir }}/../config.yml"
        name: standalone_config

    - name: Set project dirs from standalone config
      ansible.builtin.set_fact:
        input_project_dir: "{{ standalone_config.input_dir }}/{{ standalone_config.project_name }}"
        output_project_dir: "{{ standalone_config.output_dir }}/{{ standalone_config.project_name }}"
        project_name: "{{ standalone_config.project_name }}"
        cluster_os_type: "{{ standalone_config.cluster_os_type }}"
        cluster_os_version: "{{ standalone_config.cluster_os_version }}"
        admin_nic_ip: "{{ standalone_config.build_host.admin_nic_ip }}"
        cacheable: true

# --- Step 3b: Set build host vars (standalone) ---
- name: Set build host vars from standalone config
  when: standalone_mode | bool
  ansible.builtin.set_fact:
    oim_shared_path: "{{ standalone_config.build_host.shared_path }}"
    oim_node_name: "{{ standalone_config.build_host.hostname }}"
    domain_name: "{{ standalone_config.build_host.domain_name }}"
    admin_nic_ip: "{{ standalone_config.build_host.admin_nic_ip }}"
    cacheable: true
```

### Step 1.4: Guard OIM Metadata Loading

**File**: `roles/image_build_setup/tasks/main.yml`

```yaml
# BEFORE:
- name: Include oim metadata vars
  ansible.builtin.include_vars: "{{ omnia_metadata_file_path }}"

# AFTER:
- name: Include oim metadata vars
  ansible.builtin.include_vars: "{{ omnia_metadata_file_path }}"
  when: not standalone_mode | bool
```

### Step 1.5: Verify — Test Matrix

| Test Case | Command | Expected |
|-----------|---------|----------|
| Standalone + config.yml present | `ansible-playbook image_build_manager.yml` | Loads config.yml, skips upgrade guard |
| Standalone explicit | `ansible-playbook image_build_manager.yml -e standalone_mode=true` | Forces standalone mode |
| Omnia mode (existing) | Run from omnia_core container | Loads OIM metadata, checks upgrade lock |
| Standalone + no config.yml | Remove config.yml, run | Falls back to Omnia mode |

---

## Phase 2: Create Standalone Configuration Files

### Step 2.1: Create `config.yml.sample`

**File**: `config.yml.sample` (new file at repo root)

```yaml
---
# image_build_manager standalone configuration
# Copy this file to config.yml and edit for your environment.

# Project settings
project_name: "my_project"
# input/output paths are auto-derived from src/input/<project_name> and src/output/<project_name>

# Build host settings
build_host:
  hostname: "localhost"            # For cluster naming (standalone always runs locally)
  shared_path: "/opt/image_build"  # Persistent storage for MinIO + Registry data
  domain_name: "local"
  admin_nic_ip: "10.20.0.1"       # Admin NIC IP — Pulp and S3 endpoint

# OS settings
cluster_os_type: "rhel"           # rhel | rocky
cluster_os_version: "10.0"

# Repository settings (replaces repo_status.yml)
repo_source: "direct"             # "direct" | "pulp" | "none"
rpm_repos:
  x86_64:
    baseos: "https://mirror.example.com/rhel/10/baseos/x86_64"
    appstream: "https://mirror.example.com/rhel/10/appstream/x86_64"
  aarch64:
    baseos: "https://mirror.example.com/rhel/10/baseos/aarch64"
    appstream: "https://mirror.example.com/rhel/10/appstream/aarch64"

# S3 settings
s3_configurations:
  provider: "minio"               # minio | powerscale
  endpoint_url: ""                # Auto-detected for minio

# aarch64 build host (optional — leave empty to skip)
aarch64_inventory_host_ip: ""
aarch64_ssh_user: "root"

# Logging
log_dir: "./log"
```

### Step 2.2: Create `requirements.txt`

**File**: `requirements.txt` (new file at repo root)

```
ansible-core>=2.16,<2.18
jsonschema>=4.17
PyYAML>=6.0
jmespath>=1.0
```

### Step 2.3: Create `requirements.yml`

**File**: `requirements.yml` (new file at repo root)

```yaml
---
collections:
  - name: ansible.utils
    version: ">=2.0"
  - name: community.general
    version: ">=7.0"
```

### Step 2.4: Move `samples/config.yml` → Copy from Sample

Copy `config.yml.sample` to `samples/config.yml` so `samples/` has a complete reference.

---

## Phase 3: Guard `omnia.target` and Repo Manager

### Step 3.1: Guard `omnia.target` Registration

**File**: `playbooks/prepare_image_build_manager.yml`

Wrap the entire `omnia.target` block (lines 64-101) with:

```yaml
    - name: Update omnia.target with image_build_manager services
      when: not hostvars['localhost']['standalone_mode'] | default(false) | bool
      block:
        # ... existing omnia.target tasks (lines 66-101) ...
```

### Step 3.2: Guard `omnia.target` Cleanup

**File**: `roles/cleanup_build_artifacts/tasks/cleanup_omnia_target.yml`

Add at top of file:

```yaml
- name: Skip omnia.target cleanup in standalone mode
  ansible.builtin.debug:
    msg: "Standalone mode — skipping omnia.target cleanup"
  when: hostvars['localhost']['standalone_mode'] | default(false) | bool

# Existing tasks wrapped:
- name: Clean omnia.target entries
  when: not hostvars['localhost']['standalone_mode'] | default(false) | bool
  block:
    # ... existing cleanup tasks ...
```

### Step 3.3: Add Standalone RPM Repo Loading to `image_build_manager.yml`

**File**: `image_build_manager.yml` — Step 4

Add a standalone branch **before** the existing repo_status.yml loading:

```yaml
# Step 4 — add at beginning of tasks:
    - name: Build repo lists from standalone config
      when:
        - hostvars['localhost']['standalone_mode'] | default(false) | bool
        - hostvars['localhost']['standalone_config'] is defined
      block:
        - name: Build x86_64 repo list from standalone config
          ansible.builtin.set_fact:
            repo_manager_repos_x86_64: >-
              {{ (hostvars['localhost']['standalone_config'].rpm_repos.x86_64 | default({}))
                 | dict2items
                 | map(attribute='key') | zip(
                   (hostvars['localhost']['standalone_config'].rpm_repos.x86_64 | default({}))
                   | dict2items | map(attribute='value'))
                 | map('community.general.dict_kv', 'name', 'base_url')
                 | list }}
            cacheable: true

        - name: Build aarch64 repo list from standalone config
          ansible.builtin.set_fact:
            repo_manager_repos_aarch64: >-
              {{ (hostvars['localhost']['standalone_config'].rpm_repos.aarch64 | default({}))
                 | dict2items
                 | map(attribute='key') | zip(
                   (hostvars['localhost']['standalone_config'].rpm_repos.aarch64 | default({}))
                   | dict2items | map(attribute='value'))
                 | map('community.general.dict_kv', 'name', 'base_url')
                 | list }}
            cacheable: true

    # Existing repo_status.yml loading — add guard:
    - name: Check if repo_status.yml exists
      ansible.builtin.stat:
        path: "{{ _repo_status_path }}"
      register: repo_status_file
      when: not hostvars['localhost']['standalone_mode'] | default(false) | bool
```

---

## Phase 4: `/opt/omnia/` Path Handling

### Step 4.1: `ansible.cfg` — Environment Variable Override

**No file change needed.** Document the override in README:

```bash
# Standalone: override log path via environment
export ANSIBLE_LOG_PATH=./log/image_build_manager.log
export ANSIBLE_REMOTE_TMP=/tmp/.ansible/tmp
ansible-playbook image_build_manager.yml
```

The `/opt/omnia/` defaults in `ansible.cfg` remain for backward compatibility in mono-repo mode.

### Step 4.2: Role Vars — No Changes Needed

All downstream roles already use the facts-first pattern:

```yaml
oim_shared_path: "{{ hostvars['localhost']['oim_shared_path'] | default('/opt/omnia') }}"
```

Since `image_build_setup` sets `oim_shared_path` from `config.yml → build_host.shared_path`
in standalone mode, downstream roles automatically get the standalone value.
The `/opt/omnia/` default is only a last-resort fallback that never triggers when setup runs.

**Files verified (no changes needed)**:
- `deploy_minio/vars/main.yml` — uses `hostvars['localhost']['oim_shared_path']`
- `deploy_registry/vars/main.yml` — uses `hostvars['localhost']['oim_shared_path']`
- `cleanup_build_artifacts/vars/main.yml` — uses `hostvars['localhost']['oim_shared_path']`
- `build_os_images/vars/main.yml` — uses `hostvars['localhost']['oim_shared_path']`
- `fetch_build_packages/vars/main.yml` — uses `hostvars['localhost']` facts
- `prepare_aarch64_node/vars/main.yml` — uses `hostvars['localhost']` facts

### Step 4.3: `registry_storage_dir` Hardcoded Path

**File**: `roles/cleanup_build_artifacts/vars/main.yml` line 44

```yaml
# CURRENT:
registry_storage_dir: "/opt/omnia/registry/data"

# CHANGE TO:
registry_storage_dir: "{{ oim_shared_path }}/registry/data"
```

This is the **only** downstream var that doesn't use `oim_shared_path` indirection.

---

## Phase 5: Per-Domain Container (Optional Mode B)

### Step 5.1: Create `containers/Containerfile`

**File**: `containers/Containerfile` (new file)

See `STANDALONE_REPO_DESIGN.md` §4.4 for the full Containerfile.
Key points:
- Based on `cgr.dev/chainguard/wolfi-base:latest` (same as `omnia_core`)
- Long-running container with sshd (NOT run-and-exit)
- Entrypoint starts sshd and waits — user runs playbooks via `podman exec`
- Supports running multiple tags without restarting

```dockerfile
# containers/Containerfile — image_build_manager domain runner
# Pattern: Long-running (same as omnia_core — sshd, shell access)
# Usage: podman build -t image_build_runner:1.0 -f containers/Containerfile .
FROM cgr.dev/chainguard/wolfi-base:latest

RUN apk update && apk add --no-cache \
    python-3.12 py3.12-pip git openssh sshpass openssl \
    jq wget rsync curl ca-certificates shadow bash nano

COPY requirements.txt /opt/image_build_manager/requirements.txt
RUN pip install --no-cache-dir -r /opt/image_build_manager/requirements.txt

COPY requirements.yml /opt/image_build_manager/requirements.yml
RUN ansible-galaxy collection install -r /opt/image_build_manager/requirements.yml

RUN sed -i 's/^#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/^#Port 22/Port 2230/' /etc/ssh/sshd_config
EXPOSE 2230
RUN ssh-keygen -A

COPY . /image_build_manager/
WORKDIR /image_build_manager

COPY containers/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV ANSIBLE_LOG_PATH=/image_build_manager/log/image_build_manager.log
ENV ANSIBLE_REMOTE_TMP=/tmp/.ansible/tmp

ENTRYPOINT ["/entrypoint.sh"]
```

### Step 5.2: Create Entrypoint Script

**File**: `containers/entrypoint.sh` (new file)

```bash
#!/bin/bash
# Keeps container alive (same pattern as omnia_core)
/usr/sbin/sshd
echo "image_build_manager container ready"
echo "Run: podman exec -it <cid> ansible-playbook image_build_manager.yml --tags <tag>"
exec tail -f /dev/null
```

### Step 5.3: Container Usage

```bash
# Build
podman build -t image_build_runner:1.0 -f containers/Containerfile .

# Start (long-running — stays alive)
podman run -d --name image_build_mgr --privileged -p 2230:2230 \
    -v ./config.yml:/image_build_manager/config.yml:ro \
    -v ./repo_status.yml:/image_build_manager/repo_status.yml:ro \
    -v ./input:/image_build_manager/input:rw \
    -v ./output:/image_build_manager/output:rw \
    -v /run/podman/podman.sock:/run/podman/podman.sock \
    image_build_runner:1.0

# Run tags (container stays alive between runs)
podman exec -it image_build_mgr ansible-playbook image_build_manager.yml --tags validate
podman exec -it image_build_mgr ansible-playbook image_build_manager.yml --tags prepare
podman exec -it image_build_mgr ansible-playbook image_build_manager.yml --tags build
podman exec -it image_build_mgr ansible-playbook image_build_manager.yml --tags cleanup

# Debug
podman exec -it image_build_mgr bash

# Stop
podman stop image_build_mgr && podman rm image_build_mgr
```

---

## Phase 6: Repository Extraction

### Step 6.1: Create New GitHub Repository

```bash
# Create repo: github.com/dell/image-build-manager
# Branch: main (protected)
# License: Apache 2.0
```

### Step 6.2: Copy Files

```bash
# From omnia mono-repo
cd src/image_build_manager

# Copy everything to new repo root
cp -r . /path/to/image-build-manager/

# Remove omnia-specific leftovers
rm -f /path/to/image-build-manager/IMAGE_BUILD_MIGRATION_PLAN.md  # Internal migration history
```

### Step 6.3: Create `.gitignore`

```gitignore
# User data
input/
output/
log/

# Ansible
*.retry
*.log

# Credentials
.vault_pass
*_credentials_key
*_credentials.yml

# Python
__pycache__/
*.pyc
.venv/

# Config (user-specific)
config.yml
```

### Step 6.4: Create `Makefile`

```makefile
.PHONY: help lint test build clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

lint:  ## Run ansible-lint on all playbooks
	ansible-lint image_build_manager.yml playbooks/*.yml

test:  ## Run unit tests
	python -m pytest test/ -v

build:  ## Build per-domain container image
	podman build -t image_build_runner:latest -f containers/Containerfile .

clean:  ## Remove build artifacts and logs
	rm -rf output/ log/ *.retry
```

### Step 6.5: Create `README.md`

A comprehensive README covering:
- What image_build_manager does
- Three execution modes (bare-metal, container, Omnia mono-repo)
- Quick start for each mode
- Configuration reference (config.yml fields)
- Tag reference (prepare, build, cleanup, validate, upgrade, rollback)
- Input/output contracts
- Prerequisites

### Step 6.6: Update Omnia Mono-repo

In the omnia mono-repo, after extraction:

**Option A — Git Submodule** (recommended):
```bash
cd omnia/src
git submodule add https://github.com/dell/image-build-manager.git image_build_manager
```

**Option B — Documentation Reference**:
Update `omnia.sh` and docs to reference the standalone repo:
```bash
# Clone image_build_manager if not present
if [ ! -d "src/image_build_manager" ]; then
    git clone https://github.com/dell/image-build-manager.git src/image_build_manager
fi
```

---

## Phase 7: CI/CD Pipeline

### Step 7.1: GitHub Actions Workflow

**File**: `.github/workflows/ci.yml`

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install ansible-core ansible-lint
      - run: ansible-lint image_build_manager.yml playbooks/*.yml

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt pytest
      - run: python -m pytest test/ -v

  validate-standalone:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: ansible-galaxy collection install -r requirements.yml
      - run: cp config.yml.sample config.yml
      - run: mkdir -p input/my_project/image_build_manager
      - run: cp samples/image_build_config.yml input/my_project/image_build_manager/
      - run: ansible-playbook image_build_manager.yml --tags validate --check
```

---

## Migration Checklist Summary

| Phase | Task | Owner | Status |
|-------|------|-------|--------|
| **0** | Pre-migration validation (code independence) | Dev | ✅ Done |
| **1.1** | Add `standalone_mode` detection | Dev | ☐ TODO |
| **1.2** | Guard upgrade check | Dev | ☐ TODO |
| **1.3** | Add standalone config loading | Dev | ☐ TODO |
| **1.4** | Guard OIM metadata loading | Dev | ☐ TODO |
| **1.5** | Test all 4 mode scenarios | QA | ☐ TODO |
| **2.1** | Create `config.yml.sample` | Dev | ☐ TODO |
| **2.2** | Create `requirements.txt` | Dev | ☐ TODO |
| **2.3** | Create `requirements.yml` | Dev | ☐ TODO |
| **3.1** | Guard `omnia.target` registration | Dev | ☐ TODO |
| **3.2** | Guard `omnia.target` cleanup | Dev | ☐ TODO |
| **3.3** | Add standalone RPM repo loading | Dev | ☐ TODO |
| **4.1** | Document `ansible.cfg` env override | Dev | ☐ TODO |
| **4.3** | Fix `registry_storage_dir` hardcoded path | Dev | ☐ TODO |
| **5.1** | Create `Containerfile` | Dev | ☐ TODO |
| **5.2** | Create container run script | Dev | ☐ TODO |
| **6.1** | Create GitHub repository | Infra | ☐ TODO |
| **6.2** | Copy files to new repo | Dev | ☐ TODO |
| **6.3** | Create `.gitignore` | Dev | ☐ TODO |
| **6.4** | Create `Makefile` | Dev | ☐ TODO |
| **6.5** | Create `README.md` | Dev | ☐ TODO |
| **6.6** | Update Omnia mono-repo reference | Dev | ☐ TODO |
| **7.1** | Create CI/CD pipeline | Dev | ☐ TODO |

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| `config.yml` schema changes break standalone users | Medium | High | Version the schema; validate at startup |
| Omnia mode regression after standalone changes | Medium | High | Test matrix in Phase 1.5; CI runs both modes |
| `image_build_setup` role becomes too complex | Low | Medium | Keep branching minimal — only in setup role |
| Standalone users skip `requirements.txt` install | High | Low | Pre-flight check in setup role for missing deps |
| Container socket mounting fails on rootless podman | Medium | Medium | Document rootless vs rootful; test both |
| RPM repo URL format incompatible with build roles | Low | High | Validate URLs in `validate_build_runtime` |

---

## Success Criteria

1. `ansible-playbook image_build_manager.yml` works on a bare RHEL 10.x host with Ansible+Python installed (Mode A)
2. `podman exec -it image_build_mgr ansible-playbook ...` works with config.yml + repo_status.yml mounted (Mode B)
3. Existing Omnia mono-repo execution is unchanged (Mode C)
4. Zero `/opt/omnia/` hard failures in Mode A or B
5. `ansible-lint` passes on all playbooks
6. CI pipeline validates all three modes
