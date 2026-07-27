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
Formatting utilities for the image_build_manager test module.

Contains:
- Colors: ANSI color codes for terminal output
- Symbols: Unicode symbols for status indicators
- log(): Simple timestamped logging
- TestLogger: Structured test output logger
"""

import os
import sys
from datetime import datetime


def _supports_color() -> bool:
    """Check if terminal supports ANSI colors."""
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    term = os.environ.get("TERM", "")
    if term == "dumb":
        return False
    return True


_USE_COLOR = _supports_color()


# =============================================================================
# ANSI COLOR CODES
# =============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m" if _USE_COLOR else ""
    BOLD = "\033[1m" if _USE_COLOR else ""
    DIM = "\033[2m" if _USE_COLOR else ""

    RED = "\033[31m" if _USE_COLOR else ""
    GREEN = "\033[32m" if _USE_COLOR else ""
    YELLOW = "\033[33m" if _USE_COLOR else ""
    BLUE = "\033[34m" if _USE_COLOR else ""
    CYAN = "\033[36m" if _USE_COLOR else ""
    GRAY = "\033[90m" if _USE_COLOR else ""

    BRIGHT_RED = "\033[91m" if _USE_COLOR else ""
    BRIGHT_GREEN = "\033[92m" if _USE_COLOR else ""
    BRIGHT_YELLOW = "\033[93m" if _USE_COLOR else ""
    BRIGHT_BLUE = "\033[94m" if _USE_COLOR else ""
    BRIGHT_CYAN = "\033[96m" if _USE_COLOR else ""


# =============================================================================
# UNICODE SYMBOLS
# =============================================================================

class Symbols:
    """Unicode symbols for status indicators."""
    CHECK = "\u2714"
    CROSS = "\u2718"
    ARROW = "\u2192"
    SKIP = "\u21b7"
    TRIANGLE = "\u25b6"
    PIPE = "\u2502"


# =============================================================================
# LOGGING
# =============================================================================

_debug_mode = False


def set_debug_mode(enabled: bool) -> None:
    """Enable or disable debug mode globally."""
    global _debug_mode
    _debug_mode = enabled


def log(message: str, level: str = "INFO") -> None:
    """Print log message with timestamp and color."""
    if level == "DEBUG" and not _debug_mode:
        return

    timestamp = datetime.now().strftime("%H:%M:%S")
    level_colors = {
        "INFO": Colors.BRIGHT_BLUE,
        "DEBUG": Colors.GRAY,
        "WARN": Colors.BRIGHT_YELLOW,
        "ERROR": Colors.BRIGHT_RED,
        "OK": Colors.BRIGHT_GREEN,
    }
    color = level_colors.get(level, "")
    print(f"{color}[{timestamp}] [{level}] {message}{Colors.RESET}")


# =============================================================================
# TEST LOGGER
# =============================================================================

_last_output = ""

MAX_LINE_WIDTH = 100


def get_test_output(test_name: str = None) -> str:  # pylint: disable=unused-argument
    """Get captured output for the last test."""
    return _last_output


class TestLogger:
    """
    Structured test output logger for pytest validation tests.

    Usage:
        log = TestLogger("Verify S3 images pushed")
        log.check("Checking bucket...")
        log.passed("All images found", "details here")
    """

    def __init__(self, test_name: str, tc_id: str = ""):
        global _last_output  # pylint: disable=global-variable-not-assigned
        self.test_name = test_name
        self.tc_id = tc_id
        self._output_lines = []
        self._add_line("")
        id_part = f" [{tc_id}]" if tc_id else ""
        header = (
            f"  {Colors.BRIGHT_CYAN}{Colors.BOLD}"
            f"{Symbols.TRIANGLE}{id_part} {test_name}{Colors.RESET}"
        )
        self._add_line(header)

    def _add_line(self, line: str):
        """Add line to output and print."""
        global _last_output
        self._output_lines.append(line)
        print(line, flush=True)
        _last_output = "\n".join(self._output_lines)

    def check(self, message: str):
        """Log check being performed."""
        self._add_line(
            f"  {Colors.BRIGHT_YELLOW}{Symbols.ARROW}"
            f"{Colors.RESET} {message}"
        )

    def info(self, message: str):
        """Log informational message."""
        self._add_line(
            f"  {Colors.BRIGHT_BLUE}{Symbols.ARROW}"
            f"{Colors.RESET} {message}"
        )

    @staticmethod
    def _truncate(line: str, max_w: int = MAX_LINE_WIDTH) -> str:
        """Truncate a detail line to max width."""
        if len(line) > max_w:
            return line[:max_w - 3] + "..."
        return line

    def passed(self, message: str, details: str = None):
        """Log passed result."""
        self._add_line(
            f"  {Colors.BRIGHT_GREEN}{Symbols.CHECK} PASS:"
            f"{Colors.RESET} {self._truncate(message)}"
        )
        if details:
            for line in details.split('\n'):
                self._add_line(
                    f"    {Colors.GRAY}{Symbols.PIPE}"
                    f"{Colors.RESET} {self._truncate(line)}"
                )

    def skipped(self, message: str, details: str = None):
        """Log skipped result."""
        self._add_line(
            f"  {Colors.BRIGHT_YELLOW}{Symbols.SKIP} SKIP:"
            f"{Colors.RESET} {self._truncate(message)}"
        )
        if details:
            for line in details.split('\n'):
                self._add_line(
                    f"    {Colors.GRAY}{Symbols.PIPE}"
                    f"{Colors.RESET} {self._truncate(line)}"
                )
        else:
            self._add_line(
                f"    {Colors.GRAY}{Symbols.PIPE}"
                f"{Colors.RESET} {Colors.DIM}Skipped{Colors.RESET}"
            )

    def failed(self, message: str, details: str = None):
        """Log failed result."""
        self._add_line(
            f"  {Colors.BRIGHT_RED}{Symbols.CROSS} FAIL:"
            f"{Colors.RESET} {self._truncate(message)}"
        )
        if details:
            for line in details.split('\n'):
                self._add_line(
                    f"    {Colors.GRAY}{Symbols.PIPE}"
                    f"{Colors.RESET} {self._truncate(line)}"
                )

    def get_output(self) -> str:
        """Get all captured output."""
        return "\n".join(self._output_lines)
