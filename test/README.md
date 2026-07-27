# Image Build Manager — Test Automation Framework

Functional Verification Testing (FVT) framework for the `image_build_manager`
Ansible domain. Validates playbook deployment, container infrastructure, S3
storage, container registry, build output, and image package contents.

---

## Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Python | 3.12+ | `python3 --version` |
| pip | latest | Bundled with Python |
| Ansible | 2.15+ | Installed via `requirements.txt` |
| SSH access | — | Passwordless recommended (`ssh-copy-id`) |
| Target server | — | OIM server with `image_build_manager` repo |
| repo_manager output | — | In `datasets/project_default/input/repo_manager_output/` |

---

## Quick Start (5 Steps)

```bash
# Step 1 — Clone the repository
git clone <repo_url> image-build-manager
cd image-build-manager/test/

# Step 2 — Run the setup script (creates .venv, installs deps)
bash setup_env.sh

# Step 3 — Activate virtual environment
source .venv/bin/activate

# Step 4 — Configure (see "Configuration" section below)
vi test_config.yml     # Set oim_server_ip, clone settings
vi test_creds.yml      # Set oim_password (auto-encrypted on first run)

# Step 5 — Run tests
./run_validation.sh image_builder verify --marker sanity
```

> **`setup_env.sh` prints detailed next-step instructions after completing.**

---

## Configuration

### test_config.yml (MANDATORY)

This is the primary configuration file. You **must** edit this before running tests.

| Field | Required | Description | Default |
|-------|----------|-------------|---------|
| `oim_server_ip` | **YES** | IP of the target OIM server. Leave empty for local mode. | `""` |
| `oim_ssh_user` | Remote | SSH user for remote execution | `root` |
| `oim_ssh_port` | Remote | SSH port | `22` |
| `clone_url` | Remote | Git URL to clone the repo on the target server | `""` |
| `clone_path` | Remote | Absolute path on target where the repo is cloned | `/root/image-build-manager` |
| `force_clone` | No | Delete existing clone and re-clone fresh | `false` |
| `dataset` | Yes | Dataset folder name under `datasets/` | `project_default` |
| `project_name` | Yes | Project name for input/output paths on target | `project_default` |
| `sync_image_build_input` | No | Push dataset input files to target before tests | `true` |
| `shared_path` | No | Runtime output path on target | `/opt/omnia/image_build_manager` |
| `report_path` | No | Directory for test reports | `reports` |
| `report_name` | No | Base name for report files | `image_build_test_report` |

**Local mode** (`oim_server_ip` is empty): Tests run on the current machine.
No SSH, no sync — the playbook must already be deployed locally.

**Remote mode** (`oim_server_ip` is set): The framework connects to the target
via SSH, clones/pulls the repo, syncs input files, and runs verification remotely.

### test_creds.yml (REQUIRED for remote mode)

```yaml
# Before first run — plain text:
oim_password: "your_ssh_password"

# After first run — auto-encrypted with Ansible Vault.
# Vault key stored in .test_creds.key (gitignored).
```

- If using **passwordless SSH** (`ssh-copy-id`), set `oim_password` to any value.
- The vault key `.test_creds.key` is auto-generated and never committed to git.

### test_run_config.yml (Batch Execution)

Controls which suites run in `--config` mode and in what order.

```yaml
skip_on_failure: false    # Stop suite on first test failure

scenarios:
  image_builder:
    order: 1              # Execution order (ascending)
    run: true             # Enable/disable this suite
    suite: ""             # Subfolder filter (empty = all)
    marker: "sanity"      # Marker filter expression
```

### Datasets

Datasets contain the input files that the playbook needs. Located at:
```
datasets/project_default/
├── config.yml                         # Project config (hostname, domain, admin_nic_ip)
└── input/                             # Everything here syncs to target
    ├── image_build_config.yml         # Domain input configuration
    ├── image_build_credentials.yml    # Vault-encrypted credentials
    ├── .image_build_credentials_key   # Vault password file
    └── repo_manager_output/           # Upstream dependency (repo_manager output)
        ├── repo_status.yml            # RPM repo URLs, cert paths
        ├── functional_group_packages.yml
        └── certs/
            ├── pulp_webserver.crt
            └── pulp_webserver.key
```

**If the target already has the input files** (e.g., after a manual deploy):
→ Set `sync_image_build_input: false` in `test_config.yml`

**If you want to push input files from this machine**:
→ Set `sync_image_build_input: true` (default)
→ Edit the files under `datasets/project_default/input/`

---

## Usage — run_validation.sh

### Syntax

```
./run_validation.sh <scenario> <command> [options]
./run_validation.sh all <command> [options]
./run_validation.sh --config
./run_validation.sh list
./run_validation.sh --help
```

### Commands

| Command | Description |
|---------|-------------|
| `deploy` | Run the Ansible playbook only (tests marked `@deploy`) |
| `verify` | Run verification tests only (skip playbook, exclude `@deploy`) |
| `test` | Full flow: deploy the playbook, then run verification |

### Options

| Option | Description |
|--------|-------------|
| `--suite <name>` | Filter by subfolder inside the scenario (e.g., `container`, `s3`, `registry`) |
| `--marker <expr>` | Filter by pytest marker expression |
| `-v, --verbose` | Increase pytest verbosity |

### Scenarios

| Scenario | Playbook Tag | What It Tests |
|----------|-------------|---------------|
| `image_builder` | *(none — verify only)* | Containers, S3 images, registry images, build_status, packages |
| `image_build_validate` | `--tags validate` | Input config exists, credentials present |
| `image_build_prepare` | `--tags prepare` | MinIO/registry containers, systemd services, ports, S3 buckets |
| `image_build_build` | `--tags build` | S3 images per arch, registry images, build_status, functional groups |
| `image_build_cleanup` | `--tags cleanup` | Containers removed, services stopped, S3/registry cleaned |

### Markers

| Marker | Description |
|--------|-------------|
| `sanity` | Baseline must-pass tests |
| `x86_64` | x86_64 architecture-specific tests |
| `aarch64` | aarch64 architecture-specific tests |
| `functional` | Functional verification tests |
| `deploy` | Playbook deployment tests (used internally by `deploy` command) |

### Marker Expressions

| Expression | Meaning | Example |
|------------|---------|---------|
| `sanity` | Single marker — tests with `@pytest.mark.sanity` | `--marker sanity` |
| `x86_64,aarch64` | OR — tests with **either** marker | `--marker x86_64,aarch64` |
| `x86_64+sanity` | AND — tests with **both** markers | `--marker x86_64+sanity` |

---

## Examples

### Verify an existing deployment (no playbook execution)

```bash
# Verify all sanity tests
./run_validation.sh image_builder verify --marker sanity

# Verify only x86_64 tests
./run_validation.sh image_builder verify --marker x86_64

# Verify both architectures
./run_validation.sh image_builder verify --marker x86_64,aarch64

# Verify only x86_64 sanity tests (AND)
./run_validation.sh image_builder verify --marker x86_64+sanity

# Verify only container tests in the image_builder suite
./run_validation.sh image_builder verify --suite container

# Verify only S3 tests in the image_builder suite
./run_validation.sh image_builder verify --suite s3
```

### Deploy + verify (full flow)

```bash
# Deploy prepare tag and verify infrastructure
./run_validation.sh image_build_prepare test

# Deploy validate tag and verify input config
./run_validation.sh image_build_validate test

# Deploy build tag and verify images (x86_64 only)
./run_validation.sh image_build_build test --marker x86_64

# Deploy cleanup tag and verify all artifacts removed
./run_validation.sh image_build_cleanup test
```

### Deploy only (no verification)

```bash
./run_validation.sh image_build_prepare deploy
./run_validation.sh image_build_build deploy
```

### Batch execution from config

```bash
# Edit test_run_config.yml to enable/disable suites
vi test_run_config.yml

# Run all enabled suites in configured order
./run_validation.sh --config
```

### Run all scenarios

```bash
./run_validation.sh all test
./run_validation.sh all verify --marker sanity
```

### List available scenarios

```bash
./run_validation.sh list
```

### Direct pytest (advanced users)

```bash
source .venv/bin/activate

# Run specific test file
python3 -m pytest fvt/image_builder/container/test_containers.py -v -s

# Run with custom marker
python3 -m pytest fvt/image_builder/ -v -s --marker x86_64+sanity

# Run cleanup verification only (exclude deploy)
python3 -m pytest fvt/image_build_cleanup/cleanup/ -v -s -m "not deploy"
```

---

## Typical End-to-End Workflow

```bash
# 1. Setup environment (one-time)
bash setup_env.sh
source .venv/bin/activate
vi test_config.yml
vi test_creds.yml

# 2. Clean up any previous state
./run_validation.sh image_build_cleanup test

# 3. Validate inputs
./run_validation.sh image_build_validate test

# 4. Prepare infrastructure (MinIO, registry, S3 buckets)
./run_validation.sh image_build_prepare test

# 5. Build images (~30-60 minutes)
./run_validation.sh image_build_build test --marker x86_64

# 6. Full verification of the completed build
./run_validation.sh image_builder verify --marker sanity

# 7. View reports
python3 -m http.server 8899 --directory reports/
# Open: http://localhost:8899/image_build_test_report.html
```

---

## Reports

Test reports are generated automatically in `reports/` after each run:

| File | Format | Description |
|------|--------|-------------|
| `image_build_test_report.json` | JSON | Machine-readable test results |
| `image_build_test_report.html` | HTML | Interactive browser report with pass/fail/skip summary |

Reports accumulate across runs. Each run is tagged with a unique `REPORT_ID`
(auto-generated timestamp or custom via environment variable).

```bash
# Custom report ID
export REPORT_ID=sprint_42
./run_validation.sh image_builder verify

# View HTML report
python3 -m http.server 8899 --directory reports/
```

---

## Directory Structure

```
test/
├── setup_env.sh             # One-time environment setup (creates .venv)
├── run_validation.sh        # CLI runner — main entry point
├── conftest.py              # Pytest hooks, fixtures, session setup, report generation
├── test_config.yml          # Target server connection settings (MANDATORY)
├── test_creds.yml           # SSH credentials (Ansible Vault encrypted)
├── test_run_config.yml      # Batch suite definitions for --config mode
├── requirements.txt         # Python dependencies
│
├── datasets/                # Test input datasets
│   └── project_default/
│       ├── config.yml       # Project config (hostname, domain, admin_nic_ip)
│       └── input/           # Synced to target server
│           ├── image_build_config.yml
│           ├── image_build_credentials.yml
│           ├── .image_build_credentials_key
│           └── repo_manager_output/
│               ├── repo_status.yml
│               ├── functional_group_packages.yml
│               └── certs/
│
├── library/                 # Reusable automation library
│   ├── __init__.py
│   ├── functions/
│   │   ├── formatting_func.py    # TestLogger, Colors, Symbols
│   │   ├── host_func.py          # Config loading, SSH, clone, sync
│   │   ├── build_image_func.py   # Verification functions (containers, S3, registry)
│   │   ├── report_func.py        # TestReport, HTML/JSON generation
│   │   └── runner_func.py        # PlaybookRunner (ansible-playbook execution)
│   ├── vars/
│   │   ├── common_vars.py        # CMDS dict, constants, paths, ports
│   │   └── runner_vars.py        # PlaybookRunner constants
│   ├── messages/
│   │   └── build_image_msgs.py   # TEST_NAMES, TEST_LOG_MSGS, TEST_ASSERT_MSGS
│   └── validation/
│       └── functions/
│           └── validation_func.py
│
├── reports/                 # Generated test reports (gitignored)
│
└── fvt/                     # Functional Verification Tests
    ├── image_builder/       # Full verification (verify only)
    │   ├── container/       #   TC_IB_001-002: MinIO, registry
    │   ├── s3/              #   TC_IB_003-005: S3 buckets and images
    │   ├── registry/        #   TC_IB_006-010: Registry, build_status, groups
    │   └── image_verification/  # TC_IB_011-012: Package verification
    ├── image_build_validate/    # TC_VL_001-003: Validate tag
    ├── image_build_prepare/     # TC_PR_001-008: Prepare tag
    ├── image_build_build/       # TC_BD_001-006: Build tag
    └── image_build_cleanup/     # TC_CL_001-008: Cleanup tag
```

---

## Test Case IDs

Every test has a unique ID in format `TC_<AREA>_<SEQ>`:

| Area | Prefix | Description |
|------|--------|-------------|
| Image Builder (full) | `TC_IB_` | Full verification suite (14 tests) |
| Validate | `TC_VL_` | Validate tag tests (3 tests) |
| Prepare | `TC_PR_` | Prepare tag tests (8 tests) |
| Build | `TC_BD_` | Build tag tests (6 tests) |
| Cleanup | `TC_CL_` | Cleanup tag tests (8 tests) |

Test case IDs appear in:
- Test function docstrings
- TestLogger output header (e.g., `▶ [TC_IB_001] Verify S3 storage backend`)
- Design document (`docs/design/test-automation-design.md`)

---

## Architecture

### Separation of Concerns

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **Test files** | `fvt/` | Call library functions, handle pass/fail/skip, assertions |
| **Functions** | `library/functions/` | All verification logic, SSH commands, config loading |
| **Variables** | `library/vars/` | Constants, paths, command templates (`CMDS` dict) |
| **Messages** | `library/messages/` | Test names, log messages, assertion messages |

**Rule**: Test files never contain inline messages, hardcoded commands, or
verification logic. Everything is imported from the library.

### Key Components

**TestLogger** — Structured test output with `✓`/`✗` formatting:
```
  ▶ [TC_IB_006] Verify x86_64 images in registry
  ✔ PASS: All x86_64 images found in registry
    │ Registry: abhoim.vm.cluster:5000
    │ ✓ rhel-x86_64-base
    │ ✓ rhel-slurm_node_x86_64
```

**PlaybookRunner** — Live-streaming Ansible playbook execution with line
truncation and formatted output.

**TestReport** — Accumulating JSON + HTML report generator with folder
breakdown, suite/marker info, and pass/fail/skip summary.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| SSH connection refused | Check `oim_server_ip` in `test_config.yml`. Run `ssh root@<ip>` manually. |
| Dataset files not found | Ensure `datasets/project_default/input/` has all files. Set `sync_image_build_input: true`. |
| Build tests fail "not found" | Build tests require `--tags build` to have run first. Run `image_build_build test`. |
| Cleanup shows creds still exist | Expected with `test` command (conftest re-syncs). Use `verify` to check pure cleanup. |
| Reports not generating | Check `reports/` exists. Ensure pytest collects tests (`collected N items`). |
| Vault decryption error | Delete `.test_creds.key` and `test_creds.yml`, re-create and re-run. |

---

## Related Documentation

| Document | Path |
|----------|------|
| Design & Architecture | `docs/design/image-builder-design.md` |
| Test Automation Design | `docs/design/test-automation-design.md` |
| Input Contract | `docs/contracts/input-contract.md` |
| Output Contract | `docs/contracts/output-contract.md` |
| Test Automation Rules | `docs/code-style/test_automation.md` |
| Python Style Guide | `docs/code-style/python.md` |
