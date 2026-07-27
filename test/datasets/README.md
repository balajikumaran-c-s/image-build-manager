# Datasets

Each dataset is a directory under `datasets/` representing a test configuration
for image_build_manager. The automation framework syncs these files to the target
server before running tests.

## Dataset Structure

```
datasets/
  <dataset_name>/
    config.yml                      # Top-level build configuration
    input/
      image_build_config.yml        # Image build domain input file
```

### Required Files

| File | Description |
|------|-------------|
| `config.yml` | Top-level config: hostname, domain, admin_nic_ip |
| `input/image_build_config.yml` | S3 backend, repo_manager output path, functional groups, ARM host IP |

### Sync Behavior

- **`sync_image_build_input: true`** in `test_config.yml` pushes
  `datasets/<dataset>/input/` to `<clone_path>/src/input/<project_name>/`
  on the target server.
- **`sync_local_repo_output: true`** pushes repo_manager output from
  `local_repo_output_path` to `repo_manager_output_dir` on the target.
- `config.yml` is synced to `<clone_path>/config.yml` alongside input sync.

## Default Dataset: `project_default`

```
datasets/project_default/
  config.yml
  input/
    image_build_config.yml
```

### config.yml

Contains hostname, domain, and admin NIC IP for the target server.
Copy from the target server's existing `config.yml` or create manually.

### input/image_build_config.yml

Contains:
- **s3_configurations**: Provider type (`minio` or `powerscale`), endpoint URL
- **repo_manager_output_dir**: Path to repo_manager output on the target
- **aarch64_inventory_host_ip**: ARM build host IP (empty to skip aarch64)
- **functional_groups**: List of functional groups to build
- **build_image**: Async job timeouts

## Creating a New Dataset

```bash
mkdir -p datasets/my_dataset/input
# Copy and edit the config files:
cp datasets/project_default/config.yml datasets/my_dataset/
cp datasets/project_default/input/image_build_config.yml datasets/my_dataset/input/
# Edit as needed, then update test_config.yml:
#   dataset: "my_dataset"
```
