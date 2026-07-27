# Copyright 2026 Dell Inc. or its subsidiaries. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Test Automation Library for image_build_manager.

Provides reusable functions, variables, messages, and validation utilities
for FVT (Functional Verification Testing) of the image_build_manager domain.

Structure:
    functions/   - Host connection, config loading, report, runner
    vars/        - Constants, commands, paths
    messages/    - Test names, log/assert messages
    validation/  - Config validation (functions/, vars/, messages/)
"""

# Functions
from .functions import (
    get_testinfra_host,
    is_local_execution,
    load_test_config,
    load_test_credentials,
    TestLogger,
    TestReport,
    PlaybookRunner,
    set_current_report,
    get_current_report,
    get_test_output,
)

# Validation
from .validation import (
    validate_all,
    ConfigValidationError,
)
