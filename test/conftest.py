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
Pytest configuration for image_build_manager FVT.

Provides:
- host fixture (testinfra connection to target)
- Custom markers: x86_64, aarch64, sanity, functional, deploy
- Marker expression: '+' for AND, ',' for OR
- Test ordering via @pytest.mark.order(n)
- Credential auto-encryption
- Remote clone and dataset sync on session startup
"""

import sys
import os

import pytest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

from library import (
    get_testinfra_host,
    is_local_execution,
    load_test_config,
    TestReport,
    set_current_report,
    get_current_report,
    get_test_output,
)
from library.functions.host_func import (
    encrypt_test_credentials,
    clone_repo_on_remote,
    sync_image_build_input,
    sync_config_to_remote,
)
from library.functions.formatting_func import log


# =============================================================================
# CUSTOM CLI OPTIONS
# =============================================================================

def pytest_addoption(parser):
    """Add --marker option for custom marker expression filtering."""
    parser.addoption(
        "--marker",
        action="store",
        default="",
        help=(
            "Marker filter expression. "
            "Use '+' for AND (both required): x86_64+sanity. "
            "Use ',' for OR (either matches): x86_64,aarch64."
        ),
    )


# =============================================================================
# MARKER REGISTRATION
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "filterwarnings", "ignore::pytest.PytestCollectionWarning"
    )
    markers = {
        "order(n)": "Specify test execution order (lower first)",
        "x86_64": "Test applies to x86_64 architecture",
        "aarch64": "Test applies to aarch64 architecture",
        "sanity": "Baseline verification (must-pass)",
        "functional": "Functional verification",
        "regression": "Regression tests",
        "deploy": "Playbook deployment tests",
    }
    for name, desc in markers.items():
        config.addinivalue_line("markers", f"{name}: {desc}")


# =============================================================================
# MARKER EXPRESSION FILTERING
# =============================================================================

def _parse_marker_expression(expr):
    """Parse marker expression into (mode, marker_list).

    '+' => AND (all markers must be present)
    ',' => OR  (any marker must be present)
    Single marker => exact match

    Returns:
        Tuple of ('and'|'or'|'single', list_of_markers)
    """
    expr = expr.strip()
    if not expr:
        return ("none", [])
    if "+" in expr:
        return ("and", [m.strip() for m in expr.split("+")])
    if "," in expr:
        return ("or", [m.strip() for m in expr.split(",")])
    return ("single", [expr])


def _item_has_marker(item, marker_name):
    """Check if a test item has a specific marker."""
    return item.get_closest_marker(marker_name) is not None


def pytest_collection_modifyitems(session, config, items):
    """Filter by --marker expression and sort by order marker."""
    marker_expr = config.getoption("--marker", default="")
    mode, markers = _parse_marker_expression(marker_expr)

    if mode != "none" and markers:
        filtered = []
        for item in items:
            if mode == "and":
                if all(_item_has_marker(item, m) for m in markers):
                    filtered.append(item)
                else:
                    item.add_marker(pytest.mark.skip(
                        reason=(
                            f"Missing marker(s) for AND expression: "
                            f"{'+'.join(markers)}"
                        )
                    ))
                    filtered.append(item)
            elif mode == "or":
                if any(_item_has_marker(item, m) for m in markers):
                    filtered.append(item)
                else:
                    item.add_marker(pytest.mark.skip(
                        reason=(
                            f"No matching marker for OR expression: "
                            f"{','.join(markers)}"
                        )
                    ))
                    filtered.append(item)
            elif mode == "single":
                if _item_has_marker(item, markers[0]):
                    filtered.append(item)
                else:
                    item.add_marker(pytest.mark.skip(
                        reason=f"Missing marker: {markers[0]}"
                    ))
                    filtered.append(item)
        items[:] = filtered

    def _get_order(item):
        marker = item.get_closest_marker("order")
        if marker and marker.args:
            return marker.args[0]
        return 999

    items.sort(key=_get_order)


# =============================================================================
# SESSION STARTUP — ENCRYPT, CLONE, SYNC
# =============================================================================

def pytest_sessionstart(session):
    """Session startup: encrypt credentials, clone repo, sync files, init report."""
    try:
        encrypt_test_credentials()
    except (ValueError, OSError):
        pass

    config = load_test_config()
    host = get_testinfra_host()

    if not is_local_execution():
        clone_result = clone_repo_on_remote(host)
        if clone_result["success"]:
            log(clone_result["details"], "OK")
        else:
            log(f"Clone failed: {clone_result['error']}", "ERROR")

    if config.get("sync_image_build_input", False):
        sync_result = sync_image_build_input(host)
        if sync_result["success"]:
            log(sync_result["details"], "OK")
        else:
            log(
                f"Input sync failed: {sync_result['error']}",
                "ERROR",
            )

        cfg_result = sync_config_to_remote(host)
        if cfg_result["success"]:
            log(cfg_result["details"], "OK")
        else:
            log(
                f"Config sync failed: {cfg_result['error']}",
                "WARN",
            )

    # Initialize test report
    module_name = "image_build_manager"
    test_paths = session.config.args if hasattr(session.config, 'args') else []
    for p in test_paths:
        for part in p.replace("\\", "/").split("/"):
            if part.startswith("image_build_"):
                module_name = part
                break

    report_id = os.environ.get("REPORT_ID")
    report = TestReport(module_name, report_id)
    set_current_report(report)


def pytest_sessionfinish(session, exitstatus):
    """Save report after all tests complete."""
    report = get_current_report()
    if report and report.results:
        report.save()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture test results and output for the HTML report."""
    outcome = yield
    result = outcome.get_result()

    report = get_current_report()
    if not report:
        return

    if result.when not in {"call", "setup"}:
        return

    if result.when == "setup" and not result.skipped:
        return

    status = "PASSED" if result.passed else (
        "SKIPPED" if result.skipped else "FAILED"
    )

    output = get_test_output(item.name)
    details = output if output else ""
    skip_reason = ""

    if result.skipped:
        if hasattr(result, "wasxfail"):
            status = "SKIPPED"
        rep_text = str(result.longrepr) if result.longrepr else ""
        if "Skipped:" in rep_text:
            skip_reason = rep_text.split("Skipped:", 1)[-1].strip()
        elif "SKIP" in rep_text:
            skip_reason = rep_text.split("SKIP", 1)[-1].strip()

    if status == "SKIPPED" and skip_reason:
        details = (
            (details + "\n" if details else "")
            + f"SKIPPED: {skip_reason}"
        )

    report.add_result({
        "test_name": item.name,
        "status": status,
        "duration": getattr(result, "duration", 0),
        "details": details,
        "error": str(result.longrepr) if result.failed else "",
    })


# =============================================================================
# HOST FIXTURE
# =============================================================================

@pytest.fixture(scope="session")
def host():
    """Testinfra host connected to the target server."""
    return get_testinfra_host()
