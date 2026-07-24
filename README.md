# Image Build Manager

Build OS images (x86_64 + aarch64) for HPC cluster provisioning using OpenCHAMI.
Deploys MinIO (S3) + local container registry, builds base and compute images,
and writes `build_status.yml` with S3 artifact paths.

**Runs directly on a RHEL host** with Ansible + Python (Mode A — bare-metal).
No container runtime required for the playbook itself (Podman is used for image builds).

## Prerequisites

| Requirement | Minimum | Validated |
|------------|---------|-----------|
| OS | RHEL 10.x, Rocky 10.x | RHEL 10.0 |
| Python | 3.12+ | 3.12.8 |
| Ansible | ansible-core 2.20+ | 2.20.0 |
| Container runtime | Podman 5.0+ | 5.3.1 |
| Disk space | 50 GB free | — |

### Ansible Installation

**Fresh install (recommended)**:

```bash
python3 -m venv ~/.venvs/image-build
source ~/.venvs/image-build/bin/activate
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml
```

**If Ansible is already installed**:

```bash
# Check version — must be ansible-core >= 2.20
ansible --version

# If older, use a virtual environment to avoid conflicts:
python3 -m venv ~/.venvs/image-build
source ~/.venvs/image-build/bin/activate
pip install -r requirements.txt
```

**Verify**:

```bash
ansible --version          # ansible-core 2.20+
ansible-galaxy collection list | grep containers.podman
```

## Quick Start

```bash
# 1. Configure
cp config.yml.sample config.yml
# Edit config.yml — set admin_nic_ip, shared_path, domain_name, hostname

# 2. Install dependencies
python3 -m venv ~/.venvs/image-build
source ~/.venvs/image-build/bin/activate
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml

# 3. Ensure repo_manager output directory exists
# Production: /opt/omnia/repo_manager/output/<project_name>/ must contain:
#   repo_status.yml               — from repo_manager
#   functional_group_packages.yml — package mapping
# Set repo_manager_output_dir in image_build_config.yml to this directory

# 4. Edit image_build_config.yml — enable functional groups to build
vi src/input/project_default/image_build_config.yml

# 5. Run
cd src
ansible-playbook image_build_manager.yml --tags validate   # Validate config
ansible-playbook image_build_manager.yml --tags prepare    # Deploy MinIO + Registry
ansible-playbook image_build_manager.yml --tags build      # Build OS images
ansible-playbook image_build_manager.yml --tags cleanup    # Remove everything
```

## Input Files

| File | Location | Required | Description |
|------|----------|----------|-------------|
| `config.yml` | Repo root | Yes | Host + project settings |
| `image_build_config.yml` | `src/input/project_default/` | Yes | S3 config, functional groups, build settings |
| `repo_status.yml` | `/opt/omnia/repo_manager/output/<project_name>/` | Yes | RPM repo URLs + OS metadata + cert paths |
| `functional_group_packages.yml` | `/opt/omnia/repo_manager/output/<project_name>/` | Yes | **Functional group → RPM package mapping** |
| `image_build_credentials.yml` | Auto-generated in project dir | Yes (except validate/cleanup) | S3 + provision credentials |

### Certificate Handling

Certificates are referenced by **absolute paths** in `repo_status.yml`:

```yaml
repo_manager:
  port: 2225
  certificates:
    server_crt: /opt/omnia/pulp/settings/certs/pulp_webserver.crt
    server_key: /opt/omnia/pulp/settings/certs/pulp_webserver.key
    certs_dir: /opt/omnia/pulp/settings/certs
```

The playbook reads the cert path directly from `repo_status.yml` and validates the file
exists on the host. No staging or copying is needed — the cert is used as-is.

## Package Resolution Flow

```
image_build_config.yml                functional_group_packages.yml
┌──────────────────────────┐          ┌──────────────────────────────────┐
│ functional_groups:       │          │ base_packages:                   │
│   - name: slurm_node_x86│──────┐   │   - systemd                     │
│   - name: slurm_ctrl_x86│      │   │   - kernel                      │
│   - name: os_x86_64     │      │   │   - dracut                      │
└──────────────────────────┘      │   │   - ...                         │
                                  │   │ functional_groups:               │
                                  └──▶│   slurm_node_x86_64:            │
                                      │     packages:                    │
                                      │       - munge                    │
                                      │       - slurm-slurmd             │
                                      │       - ...                      │
                                      └──────────────────────────────────┘
                                                  │
                                                  ▼
                                      base_image_packages  (all images)
                                      compute_images_dict  (per functional group)
                                                  │
                                                  ▼
                                      OpenCHAMI image-build → S3 upload
```

**No `software_config.json` needed.** The `functional_group_packages.yml` file is the
single source of truth for which RPM packages belong to each functional group.

## Configuration Reference

### `config.yml`

Host and project settings. See `config.yml.sample`.

| Field | Description | Default |
|-------|-------------|---------|
| `project_name` | Project name (maps to input/output dirs) | `project_default` |
| `host.hostname` | Short hostname (NOT FQDN) — domain_name appended | `localhost` |
| `host.shared_path` | Persistent storage for MinIO + Registry data | `/opt/omnia/image_build_manager` |
| `host.domain_name` | Domain suffix for registry naming | `local` |
| `host.admin_nic_ip` | Admin NIC IP (Pulp and S3 endpoint) | — |

### `image_build_config.yml`

Per-domain configuration. Key sections:
- **`s3_configurations`** — S3 provider (minio or powerscale)
- **`repo_manager_output_dir`** — directory with `repo_status.yml` + `functional_group_packages.yml` (default: `/opt/omnia/repo_manager/output/project_default`)
- **`functional_groups`** — image variants to build (e.g., `os_x86_64`, `slurm_node_x86_64`)
- **`aarch64_inventory_host_ip`** — ARM build host (leave empty to skip aarch64)
- **`build_image`** — async/retry/delay settings

### `functional_group_packages.yml`

**Single source of truth** for RPM package mapping per functional group.
Located in `repo_manager_output/`. Structure:

```yaml
base_packages:         # RPMs installed in EVERY image (base OS layer)
  - systemd
  - kernel
  - ...

functional_groups:     # Additional RPMs per functional group
  slurm_node_x86_64:
    packages:
      - munge
      - slurm-slurmd
      - ...
  os_x86_64:
    packages: []       # Only base packages
```

**To customize**: Add or remove RPM package names under the appropriate functional group.
Package names must match what is available in the Pulp RPM repos defined in `repo_status.yml`.

### `repo_status.yml`

Produced by `repo_manager` at `/opt/omnia/repo_manager/output/repo_status.yml`.
Contains RPM repo URLs, OS metadata, and certificate paths (absolute).

Key fields consumed by image_build_manager:
- **`cluster_os_type`** / **`cluster_os_version`** — build target OS
- **`rpm_repos.x86_64`** / **`rpm_repos.aarch64`** — RPM repository URLs
- **`repo_manager.port`** — Pulp HTTPS port (default: 2225)
- **`repo_manager.certificates.server_crt`** — absolute path to Pulp TLS cert

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

## Output Paths

All runtime output goes to `<shared_path>/` (default: `/opt/omnia/image_build_manager/`):

| Path | Purpose |
|------|---------|
| `<shared_path>/output/<project_name>/` | Build output (`build_status.yml`) |
| `<shared_path>/log/<project_name>/` | Build logs (base/compute image logs) |
| `<shared_path>/log/image_build_manager.log` | Ansible playbook log |
| `<shared_path>/s3/` | MinIO S3 data |
| `<shared_path>/registry/` | Local container registry storage |
| `<shared_path>/oci/` | OCI image data |
| `<shared_path>/workdir/` | OpenCHAMI image build workdir |

## CI/CD Pipeline

The `.github/workflows/ci.yml` runs on push/PR to `main`:

- **lint** — `ansible-lint` on all playbooks
- **test** — `pytest` on unit tests
- **validate-standalone** — Copies `config.yml.sample` + `repo_status.yml`, creates input dirs, runs `--tags validate --check`

## Repository Structure

```
image-build-manager/
├── README.md                    # This file
├── CODING_RULES.md              # Developer coding rules and conventions
├── config.yml.sample            # Sample config (host + project settings)
├── requirements.txt             # Python dependencies (ansible-core>=2.20)
├── requirements.yml             # Ansible collections
├── .gitignore
├── .github/workflows/ci.yml    # CI pipeline
├── docs/                        # All documentation (see docs/README.md)
│   ├── README.md                # Documentation index
│   ├── design/                  # Architecture and design documents
│   │   ├── standalone-mode-a.md # Mode A bare-metal design
│   │   └── omnia-domain-repo-design.md # Generic Omnia domain standard
│   ├── code-style/              # Code style guides
│   │   ├── ansible.md           # Ansible/YAML style guide
│   │   ├── python.md            # Python style guide
│   │   ├── jinja2.md            # Jinja2 template style guide
│   │   └── general.md           # General code style
│   ├── contracts/               # Input/output contracts
│   ├── migration/               # Migration history from Omnia mono-repo
│   ├── architecture.md          # Architecture overview
│   ├── package-mapping-guide.md # Package customization guide
│   └── troubleshooting.md       # Common issues and fixes
├── test/                        # Unit and integration tests
└── src/
    ├── ansible.cfg              # Ansible configuration
    ├── image_build_manager.yml  # Main playbook entry point (roles + imports only)
    ├── roles/                   # All Ansible roles
    │   ├── image_build_setup/         # Config, validation, prereqs, repo loading
    │   │   └── tasks/
    │   │       ├── main.yml               # Dispatcher (includes below)
    │   │       ├── validate_tags.yml      # Tag validation
    │   │       ├── load_config.yml        # Load config.yml + host validation
    │   │       ├── validate_prereqs.yml   # Prerequisite file checks
    │   │       └── load_repo_status.yml   # Load repo_status + build repo lists
    │   ├── validate_image_build_input/ # Schema + logic validation
    │   ├── validate_build_runtime/    # Runtime pre-checks
    │   ├── collect_build_credentials/ # Interactive credential prompts
    │   ├── deploy_minio/              # MinIO S3 deployment (Quadlet)
    │   ├── deploy_registry/           # Local container registry (Quadlet)
    │   ├── fetch_build_packages/      # Package resolution from mapping file
    │   ├── build_os_images/           # OpenCHAMI image build + S3 upload
    │   ├── prepare_aarch64_node/      # ARM node preparation
    │   └── cleanup_build_artifacts/   # Full cleanup
    ├── playbooks/               # Sub-playbooks (prepare, build, cleanup)
    ├── library/                 # Custom Ansible modules
    ├── module_utils/            # Shared Python module utilities
    ├── callback_plugins/        # Output callback (omnia_default.py)
    ├── vars/                    # Shared variables
    └── input/
        └── project_default/
            └── image_build_config.yml  # Build config (edit this)
```

### Runtime Output (auto-created at `/opt/omnia/image_build_manager/`)

```
/opt/omnia/image_build_manager/
├── output/project_default/      # build_status.yml, versioned copies
├── log/project_default/         # Base/compute image build logs
├── log/image_build_manager.log  # Ansible playbook log
├── s3/                          # MinIO S3 data
├── registry/                    # Local container registry storage
├── oci/                         # OCI image data
└── workdir/                     # OpenCHAMI image build workdir
```

## License

Apache License, Version 2.0