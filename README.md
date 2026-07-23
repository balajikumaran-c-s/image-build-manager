# Image Build Manager

Build OS images (x86_64 + aarch64) for HPC cluster provisioning using OpenCHAMI.
Deploys MinIO (S3) + local container registry, builds base and compute images,
and writes `build_status.yml` with S3 artifact paths.

## Execution Modes

| Mode | Description | Config Source |
|------|-------------|---------------|
| **A — Bare-metal** | Run directly on a RHEL host with Ansible + Python | `config.yml` + `repo_status.yml` |
| **B — Container** | Run inside a long-running domain container | Mounted `config.yml` + `repo_status.yml` |

## Quick Start

### Mode A — Bare-metal (standalone)

```bash
# 1. Install dependencies
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml

# 2. Configure
cp config.yml.sample config.yml
# Edit config.yml — set admin_nic_ip, shared_path, domain_name

# 3. Copy repo_manager output (repo_status.yml + certs)
# repo_status.yml is already in src/input/project_default/repo_manager_output/
# Edit it — replace {{ admin_nic_ip }} with actual IP
# Copy Pulp certs from your repo_manager host:
cp /path/to/pulp_webserver.crt src/input/project_default/repo_manager_output/certs/
cp /path/to/pulp_webserver.key src/input/project_default/repo_manager_output/certs/

# 4. Edit image_build_config.yml (already in place)
# Edit src/input/project_default/image_build_config.yml

# 5. Run
export ANSIBLE_LOG_PATH=$(pwd)/log/image_build_manager.log
cd src
ansible-playbook image_build_manager.yml --tags validate
ansible-playbook image_build_manager.yml --tags prepare
ansible-playbook image_build_manager.yml --tags build
```

### Mode B — Container

All paths auto-derived — only 4 mounts needed.

```bash
# 1. Configure
cp config.yml.sample config.yml
# Edit config.yml — set admin_nic_ip, shared_path, domain_name

# 2. Copy repo_manager output (repo_status.yml + certs)
# repo_status.yml is already in src/input/project_default/repo_manager_output/
# Edit it — replace {{ admin_nic_ip }} with actual IP
# Copy Pulp certs from your repo_manager host:
cp /path/to/pulp_webserver.crt src/input/project_default/repo_manager_output/certs/
cp /path/to/pulp_webserver.key src/input/project_default/repo_manager_output/certs/

# 3. Edit image_build_config.yml (already in place)
# Edit src/input/project_default/image_build_config.yml

# 4. Build container
podman build -t image_build_runner:1.0 -f src/containers/image_build_runner/Containerfile .

# 5. Start
mkdir -p /opt/image_build
podman run -d --name image_build_mgr --privileged -p 2230:2230 \
    -v $(pwd)/config.yml:/image_build_manager/config.yml:ro \
    -v $(pwd)/src:/image_build_manager/src:rw \
    -v /opt/image_build:/opt/image_build:rw \
    -v /run/podman/podman.sock:/run/podman/podman.sock \
    image_build_runner:1.0

# 6. Run
podman exec -it image_build_mgr ansible-playbook image_build_manager.yml --tags validate
podman exec -it image_build_mgr ansible-playbook image_build_manager.yml --tags prepare
podman exec -it image_build_mgr ansible-playbook image_build_manager.yml --tags build
podman exec -it image_build_mgr ansible-playbook image_build_manager.yml --tags cleanup

# Debug / Stop
podman exec -it image_build_mgr bash
podman stop image_build_mgr && podman rm image_build_mgr
```

## Input Files

| File | Location | Required |
|------|----------|----------|
| `config.yml` | Repo root | Yes |
| `image_build_config.yml` | `src/input/project_default/` | Yes |
| `repo_status.yml` | `src/input/project_default/repo_manager_output/` | Yes |
| Pulp certs | `src/input/project_default/repo_manager_output/certs/` | Yes |
| `image_build_credentials.yml` | Auto-generated in project dir | Yes (except validate/cleanup) |

## Configuration Reference

### `config.yml`

Project and build host settings for standalone mode. See `config.yml.sample`.

| Field | Description | Default |
|-------|-------------|---------|
| `project_name` | Project name (maps to input/output dirs) | `project_default` |
| `build_host.hostname` | Hostname for cluster naming (always runs locally) | `localhost` |
| `build_host.shared_path` | Persistent storage for MinIO + Registry | `/opt/image_build` |
| `build_host.domain_name` | Domain name for the build host | `local` |
| `build_host.admin_nic_ip` | Admin NIC IP (Pulp and S3 endpoint) | — |

### `image_build_config.yml`

Per-domain configuration. Key sections:
- `s3_configurations` — S3 provider (minio or powerscale)
- `repo_manager_output_path` — path to `repo_manager_output/` directory
- `functional_groups` — image variants to build (e.g., `os_x86_64`, `slurm_node_x86_64`)
- `aarch64_inventory_host_ip` — ARM build host (leave empty to skip aarch64)
- `build_image` — async/retry/delay settings

### `repo_status.yml`

Produced by `repo_manager`. Contains RPM repo URLs, OS metadata, and certificates.
In standalone mode, copy this from your repo_manager output or create manually.

Key fields consumed by image_build_manager:
- `cluster_os_type` / `cluster_os_version` — build target OS
- `rpm_repos.x86_64` / `rpm_repos.aarch64` — RPM repository URLs
- `repo_manager.port` / `repo_manager.certificates` — Pulp connection

See `src/input/project_default/repo_manager_output/repo_status.yml` for the full structure.

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
    ├── input/
    │   └── project_default/
    │       ├── image_build_config.yml  # Edit this
    │       └── repo_manager_output/   # Copy repo_manager output here
    │           ├── repo_status.yml
    │           └── certs/             # Pulp certs
    ├── output/                  # Build output (auto-created)
    └── containers/
        ├── build_images.sh      # Build script for image containers
        ├── image_builder/       # OpenCHAMI image builder container (ochami)
        └── image_build_runner/  # Domain runner container (sshd, long-running)
            ├── Containerfile    # Wolfi-based, Python 3.13, SSH port 2230 (configurable)
            └── entrypoint.sh    # Starts sshd + keeps container alive
```

## License

Apache License, Version 2.0