# Image Build Manager — Coding Rules

Rules and conventions for all contributors. Follow these for consistency across
the codebase. Share this file with any developer working on this repository.

---

## 1. Repository Structure

```
image-build-manager/
├── config.yml.sample              # Sample config — users copy to config.yml
├── requirements.txt               # Python deps (ansible-core, jmespath, etc.)
├── requirements.yml               # Ansible Galaxy collections
├── CODING_RULES.md                # This file
├── docs/                          # All documentation (design, migration, contracts)
├── test/                          # Unit + integration tests
└── src/                           # All Ansible code
    ├── ansible.cfg                # Ansible configuration (no hardcoded /opt paths)
    ├── image_build_manager.yml    # Entry point — ONLY role/playbook imports
    ├── roles/                     # One role per responsibility
    ├── playbooks/                 # Sub-playbooks for each flow
    ├── library/                   # Custom Ansible modules
    ├── module_utils/              # Shared Python module utilities
    ├── callback_plugins/          # Output callback
    ├── vars/                      # Shared variables (cross-role)
    └── input/                     # Project input files
```

## 2. Playbook Rules

### Entry Point (`image_build_manager.yml`)
- **NO inline `tasks:` blocks** — use `roles:` or `import_playbook:` only.
- Each play must have a clear step comment (`# Step N: ...`).
- All setup, validation, and data loading belongs in the `image_build_setup` role.

### Sub-Playbooks (`playbooks/`)
- Named by flow: `prepare_*.yml`, `build_image_*.yml`, `cleanup_*.yml`.
- Must NOT duplicate logic already in the setup role (e.g., repo_status loading).
- Each sub-playbook starts with a guard: skip if already done or not applicable.

## 3. Role Rules

### Structure
```
roles/<role_name>/
├── tasks/
│   └── main.yml                   # Entry point
├── vars/
│   └── main.yml                   # ALL error messages, constants, defaults
├── defaults/
│   └── main.yml                   # User-overridable defaults (rare)
├── templates/                     # Jinja2 templates
├── files/                         # Static files
└── handlers/
    └── main.yml                   # Handlers (restart, reload, etc.)
```

### Naming
- Role names: `snake_case`, verb-noun pattern (e.g., `deploy_minio`, `build_os_images`).
- Task file names: `snake_case.yml` (e.g., `fetch_pulp_repos.yml`, `write_build_status.yml`).
- Variable names: `snake_case` (e.g., `repo_manager_output_dir`, `shared_path`).
- Private/internal variables: prefix with `_` (e.g., `_prereq_checks`, `_pulp_cert_check`).

## 4. Variable and Message Rules

### All error messages MUST be in `vars/main.yml`
- **Never** write error messages inline in tasks.
- Define a `*_fail_msg` variable in `vars/main.yml` for every `fail:` or `assert:`.
- Reference the variable: `msg: "{{ repo_status_not_found_fail_msg }}"`.

### Naming conventions for messages
| Suffix | Used in | Example |
|--------|---------|---------|
| `_fail_msg` | `ansible.builtin.fail` | `config_missing_fail_msg` |
| `_warn_msg` | `ansible.builtin.debug` (warnings) | `cert_expiry_warn_msg` |
| `_info_msg` | `ansible.builtin.debug` (info) | `build_completion_info_msg` |

### Variable categories
| Prefix/Pattern | Purpose | Example |
|----------------|---------|---------|
| `*_path` | File or directory path | `repo_manager_output_path` |
| `*_dir` | Directory only | `input_project_dir` |
| `*_file` | File only | `_config_file` (stat register) |
| `*_check` | Stat/validation register | `_pulp_cert_check` |
| `*_list` | List variable | `repo_manager_repos_x86_64` |

## 5. Path Conventions

| Path | Purpose |
|------|---------|
| `<shared_path>/` | Shared path root |
| `<shared_path>/output/<project_name>/` | Project output (build_status.yml) |
| `<shared_path>/log/<project_name>/` | Project logs |
| `<shared_path>/s3/` | MinIO S3 data |
| `<shared_path>/registry/` | Local container registry |
| `<shared_path>/workdir/` | OpenCHAMI build workdir |
| `/opt/omnia/repo_manager/output/<project_name>/` | repo_manager output directory |
| `/opt/omnia/pulp/settings/certs/` | Pulp certificates (absolute, read as-is) |
| `src/input/<project_name>/` | Project input config files |

### Path rules
- **Absolute paths**: Always start with `/`. Used for production paths.
- **Relative paths**: Relative to `playbook_dir` (i.e., `src/`). Used for input/output dirs.
- **Never hardcode `/opt/omnia` in task files** — use variables from config.yml or vars.
- `repo_manager_output_dir` is always a **directory**, not a file path.
- Output and log directories go under `<shared_path>/output/<project_name>/` and `<shared_path>/log/<project_name>/`, NOT under `src/`.

## 6. Ansible Style Guide

### Module usage
- **Always use FQCN**: `ansible.builtin.file`, not `file`.
- **Always use `ansible.builtin.*`** for built-in modules.
- Collections: `containers.podman.*` for Podman, `ansible.utils.*` for IP validation.

### Task conventions
- Every task MUST have a `name:` (no unnamed tasks).
- Task names: sentence case, imperative verb (e.g., "Validate pulp certificate exists").
- Use `become: true` only when root privileges are needed (never at play level).
- Prefer `ansible.builtin.assert` over `fail` + `when` for validation (cleaner output).
- Use `cacheable: true` on `set_fact` when the fact is needed across plays.
- Use `verbosity: 1` or `2` on debug tasks (not shown by default).
- Use `quiet: true` on assert tasks to suppress verbose assertion output.

### Conditional patterns
```yaml
# Good — simple boolean
when: standalone_mode | bool

# Good — variable check
when: repo_manager_output_path | default('') | length > 0

# Bad — nested ternary in when clause
when: "{{ some_complex_ternary }}"
```

### Loop conventions
```yaml
# Always use loop_control with loop_var for clarity
loop: "{{ items | dict2items }}"
loop_control:
  loop_var: item
```

## 7. Validation Rules

### Fail-fast principle
- All prerequisite file checks go in `image_build_setup` role (Step 4).
- Check **all** files before loading any — user sees every missing file at once.
- Use `ansible.builtin.stat` + loop for batch checking.

### Config validation order
1. Check `config.yml` exists
2. Load `config.yml`
3. Validate structure (required keys)
4. Validate values (hostname regex, IPv4 format, absolute path)
5. Set project dirs
6. Check project dir exists
7. Load `image_build_config.yml` (get `repo_manager_output_path`)
8. Stat all prereq files (`repo_status.yml`, `functional_group_packages.yml`)
9. Fail with actionable error messages for each missing file

## 8. Host Configuration

All playbooks run on `localhost` with `connection: local`. There is no remote
host concept, no inventory groups, no SSH to build host.

```yaml
# config.yml
host:
  hostname: "myhost"                         # alphanumeric + hyphens only
  shared_path: "/opt/omnia/image_build_manager"  # absolute path
  domain_name: "local"                       # non-empty string
  admin_nic_ip: "10.20.0.1"                 # valid IPv4
```

Derived paths:
- Output: `<shared_path>/output/<project_name>/`
- Logs: `<shared_path>/log/<project_name>/`

## 9. Git Conventions

- **Branch naming**: `feature/<short-name>` or `fix/<short-name>`
- **Commit messages**: `<type>(<scope>): <description>`
  - Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
  - Example: `feat(setup): add host validation for config.yml`
- **One logical change per commit** — don't mix refactoring with features.

