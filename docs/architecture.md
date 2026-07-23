# Image Build Manager — Architecture Overview

## System Context

```
                    ┌─────────────────────────────────────────────┐
                    │           Image Build Manager                │
                    │                                             │
  ┌──────────┐      │  ┌────────────┐  ┌────────────┐  ┌────────┐│      ┌──────────┐
  │ User     │─────▶│  │ Validate   │─▶│ Prepare    │─▶│ Build  ││─────▶│ S3 / OCI │
  │ config   │      │  │ (schema +  │  │ (MinIO +   │  │ (base +││      │ Artifacts│
  │ files    │      │  │  runtime)  │  │  registry) │  │ compute││      │          │
  └──────────┘      │  └────────────┘  └────────────┘  └────────┘│      └──────────┘
                    └─────────────────────────────────────────────┘
```

## Execution Flow

### 1. Setup (`image_build_manager.yml` — tag: always)

- Detect execution mode (standalone or omnia)
- Load `config.yml` → set `input_project_dir`, `output_project_dir`, `oim_shared_path`
- Load `image_build_config.yml` → S3 config, functional groups, build settings
- Load `repo_status.yml` → RPM repo URLs, OS metadata, Pulp certificates
- Create `oim` host group (local for Mode A, SSH for Mode B)
- Validate tag usage (supported_tags, invalid_tag_combinations)

### 2. Validate (`--tags validate`)

- Schema validation of `image_build_config.yml` against JSON schema
- Logic validation (S3 provider, aarch64 host, repo_status pre-check)
- No credentials required

### 3. Prepare (`--tags prepare`)

- Collect S3 credentials (interactive prompts, Ansible Vault)
- Deploy MinIO S3 (if provider=minio) via Podman Quadlet
- Deploy local OCI container registry via Podman Quadlet

### 4. Build (`--tags build`)

- Write `functional_groups_config.yml` from `image_build_config.yml`
- Load `functional_group_packages.yml` → `base_image_packages` + `compute_images_dict`
- Fetch Pulp RPM repo URLs from `repo_status.yml`
- Build base OS image (OpenCHAMI image-build)
- Build compute images per functional group (OpenCHAMI image-build)
- Upload to S3 (boot-images + efi-images buckets)
- Write `build_status.yml` with artifact paths

### 5. Cleanup (`--tags cleanup`)

- Stop and remove MinIO + Registry containers
- Remove build artifacts, credentials, S3 data
- Remove firewall ports and systemd entries

## Role Dependency Graph

```
image_build_setup ─────────────────────────────────────────┐
       │                                                   │
       ▼                                                   ▼
validate_image_build_input                    collect_build_credentials
       │                                                   │
       ▼                                                   ▼
validate_build_runtime                        deploy_minio + deploy_registry
       │                                                   │
       ▼                                                   ▼
fetch_build_packages ──────────────────────▶ build_os_images
       │                                                   │
       │                                                   ▼
       │                                     write_build_status
       │
       ▼
cleanup_build_artifacts
```

## Data Contract

### Inputs

| File | Purpose |
|------|---------|
| `config.yml` | Project + build host settings |
| `image_build_config.yml` | S3, functional groups, build params |
| `repo_status.yml` | RPM repo URLs + OS metadata |
| `functional_group_packages.yml` | Functional group → RPM package mapping |
| Pulp certs | TLS certificates for RPM repo access |

### Outputs

| File | Purpose |
|------|---------|
| `build_status.yml` | S3 artifact paths per functional group |
| Validation logs | `output/<project>/log/image_build_validation_*.log` |

## Key Design Decisions

1. **No `software_config.json`** — replaced by `functional_group_packages.yml`
2. **No `/opt/omnia` paths** — all paths derived from `config.yml`
3. **No `omnia_core` container** — runs on bare-metal or domain container
4. **Mode C code commented out** — kept for historical reference only
5. **Single mapping file** — `functional_group_packages.yml` is the single source
   of truth for which RPMs go into each image variant
