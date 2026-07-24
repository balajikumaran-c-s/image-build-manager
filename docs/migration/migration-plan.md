# Image Build Manager — Migration & Validation Plan

## Status: COMPLETE

---

## 1. openchami_vars_suppport Removal ✅ DONE

**Finding**: `openchami_vars.yml` contains vars (`cluster_env_key`, `cert_wait_time`, `openchami_auth_retries`, etc.) used **only** by `orchestrator/tasks/openchami_auth.yml`. Image_build_manager never uses them.

**Action taken**: Removed `openchami_vars_suppport: true` from all image_build_manager playbooks.

**Broken reference found**: `build_image_x86_64.yml` and `build_image_aarch64.yml` reference `common/tasks/common/openchami_auth.yml` — **this file does not exist**. The actual file is at `orchestrator/tasks/openchami_auth.yml`. This needs to be fixed or the openchami_auth task needs to be moved to `common/tasks/common/`.

---

## 2. Main Flow Guard (`image_build_main_flow`) ✅ DONE

**Pattern**: `image_build_manager.yml` sets `image_build_main_flow: true` at startup. Sub-playbooks check `when: not (image_build_main_flow | default(false) | bool)` to skip:
- `include_input_dir.yml` import
- `image_build_credentials.yml` import

This prevents duplicate execution when sub-playbooks are called from the main entry point vs standalone.

---

## 3. Input Validation for image_build_manager

### Current State
- Central `validate_config.yml` → `validate_input` module → `common/library/module_utils/input_validation/`
- Schemas already exist: `image_build_config.json`, `image_build_credentials.json`, `functional_groups_config.json`
- `build_image_x86_64.yml` and `build_image_aarch64.yml` already call `validate_config.yml`
- `validate_build_config` role exists in image_build_manager for L2 validation (file existence checks)

### Plan: Add image_build-specific validation sub-playbook + role

#### Step 1: Create validation sub-playbook
```
src/image_build_manager/playbooks/validate_image_build_config.yml
```
- Calls `image_build_setup` (standalone guard)
- Calls the `validate_image_build_input` role (new)
- Can be run standalone: `ansible-playbook validate_image_build_config.yml`

#### Step 2: Create `validate_image_build_input` role
```
src/image_build_manager/roles/validate_image_build_input/
├── tasks/
│   └── main.yml          # L1 (schema) + L2 (logic) validation
├── vars/
│   └── main.yml          # Validation messages
├── library/              # Role-level Ansible modules (auto-discovered)
│   └── validate_image_build_config.py   # Python module for image_build-specific validation
└── module_utils/         # Role-level module utils
    └── image_build_validation/
        ├── __init__.py
        ├── schema/
        │   ├── image_build_config.json        # MOVED from common
        │   ├── image_build_credentials.json   # MOVED from common
        │   └── functional_groups_config.json  # MOVED from common
        └── image_build_validation_flow.py  # image_build-specific validation logic
```

#### Step 3: Validation levels
- **L1 (Schema)**: JSON schema validation of `image_build_config.yml`, `image_build_credentials.yml`, `functional_groups_config.yml`
- **L2 (Logic)**: Cross-field validation (e.g., if provider=powerscale then endpoint_url required; if aarch64 build then aarch64_inventory_host_ip required)
- **L3 (Runtime)**: File existence, connectivity checks (existing `validate_build_config` role)

#### Step 4: Integration
- `build_image_x86_64.yml` and `build_image_aarch64.yml` call `validate_image_build_input` instead of the central `validate_config.yml` for image_build-specific tags
- Central `validate_config.yml` can still call image_build validation via its tag system

---

## 4. Move Library & Modules from `src/common` to `image_build_manager`

### What to Move (image_build-exclusive)

| Source (in `src/common/`) | Target (in `src/image_build_manager/`) | Reason |
|---|---|---|
| `library/modules/base_image_package_collector.py` | `library/modules/` | Only used by image_build_manager |
| `library/modules/image_package_collector.py` | `library/modules/` | Only used by image_build_manager |
| `library/modules/functional_group_parser.py` | `library/modules/` | Only used by image_build_manager |
| `library/module_utils/build_image/` | `library/module_utils/build_image/` | Only used by image_build modules |
| `library/module_utils/input_validation/schema/image_build_config.json` | `library/module_utils/image_build_validation/schema/` | image_build-specific schema |
| `library/module_utils/input_validation/schema/image_build_credentials.json` | `library/module_utils/image_build_validation/schema/` | image_build-specific schema |
| `library/module_utils/input_validation/schema/functional_groups_config.json` | `library/module_utils/image_build_validation/schema/` | image_build-specific schema |

### What to KEEP in `src/common` (shared across domains)

| File | Why |
|---|---|
| `library/modules/generate_functional_groups.py` | Used by both image_build_manager and orchestrator |
| `library/modules/validate_input.py` | Central validation framework for all domains |
| `library/module_utils/input_validation/common_utils/` | Shared validation utilities |
| `library/module_utils/input_validation/validation_flows/common_validation.py` | Shared validation logic |
| `vars/common_vars.yml` | Used everywhere (permissions, retries) |
| `callback_plugins/omnia_default.py` | Global callback |

### How Ansible Finds Role-Level Libraries

Ansible automatically searches for `library/` and `module_utils/` directories **within a role**:

```
roles/fetch_packages/
├── library/                    # Auto-discovered by Ansible
│   ├── base_image_package_collector.py
│   ├── image_package_collector.py
│   └── functional_group_parser.py
├── module_utils/               # Auto-discovered by Ansible
│   └── build_image/
│       ├── __init__.py
│       ├── common_functions.py
│       └── config.py
└── tasks/
    └── main.yml
```

**Important**: Modules in role-level `library/` are only available **within that role's tasks**. If the same module is needed in multiple roles, either:
1. Keep it in `src/common/library/modules/` (global)
2. Use a "shared" role that other roles depend on
3. Duplicate the module (not recommended)

### Migration Steps

1. **Create role-level `library/` and `module_utils/` directories** in target roles
2. **Copy files** from `src/common/` to the target role
3. **Update imports** in the moved Python files if any `module_utils` paths change
4. **Test** that the role still discovers the modules correctly
5. **Remove originals** from `src/common/` after confirming no other domain uses them
6. **Update `src/common/README.md`** to reflect the migration

### Module Utils Import Path Change

When moving `module_utils/build_image/` to a role-level directory, Python imports change:

**Before** (global):
```python
from ansible.module_utils.build_image.common_functions import fn
```

**After** (role-level — same import path, Ansible resolves it):
```python
from ansible.module_utils.build_image.common_functions import fn
```

Ansible merges role-level `module_utils/` with global `module_utils/`, so **import paths remain the same** as long as there's no naming conflict.

---

## 5. Broken Reference Fix Needed

**`build_image_x86_64.yml:176`** and **`build_image_aarch64.yml:196`**:
```yaml
ansible.builtin.include_tasks: "{{ playbook_dir }}/../../common/tasks/common/openchami_auth.yml"
```

This file **does not exist** at `common/tasks/common/openchami_auth.yml`. The actual file is at `orchestrator/tasks/openchami_auth.yml`.

**Options**:
1. Copy `openchami_auth.yml` to `common/tasks/common/` (if shared)
2. Create an image_build_manager-local copy at `roles/image_creation/tasks/openchami_auth.yml`
3. Fix the path to point to `orchestrator/tasks/`

---

## 6. Library Location: Domain Folder vs Role-Level

### Comparison

| Approach | Pros | Cons |
|----------|------|------|
| **Domain folder** (`image_build_manager/library/`) | Single location for all image_build Python code; all roles can use it; mirrors `src/common/library/` pattern; `ansible.cfg` controls path | Requires `ansible.cfg` update or CLI `-M` flag |
| **Role-level** (`roles/fetch_packages/library/`) | Zero config — Ansible auto-discovers; no `ansible.cfg` changes | Code fragmented across roles; if 2 roles need the same module → duplication; modules only visible within that role |

### Recommendation: **Domain Folder** (image_build_manager-level)

Place image_build-specific Python code at the domain level, mirroring how `src/common/library/` works:

```
src/image_build_manager/
├── library/                            # image_build-specific Ansible modules
│   ├── modules/
│   │   ├── base_image_package_collector.py
│   │   ├── image_package_collector.py
│   │   ├── functional_group_parser.py
│   │   └── validate_image_build_config.py       # NEW — image_build validation module
│   └── module_utils/
│       ├── build_image/                 # MOVED from common
│       │   ├── __init__.py
│       │   ├── common_functions.py
│       │   └── config.py
│       └── image_build_validation/              # NEW — image_build validation helpers
│           ├── __init__.py
│           ├── schema/
│           │   ├── image_build_config.json
│           │   ├── image_build_credentials.json
│           │   └── functional_groups_config.json
│           └── image_build_validation_flow.py
```

**Why domain folder is better**:
1. All roles under `image_build_manager/roles/` can access modules in `image_build_manager/library/`
2. Single place to maintain Python code — no duplication
3. Mirrors the existing `src/common/library/` pattern used by the project
4. Clean separation: `src/common/library/` = shared, `src/image_build_manager/library/` = image_build-specific
5. When multiple roles (e.g., `fetch_packages`, `validate_image_build_input`, `image_creation`) need the same module, it's in one place

**ansible.cfg change needed**:
```ini
library = src/common/library/modules:src/image_build_manager/library/modules
module_utils = src/common/library/module_utils:src/image_build_manager/library/module_utils
```

Ansible supports colon-separated paths (like `$PATH`), so both locations are searched.

---

## 7. Target Structure After Migration

```
src/image_build_manager/
├── image_build_manager.yml          # Main entry point (sets image_build_main_flow)
├── ansible.cfg                      # Domain-specific config with local + common library paths
├── library/                         # image_build-specific Python code (domain-level)
│   ├── MIGRATED_FROM_COMMON.md      # Tracks what was copied and removal plan
│   ├── modules/
│   │   ├── base_image_package_collector.py   # COPIED from common
│   │   ├── image_package_collector.py        # COPIED from common
│   │   ├── functional_group_parser.py        # COPIED from common
│   │   └── validate_image_build_config.py    # NEW — image_build L1+L2 validation module
│   └── module_utils/
│       └── image_build_validation/           # NEW — image_build validation helpers
│           ├── __init__.py
│           ├── schema/
│           │   ├── image_build_config.json   # COPIED from common
│           │   ├── image_build_credentials.json
│           │   └── functional_groups_config.json
│           └── image_build_validation_flow.py
├── playbooks/
│   ├── prepare_image_build_manager.yml
│   ├── build_image_x86_64.yml
│   ├── build_image_aarch64.yml
│   ├── cleanup_image_build_manager.yml
│   ├── image_build_credentials.yml
│   ├── validate_image_build_config.yml  # NEW — standalone validation sub-playbook
│   ├── upgrade_image_build_manager.yml
│   └── rollback_image_build_manager.yml
├── roles/
│   ├── deploy_minio/
│   ├── deploy_registry/
│   ├── image_build_credentials/
│   ├── image_build_setup/               # Replaces utils imports
│   ├── image_build_functional_groups/   # Replaces utils generate_functional_groups
│   ├── image_creation/
│   ├── cleanup_image_build_manager/
│   ├── validate_build_config/           # Existing L2/L3 validation (runtime checks)
│   ├── validate_image_build_input/      # NEW — L1 schema + L2 logic validation role
│   │   ├── tasks/main.yml
│   │   └── vars/main.yml
│   ├── fetch_packages/
│   │   ├── tasks/
│   │   └── vars/
│   └── prepare_arm_node/
└── vars/

NOTE: module_utils/build_image/ stays in src/common/ (shared with orchestrator).
```

---

## Execution Order

1. ✅ Remove `openchami_vars_suppport` from image_build playbooks
2. ✅ Add `image_build_main_flow` guard
3. ✅ Remove `tags: always` from sub-playbooks
4. ✅ Remove `enable_build_stream_flag` duplication
5. ✅ Add `default(false)` to all `enable_build_stream` references
6. ✅ Fix broken `openchami_auth.yml` reference (created in common/tasks/common/)
7. ✅ Fix `omnia_run_tags` not set → all-domain validation
8. ✅ Fix `software_config` not loaded when `enable_build_stream=false`
9. ✅ Set `skip_subscription_check` fact for image_build flows
10. ✅ Create `image_build_setup` role — replaces `upgrade_checkup.yml` + `include_input_dir.yml` + `create_container_group.yml`
11. ✅ Create `image_build_functional_groups` role — replaces `generate_functional_groups.yml`
12. ✅ Update `image_build_manager.yml` to use `image_build_setup` role
13. ✅ Update all sub-playbooks (`prepare`, `build_x86_64`, `build_aarch64`, `cleanup`, `credentials`) to use `image_build_setup`/`image_build_functional_groups`
14. ✅ Remove ALL `../../playbooks/utils/` imports from image_build_manager — zero remaining
15. ✅ Rename all `ibm_` prefixed roles, variables, and files to `image_build_` to avoid trademark confusion
16. ✅ Create `image_build_manager/library/` directory structure (modules/, module_utils/image_build_validation/)
17. ✅ Copy image_build-exclusive modules from `src/common/library/modules/` (base_image_package_collector, image_package_collector, functional_group_parser)
18. ⚠️ Keep `module_utils/build_image/` in common — shared with `additional_images_collector.py` (orchestrator)
19. ✅ Copy image_build-specific schemas to `library/module_utils/image_build_validation/schema/`
20. ✅ Update `ansible.cfg` with colon-separated library paths (`library/modules:../common/library/modules`)
21. ✅ Create `validate_image_build_input` role with L1 schema + L2 logic validation
22. ✅ Create `validate_image_build_config.yml` sub-playbook (standalone and embedded)
23. ✅ Removed moved modules from `src/common/` — see `library/MIGRATED_FROM_COMMON.md`
