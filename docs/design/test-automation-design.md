# Test Automation — Design & Architecture

> **Domain**: `image_build_manager` | **Version**: 2.0 | **Last Updated**: Jul 2026

---

## 1. Overview

### 1.1 Purpose

This document describes the test automation architecture for the **image_build_manager**
module. The framework provides Functional Verification Testing (FVT) that validates
the Ansible playbook correctly deploys infrastructure (MinIO, registry), builds OS
images, and produces valid output artifacts on a target server.

### 1.2 Design Principles

| # | Principle | Implementation |
|---|-----------|----------------|
| P1 | **No fallback defaults** | All config fields required. Session fails fast with clear error listing every missing field |
| P2 | **Strict separation** | Messages in `messages/`, constants in `vars/`, logic in `functions/`, tests only call + assert |
| P3 | **Zero hardcoded values** | All IPs, paths, credentials read from config files |
| P4 | **Graceful skipping** | Optional features (aarch64) skip cleanly — no false failures |
| P5 | **Remote + local** | Same tests run against remote server (SSH) or locally (subprocess) |
| P6 | **Structured output** | TestLogger produces consistent ✓/✗ formatted results |
| P7 | **Consolidated reports** | HTML + JSON reports merge across multiple scenario runs |
| P8 | **Deploy + Verify lifecycle** | Every scenario has `test_playbook.py` (deploy) + `<area>/test_<area>.py` (verify) |

### 1.3 Scope

The framework covers five playbook phases via test scenarios:

| Playbook Tag | Test Scenario | What It Verifies |
|-------------|---------------|------------------|
| `validate` | `validate` | Input config exists, credentials synced |
| `prepare` | `prepare` | Containers running, S3 buckets, ports |
| `build` | `build` | S3 images, registry images, build_status |
| `cleanup` | `cleanup` | Containers removed, artifacts cleaned |
| *(none — default)* | `image_build_manager` | Full end-to-end (deploy + verify) |

---

## 2. Repository Structure

### 2.1 Source Code Layout

```
image-build-manager/                    # Repository root
├── src/                                # Ansible source code
│   ├── image_build_manager.yml         # Main playbook (tags: validate, prepare, build, cleanup)
│   ├── input/                          # Input file templates
│   ├── roles/                          # Ansible roles
│   ├── playbooks/                      # Sub-playbooks
│   ├── library/                        # Custom Ansible modules
│   └── vars/                           # Ansible variables
├── config.yml                          # Project config (hostname, domain, admin_nic_ip)
├── docs/design/                        # Design documentation
└── test/                               # Test automation (this framework)
```

### 2.2 Test Framework Layout

```
test/
├── run_validation.sh                   # CLI entry point — scenarios, commands, tab completion
├── setup_env.sh                        # One-time env setup: venv, deps, completion registration
├── conftest.py                         # Pytest hooks: validation, sync, fixtures, report
├── test_config.yml                     # Connection, dataset, sync, report settings
├── test_creds.yml                      # SSH credentials (auto-encrypted with Vault)
├── test_run_config.yml                 # Batch execution: scenario order, markers, suites
├── requirements.txt                    # Python dependencies
│
├── docs/                               # Configuration reference
│   ├── test_config.md
│   ├── test_creds.md
│   └── test_run_config.md
│
├── datasets/                           # Test input datasets
│   └── data_set_01/                    # Default dataset
│       ├── input/                      # Synced → <clone_path>/src/input/<project>/
│       │   ├── config.yml              # Also synced → <clone_path>/config.yml
│       │   ├── image_build_config.yml
│       │   └── image_build_credentials.yml
│       └── repo_manager_output/        # Synced → repo_manager_output_dir (when sync_output: true)
│           ├── repo_status.yml
│           ├── functional_group_packages.yml
│           └── certs/
│
├── library/                            # Reusable automation library
│   ├── __init__.py                     # Module exports
│   ├── functions/                      # ALL verification logic
│   │   ├── host_func.py               # Config, SSH, testinfra, sync
│   │   ├── build_image_func.py         # S3, registry, container checks
│   │   ├── runner_func.py              # run_playbook() — subprocess + ansible-playbook execution
│   │   ├── report_func.py             # HTML + JSON report generation
│   │   ├── formatting_func.py         # Colors, Symbols, TestLogger
│   │   └── validation_func.py         # Config validation — fail fast, no defaults
│   ├── vars/                           # ALL constants
│   │   ├── common_vars.py             # Paths, commands, ports, containers
│   │   └── runner_vars.py             # run_playbook defaults, timeouts, SSH options
│   └── messages/                       # ALL test names, log/assert messages
│       ├── build_image_msgs.py
│       └── runner_msgs.py             # run_playbook log/assertion messages
│
├── fvt/                                # Functional Verification Tests
│   ├── TEST_CASES.md                   # Complete test case registry
│   ├── image_build_manager/            # Full end-to-end (deploy + verify)
│   │   ├── test_playbook.py            # Deploy — no tags (prepare + build)
│   │   ├── container/test_containers.py
│   │   ├── s3/test_s3_images.py
│   │   ├── registry/test_registry_images.py
│   │   └── image_verification/test_image_packages.py
│   ├── validate/                       # --tags validate
│   │   ├── test_playbook.py
│   │   └── status/test_status.py
│   ├── prepare/                        # --tags prepare
│   │   ├── test_playbook.py
│   │   ├── container/test_containers.py
│   │   └── s3/test_s3.py
│   ├── build/                          # --tags build
│   │   ├── test_playbook.py
│   │   ├── s3/test_s3.py
│   │   └── registry/test_registry.py
│   └── cleanup/                        # --tags cleanup
│       ├── test_playbook.py
│       └── cleanup/test_verify_cleanup.py
│
└── reports/                            # Generated HTML + JSON (gitignored)
```

---

## 3. Architecture

### 3.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TEST AUTOMATION ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────────────────┘

  Automation Runner (local machine)           Target Server (OIM)
  ─────────────────────────────────           ──────────────────────
  ┌──────────────────────┐                    ┌───────────────────────────┐
  │ run_validation.sh    │                    │ image_build_manager.yml   │
  │  ├── scenario select │                    │  ├── roles/deploy_minio   │
  │  ├── command routing │                    │  ├── roles/deploy_registry│
  │  └── pytest invoke   │                    │  ├── roles/image_creation │
  └──────────┬───────────┘                    │  └── roles/cleanup        │
             │                                └─────────────┬─────────────┘
             ▼                                              ▲
  ┌──────────────────────┐           SSH / testinfra        │
  │ conftest.py          │──────────────────────────────────┤
  │  ├── validate config │                                  │
  │  ├── encrypt creds   │    ┌──────────────────────────┐  │
  │  ├── clone repo      │    │ run_playbook()           │──┘
  │  ├── sync dataset    │    │  └── ansible-playbook    │
  │  └── init report     │    │     └── live streaming   │
  └──────────┬───────────┘    └──────────────────────────┘
             │
             ▼
  ┌──────────────────────┐    ┌──────────────────────────┐
  │ fvt/<scenario>/      │───>│ library/functions/       │
  │  ├── test_playbook   │    │  ├── build_image_func    │
  │  └── <area>/test_*   │    │  ├── host_func           │
  └──────────────────────┘    │  └── runner_func         │
                              └──────────────────────────┘
```

### 3.2 Connection Modes

| Mode | Config | Host Connection | Playbook Execution | File Sync |
|------|--------|-----------------|-------------------|-----------|
| **Remote** | `oim_server_ip: "10.x.x.x"` | `testinfra ssh://<ip>` | `sshpass + ssh` | `rsync` |
| **Local** | `oim_server_ip: ""` | `testinfra local://` | `subprocess` | `cp / rsync` |

---

## 4. Execution Flow

### 4.1 Entry Point: `run_validation.sh`

```
./run_validation.sh <scenario> <command> [options]
                         │          │         │
                         │          │         ├── --suite <area>    (directory filter)
                         │          │         └── --marker <expr>   (pytest marker filter)
                         │          │
                         │          ├── deploy   → run playbook only
                         │          ├── verify   → run verification tests only
                         │          └── test     → deploy + verify (combined)
                         │
                         ├── image_build_manager   → fvt/image_build_manager/
                         ├── validate              → fvt/validate/
                         ├── prepare               → fvt/prepare/
                         ├── build                 → fvt/build/
                         ├── cleanup               → fvt/cleanup/
                         ├── all                   → all scenarios sequentially
                         ├── list                  → list available scenarios
                         └── --config              → batch from test_run_config.yml
```

### 4.2 Session Lifecycle

```
Phase 1 — Session Setup (conftest.py pytest_sessionstart)
    1. Validate test_config.yml → fail fast if invalid (no fallback defaults)
    2. Encrypt test_creds.yml (if not already encrypted)
    3. Clone/pull repo on target (if remote mode + clone_url set)
    4. Sync dataset input/ → <clone_path>/src/input/<project_name>/
    5. Sync input/config.yml → <clone_path>/config.yml
    6. Sync repo_manager_output/ → repo_manager_output_dir (if sync_output: true)
    7. Initialize TestReport

Phase 2 — Deploy (test_playbook.py — @pytest.mark.deploy)
    1. run_playbook() connects to target
    2. Runs: ansible-playbook image_build_manager.yml [--tags <tag>]
    3. Streams live output with │ prefix
    4. Returns success/failure dict

Phase 3 — Verify (fvt/<scenario>/<area>/test_*.py)
    1. Testinfra connects to target
    2. Calls verification functions (check_*, verify_*)
    3. TestLogger produces structured ✓/✗ output
    4. Results collected by TestReport

Phase 4 — Report (conftest.py pytest_sessionfinish)
    1. TestReport.save() → JSON + HTML
    2. Multiple runs with same report_id merge into single report
```

### 4.3 Data Flow

```
test/datasets/data_set_01/
    ├── input/                              ──rsync──→  <clone_path>/src/input/<project>/
    │   └── config.yml                      ──copy───→  <clone_path>/config.yml
    └── repo_manager_output/                ──rsync──→  <repo_manager_output_dir>/
                                                              │
                                                              ▼
                                                   ansible-playbook image_build_manager.yml
                                                              │
                                                              ▼
                                                   /opt/omnia/image_build_manager/  (runtime output)
```

---

## 5. Configuration

### 5.1 Required Config Fields

All fields must be explicitly set in `test_config.yml`. **No fallback defaults.**

| Field | Type | Description |
|-------|------|-------------|
| `oim_server_ip` | string | Target server IP (empty = local mode) |
| `dataset` | string | Dataset folder name under `datasets/` |
| `project_name` | string | Maps to `<clone_path>/src/input/<project_name>/` |
| `clone_path` | abs path | Repo location on target server |
| `shared_path` | abs path | Runtime persistent storage path |
| `report_path` | string | Report output dir (relative or absolute) |
| `report_name` | string | Report file basename |

### 5.2 Sync Options

| Flag | Default | What It Syncs |
|------|---------|---------------|
| `sync_image_build_input` | `true` | `input/` → target + `config.yml` → clone root |
| `sync_output` | `false` | `repo_manager_output/` → `repo_manager_output_dir` |

### 5.3 Config Validation

Validation runs at session start before any tests. On failure, pytest exits
immediately with all errors listed:

- All required fields present and non-null
- Dataset directory exists with required files
- Paths are absolute where required
- IP format valid (if set)
- `oim_ssh_user` required when remote mode

---

## 6. Library Architecture

### 6.1 Strict Separation Rules

| Layer | Location | Rule |
|-------|----------|------|
| **Messages** | `messages/` | ALL test names, log messages, assertion messages |
| **Variables** | `vars/` | ALL constants: paths, ports, commands, timeouts |
| **Functions** | `functions/` | ALL verification logic (return dict pattern) |
| **Tests** | `fvt/` | Import → call → assert. No business logic |

### 6.2 Core Functions

| File | Key Exports | Purpose |
|------|-------------|---------|
| `host_func.py` | `get_testinfra_host`, `load_test_config`, `sync_*` | Config, connection, dataset sync |
| `build_image_func.py` | `check_container_running`, `check_s3_*`, `check_registry_*` | All verification checks |
| `runner_func.py` | `run_playbook` | Ansible playbook execution via subprocess with live streaming |
| `report_func.py` | `TestReport` | HTML + JSON report generation |
| `formatting_func.py` | `TestLogger`, `Colors`, `Symbols` | Structured terminal output |
| `validation_func.py` | `validate_all`, `ConfigValidationError` | Pre-flight config validation |

### 6.3 Report Architecture

```
report_path/
  └── <report_name>.{json,html}     # Auto-created, supports absolute paths
```

- **Header** — server info, suite, marker, duration
- **Summary** — pass/fail/skip counts
- **Folder Breakdown** — results grouped by test folder
- **Test Details** — expandable per-test results
- **Merge** — same `report_id` across runs merges into one report

---

## 7. Security

- **test_creds.yml** — auto-encrypted with Ansible Vault on first run
- **image_build_credentials.yml** — vault-encrypted in dataset
- **No secrets in code** — all credentials from config files
- **No secrets in git** — `.gitignore` excludes `.key` files
- **SSH** — `StrictHostKeyChecking=no` for automation only

---

## 8. CLI Features

### 8.1 Tab Completion

```bash
eval "$(./run_validation.sh --completion)"
```

Enables bash tab completion for scenarios, commands, `--suite` values, and `--marker` values.
Registered automatically by `setup_env.sh`.

### 8.2 Batch Execution

```yaml
# test_run_config.yml
scenarios:
  image_build_manager:
    order: 1
    run: true
    suite: ""
    marker: "sanity"
```

Run with: `./run_validation.sh --config`

---

## 9. Extensibility

### Adding a New Test Scenario

1. Create `fvt/<scenario_name>/` directory
2. Add `test_playbook.py` at scenario root (deploy with tag)
3. Add `<area>/test_<area>.py` for verification
4. Add test names/messages to `build_image_msgs.py`
5. Add scenario to `test_run_config.yml`
6. Register TC IDs in `fvt/TEST_CASES.md`

### Adding a New Verification Check

1. Add function to `build_image_func.py` (return dict pattern)
2. Add command to `CMDS` in `common_vars.py` (if new shell command)
3. Add messages to `build_image_msgs.py`
4. Create test in appropriate `fvt/` folder
5. Run pylint and verify score ≥ 8.7

---

## 10. Test Case Summary

**38 test cases** across 5 scenarios. Full registry in `fvt/TEST_CASES.md`.

| Scenario | Prefix | Count | Playbook Tag |
|----------|--------|-------|-------------|
| image_build_manager | TC_IB_ | 13 | *(none — prepare + build)* |
| validate | TC_VL_ | 3 | `validate` |
| prepare | TC_PR_ | 8 | `prepare` |
| build | TC_BD_ | 6 | `build` |
| cleanup | TC_CL_ | 8 | `cleanup` |
