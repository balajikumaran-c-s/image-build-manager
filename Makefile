# Copyright 2026 Dell Inc. or its subsidiaries. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

.PHONY: help lint test build clean setup

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup:  ## Install Python and Ansible dependencies
	pip install -r requirements.txt
	ansible-galaxy collection install -r requirements.yml

lint:  ## Run ansible-lint on all playbooks
	cd src && ansible-lint image_build_manager.yml playbooks/*.yml

test:  ## Run unit tests
	python -m pytest src/test/ -v

build:  ## Build per-domain container image
	podman build -t image_build_runner:latest -f src/containers/image_build_runner/Containerfile .

clean:  ## Remove build artifacts and logs
	rm -rf output/ log/ *.retry
