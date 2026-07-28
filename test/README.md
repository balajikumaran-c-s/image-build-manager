# Image Build Manager — Test Automation Framework

Functional Verification Testing (FVT) framework for the `image_build_manager`
Ansible domain. Validates playbook deployment, container infrastructure, S3
storage, container registry, build output, and image package contents.

---

## Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Python | 3.12+ | `python3 --version` |
| Ansible | 2.15+ | Installed via `requirements.txt` |

---

## Quick Start

```bash
# Step 1 — Clone and enter test directory
git clone <repo_url> image-build-manager
cd image-build-manager/test/

# Step 2 — Run setup (creates .venv, installs deps)
bash setup_env.sh

# Step 3 — Activate and configure
source .venv/bin/activate
vi test_config.yml              # See docs/test_config.md

# Step 4 — Run tests
./run_validation.sh image_build_manager verify --marker sanity
```

---

## Configuration

| File | Purpose | Reference |
|------|---------|-----------|
| [`test_config.yml`](docs/test_config.md) | Target server, sync, dataset, report settings | [docs/test_config.md](docs/test_config.md) |
| [`test_creds.yml`](docs/test_creds.md) | SSH credentials (auto-encrypted with Ansible Vault) | [docs/test_creds.md](docs/test_creds.md) |
| [`test_run_config.yml`](docs/test_run_config.md) | Batch execution: scenario order, markers, suites | [docs/test_run_config.md](docs/test_run_config.md) |

### Execution Modes

- **Local mode** (`oim_server_ip: ""`): Tests run on the current machine. No SSH needed.
- **Remote mode** (`oim_server_ip: "<IP>"`): Tests run against a remote server via SSH.

### Datasets

Input files for the playbook are stored in `datasets/data_set_01/`.
See [`datasets/data_set_01/README.md`](datasets/data_set_01/README.md) for field details.

---

## Usage

```
./run_validation.sh <scenario> <command> [options]
./run_validation.sh --config          # Batch run from test_run_config.yml
./run_validation.sh list              # List available scenarios
./run_validation.sh --help            # Full usage
```

### Commands

| Command | Description |
|---------|-------------|
| `deploy` | Run the Ansible playbook only |
| `verify` | Run verification tests only (no playbook) |
| `test` | Full flow: deploy + verify |

### Scenarios

| Scenario | Playbook Tag | What It Tests |
|----------|-------------|---------------|
| `image_build_manager` | *(none — prepare + build)* | Full end-to-end: containers, S3, registry, build_status, packages |
| `validate` | `--tags validate` | Input config and credentials present |
| `prepare` | `--tags prepare` | MinIO, registry, systemd services, S3 buckets |
| `build` | `--tags build` | S3 images, registry images, build_status |
| `cleanup` | `--tags cleanup` | All artifacts removed |

### Options

| Option | Description |
|--------|-------------|
| `--suite <name>` | Filter by subfolder (e.g., `container`, `s3`, `registry`) |
| `--marker <expr>` | Filter by marker (`sanity`, `x86_64`, `x86_64+sanity`, `x86_64,aarch64`) |
| `--debug` | Full debug output (pytest -vvs) |
| `-v, --verbose` | Increase pytest verbosity |

---

## Typical Workflow

```bash
./run_validation.sh cleanup test                              # 1. Clean previous state
./run_validation.sh validate test                              # 2. Validate inputs
./run_validation.sh prepare test                               # 3. Prepare infrastructure
./run_validation.sh build test --marker x86_64                 # 4. Build images
./run_validation.sh image_build_manager verify --marker sanity  # 5. Full verification
```

---

## Reports

Generated in `reports/` after each run:

| File | Format |
|------|--------|
| `image_build_test_report.json` | Machine-readable results |
| `image_build_test_report.html` | Interactive browser report |

```bash
python3 -m http.server 8899 --directory reports/
```

---

## Test Cases

See [`fvt/TEST_CASES.md`](fvt/TEST_CASES.md) for the complete test case registry.

| Scenario | Prefix | Count |
|----------|--------|-------|
| image_build_manager | TC_IB_ | 12 |
| validate | TC_VL_ | 3 |
| prepare | TC_PR_ | 8 |
| build | TC_BD_ | 6 |
| cleanup | TC_CL_ | 8 |

---

## Directory Structure

```
test/
├── setup_env.sh                 # Environment setup (--force, --debug)
├── run_validation.sh            # CLI runner
├── conftest.py                  # Pytest hooks, fixtures, report generation
├── test_config.yml              # Target server settings
├── test_creds.yml               # SSH credentials (Ansible Vault)
├── test_run_config.yml          # Batch execution config
├── requirements.txt             # Python dependencies
│
├── docs/                        # Configuration documentation
│   ├── test_config.md
│   ├── test_creds.md
│   └── test_run_config.md
│
├── datasets/                    # Test input datasets
│   └── data_set_01/             # See datasets/data_set_01/README.md
│       ├── input/               # config.yml, image_build_config, credentials
│       └── repo_manager_output/ # repo_status, packages, certs
│
├── library/                     # Reusable automation library
│   ├── functions/               # Host, formatting, build image, report, runner, validation
│   ├── vars/                    # Constants, paths, commands
│   └── messages/                # Test names, log/assert messages
│
└── fvt/                         # Functional Verification Tests
    ├── TEST_CASES.md            # Complete test case registry
    ├── image_build_manager/     # Full end-to-end (deploy + verify)
    │   ├── container/
    │   ├── s3/
    │   ├── registry/
    │   └── image_verification/
    ├── validate/                # Validate tag
    │   └── status/
    ├── prepare/                 # Prepare tag
    │   ├── container/
    │   └── s3/
    ├── build/                   # Build tag
    │   ├── s3/
    │   └── registry/
    └── cleanup/                 # Cleanup tag
        └── cleanup/
```

---

## Documentation

| Document | Location |
|----------|----------|
| [Test Automation Design](../docs/design/test-automation-design.md) | `docs/design/test-automation-design.md` |
| [Test Automation Rules](../docs/code-style/test_automation.md) | `docs/code-style/test_automation.md` |
