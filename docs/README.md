# Image Build Manager — Documentation

All project documentation is organized into the folders below.

## Contents

| Folder / File | Description |
|----------------|-------------|
| [design/](design/) | Architecture and design documents |
| [code-style/](code-style/) | Code style guides (Ansible, Python, Jinja2, general) |
| [contracts/](contracts/) | Input/output YAML contracts |
| [migration/](migration/) | Migration history from Omnia mono-repo |
| [architecture.md](architecture.md) | Architecture overview |
| [package-mapping-guide.md](package-mapping-guide.md) | How to customize RPM packages per functional group |
| [troubleshooting.md](troubleshooting.md) | Common issues and fixes |

## Design Documents

| Document | What It Covers |
|----------|---------------|
| [standalone-mode-a.md](design/standalone-mode-a.md) | Mode A bare-metal design — **active mode** |
| [omnia-domain-repo-design.md](design/omnia-domain-repo-design.md) | Generic Omnia domain repo structure & coding standard |
| [image-builder-design.md](design/image-builder-design.md) | Original OpenCHAMI image builder design |
| [standalone-design.md](design/standalone-design.md) | Full standalone repo design (detailed) |

## Code Style Guides

| Guide | What It Covers |
|-------|---------------|
| [ansible.md](code-style/ansible.md) | Playbook structure, FQCN, role layout, linting |
| [python.md](code-style/python.md) | Naming, docstrings, pylint, Ansible module patterns |
| [jinja2.md](code-style/jinja2.md) | Template syntax, filters, whitespace |
| [general.md](code-style/general.md) | Copyright headers, readability, principles |

## Contracts

| Contract | What It Covers |
|----------|---------------|
| [input-contract.md](contracts/input-contract.md) | Required input files, schemas, validation |
| [output-contract.md](contracts/output-contract.md) | Output artifacts (build_status.yml, S3 paths) |

## Quick Links

- **Root README**: [../README.md](../README.md)
- **Coding Rules**: [../CODING_RULES.md](../CODING_RULES.md)
- **Sample Config**: [../config.yml.sample](../config.yml.sample)
