# Image Build Manager

Build OS images (x86_64 + aarch64) for HPC cluster provisioning using OpenCHAMI.
Deploys MinIO (S3) + local container registry, builds base and compute images,
and writes `build_status.yml` with S3 artifact paths.

## Execution Modes

| Mode | Description | Config Source |
|------|-------------|---------------|
| **A — Bare-metal** | Run directly on a RHEL host with Ansible + Python | `config.yml` + `repo_status.yml` |
| **B — Container** | Run inside a long-running domain container | Mounted `config.yml` + `repo_status.yml` |
| **C — Omnia mono-repo** | Run inside `omnia_core` container (existing) | OIM metadata + repo_manager output |

## Quick Start

### Mode A — Bare-metal (standalone)

```bash
# 1. Install dependencies
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml

# 2. Configure
cp config.yml.sample config.yml
# Edit config.yml:
#   - Set input_dir/output_dir to ABSOLUTE paths on this host
#     e.g., input_dir: "/home/user/image-build-manager/src/input"
#   - Set admin_nic_ip, shared_path, domain_name

# 3. Provide repo_status.yml (RPM repo URLs + OS version)
# Copy from repo_manager output or create manually — see src/samples/repo_status.yml
cp src/samples/repo_status.yml src/repo_status.yml
# Edit src/repo_status.yml — replace {{ admin_nic_ip }} with actual IP

# 4. Create input project directory with image_build_config.yml
mkdir -p src/input/project_default/image_build_manager
# Place image_build_config.yml in the above directory

# 5. Set log path (overrides /opt/omnia/ default in ansible.cfg)
export ANSIBLE_LOG_PATH=$(pwd)/log/image_build_manager.log
export ANSIBLE_REMOTE_TMP=/tmp/.ansible/tmp

# 6. Run
cd src
ansible-playbook image_build_manager.yml --tags validate    # Validate config only
ansible-playbook image_build_manager.yml --tags prepare     # Deploy MinIO + Registry
ansible-playbook image_build_manager.yml --tags build       # Build images
ansible-playbook image_build_manager.yml --tags cleanup     # Cleanup
ansible-playbook image_build_manager.yml                    # Full flow (all tags)
```

### Mode B — Container

```bash
# 1. Configure
cp config.yml.sample config.yml
# Edit config.yml:
#   - Default paths (/image_build_manager/input, /output, /log) match the podman mounts below
#   - Set admin_nic_ip, shared_path, domain_name

# 2. Provide repo_status.yml
cp src/samples/repo_status.yml src/repo_status.yml
# Edit src/repo_status.yml — replace {{ admin_nic_ip }} with actual IP

# 3. Create input project directory with image_build_config.yml
mkdir -p src/input/project_default/image_build_manager
# Place image_build_config.yml in the above directory

# 4. Build the domain runner container
podman build -t image_build_runner:1.0 -f src/containers/image_build_runner/Containerfile .

# 5. Start (long-running — stays alive with sshd)
# Volume mounts MUST match the absolute paths in config.yml:
#   config.yml input_dir  → /image_build_manager/input
#   config.yml output_dir → /image_build_manager/output
podman run -d --name image_build_mgr --privileged -p 2230:2230 \
    -v $(pwd)/config.yml:/image_build_manager/config.yml:ro \
    -v $(pwd)/src/repo_status.yml:/image_build_manager/src/repo_status.yml:ro \
    -v $(pwd)/src/input:/image_build_manager/input:rw \
    -v $(pwd)/src/output:/image_build_manager/output:rw \
    -v $(pwd)/log:/image_build_manager/log:rw \
    -v /run/podman/podman.sock:/run/podman/podman.sock \
    image_build_runner:1.0

# 6. Run tags (container stays alive between runs)
podman exec -it image_build_mgr ansible-playbook image_build_manager.yml --tags validate
podman exec -it image_build_mgr ansible-playbook image_build_manager.yml --tags prepare
podman exec -it image_build_mgr ansible-playbook image_build_manager.yml --tags build
podman exec -it image_build_mgr ansible-playbook image_build_manager.yml --tags cleanup

# Debug
podman exec -it image_build_mgr bash

# Stop
podman stop image_build_mgr && podman rm image_build_mgr
```

### Mode C — Omnia mono-repo (existing behavior)

No changes needed. Run inside `omnia_core` as before:

```bash
cd omnia/src/image_build_manager
ansible-playbook image_build_manager.yml
```

## Input Files

| File | Source | Required |
|------|--------|----------|
| `config.yml` | User (standalone only) | Modes A/B |
| `repo_status.yml` | repo_manager output or user-provided | Yes |
| `image_build_config.yml` | Input project dir | Yes |
| `image_build_credentials.yml` | Ansible Vault prompt | Yes (except validate/cleanup) |

## Configuration Reference

### `config.yml`

Project and build host settings for standalone mode. See `config.yml.sample`.

| Field | Description | Default |
|-------|-------------|---------|
| `project_name` | Project name (maps to input/output dirs) | `project_default` |
| `input_dir` | Path to input directory | `./input` |
| `output_dir` | Path to output directory | `./output` |
| `build_host.hostname` | Build host (`localhost` for local) | `localhost` |
| `build_host.shared_path` | NFS or local path for build artifacts | `/opt/image_build` |
| `build_host.domain_name` | Domain name for the build host | `local` |
| `build_host.admin_nic_ip` | Admin NIC IP (used for MinIO/S3 endpoint) | — |
| `log_dir` | Log directory | `./log` |

### `repo_status.yml`

Produced by `repo_manager`. Contains RPM repo URLs, OS metadata, and certificates.
In standalone mode, copy this from your repo_manager output or create manually.

Key fields consumed by image_build_manager:
- `cluster_os_type` / `cluster_os_version` — build target OS
- `rpm_repos.x86_64` / `rpm_repos.aarch64` — RPM repository URLs
- `repo_manager.port` / `repo_manager.certificates` — Pulp connection

See `src/samples/repo_status.yml` for the full structure.

## Tags

| Tag | Description |
|-----|-------------|
| `validate` | Validate configuration only (no credentials required) |
| `prepare` | Deploy MinIO S3 + local container registry |
| `build` | Build x86_64 + aarch64 OS images |
| `cleanup` | Remove MinIO, registry, build artifacts, credentials |
| `upgrade` | Upgrade flow |
| `rollback` | Rollback flow |

## Makefile Targets

Run from the repo root:

| Target | Command | Description |
|--------|---------|-------------|
| `make help` | — | Show all available targets |
| `make setup` | `pip install + ansible-galaxy` | Install Python and Ansible dependencies |
| `make lint` | `ansible-lint` | Lint all playbooks |
| `make test` | `pytest` | Run unit tests |
| `make build` | `podman build` | Build the `image_build_runner` container image |
| `make clean` | `rm -rf` | Remove output/, log/, *.retry files |

## Prerequisites

| Requirement | Minimum |
|------------|---------|
| OS | RHEL 10.x, Rocky 10.x |
| Python | 3.13+ |
| Ansible | ansible-core 2.20+ |
| Container runtime | Podman 4.0+ |
| Disk space | 50 GB free |

## CI/CD Pipeline

The `.github/workflows/ci.yml` runs on push/PR to `main`:

- **lint** — `ansible-lint` on all playbooks
- **test** — `pytest` on unit tests
- **validate-standalone** — Copies `config.yml.sample` + `repo_status.yml`, creates input dirs, runs `--tags validate --check`

## Repository Structure

```
image-build-manager/
├── README.md                    # This file
├── config.yml.sample            # Sample standalone config
├── requirements.txt             # Python dependencies (ansible-core>=2.20)
├── requirements.yml             # Ansible collections
├── Makefile                     # help, setup, lint, test, build, clean
├── .gitignore
├── .github/workflows/ci.yml    # CI pipeline
└── src/
    ├── ansible.cfg              # Ansible configuration
    ├── image_build_manager.yml  # Main playbook entry point
    ├── roles/                   # All Ansible roles
    ├── playbooks/               # Sub-playbooks (prepare, build, cleanup, etc.)
    ├── library/                 # Custom Ansible modules
    ├── callback_plugins/        # Output callback
    ├── samples/                 # Sample files (repo_status.yml, build_status.yml)
    ├── vars/                    # Shared variables
    └── containers/
        ├── build_images.sh      # Build script for image containers
        ├── image_builder/       # OpenCHAMI image builder container (ochami)
        └── image_build_runner/  # Domain runner container (sshd, long-running)
            ├── Containerfile    # Wolfi-based, Python 3.13, SSH port 2230 (configurable)
            └── entrypoint.sh    # Starts sshd + keeps container alive
```

## License

Apache License, Version 2.0