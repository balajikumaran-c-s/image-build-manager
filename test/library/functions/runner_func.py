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
PlaybookRunner — live output streaming for image_build_manager.

Runs ansible-playbook directly on the target host (bare-metal, no
container exec) with live output streaming.

Usage::

    runner = PlaybookRunner()
    result = runner.run("image_build_manager.yml", tag="prepare")
    assert result["success"], result["error"]
"""

import os
import re
import shutil
import signal
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

from .host_func import (
    load_test_config,
    load_test_credentials,
    is_local_execution,
)
from .formatting_func import TestLogger, Colors, Symbols
from ..vars.runner_vars import (
    DEFAULT_VERBOSITY,
    DEFAULT_TIMEOUT,
    LINE_WIDTH,
    SSH_OPTIONS,
)
from ..vars.common_vars import (
    PLAYBOOK_ENTRY_POINT,
    PLAYBOOK_WORKDIR,
)
from ..messages.runner_msgs import (
    RUNNER_LOG_MSGS,
    RUNNER_ASSERT_MSGS,
)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\r")


class PlaybookRunner:
    """Runs ansible-playbook on the target host with live streaming.

    Supports two execution modes:
      - **Local mode**: Runs commands directly on this machine.
      - **Remote mode**: Wraps commands inside SSH via ``sshpass``.

    Args:
        verbosity: Ansible verbosity level 0-4 (default: 1).
        timeout: Max seconds to wait for completion (default: 7200).
    """

    def __init__(
        self,
        verbosity: int = DEFAULT_VERBOSITY,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self._verbosity = verbosity
        self._timeout = timeout

        self._config = load_test_config()
        self._credentials = load_test_credentials()
        self._local_mode = is_local_execution()

    def run(
        self,
        playbook: Optional[str] = None,
        tag: Optional[str] = None,
        workdir: Optional[str] = None,
        extra_vars: Optional[Dict[str, str]] = None,
        verbosity: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run an ansible-playbook with the given tag.

        Args:
            playbook: Playbook filename (default: image_build_manager.yml).
            tag: Ansible tag (prepare, build, validate, cleanup).
            workdir: Working directory (default: <clone_path>/src/).
            extra_vars: Extra --extra-vars key=value pairs.
            verbosity: Override instance verbosity for this run.
            timeout: Override instance timeout for this run.

        Returns:
            Dict with success, rc, output, duration, error, playbook.
        """
        v = verbosity if verbosity is not None else self._verbosity
        t = timeout if timeout is not None else self._timeout

        clone_path = self._config["clone_path"]
        if playbook is None:
            playbook = PLAYBOOK_ENTRY_POINT
        if workdir is None:
            workdir = f"{clone_path}/{PLAYBOOK_WORKDIR}"

        log = TestLogger("playbook_runner")

        if not self._local_mode and not shutil.which("sshpass"):
            return self._fail(
                playbook, 0.0,
                RUNNER_ASSERT_MSGS["sshpass_missing"],
            )

        ansible_cmd = self._build_ansible_cmd(
            playbook, workdir, v, extra_vars, tag,
        )
        cmd = self._wrap_for_execution(ansible_cmd)

        if self._local_mode:
            log.check(RUNNER_LOG_MSGS["connecting_local"])
        else:
            host = self._config["oim_server_ip"]
            port = self._config.get("oim_ssh_port", 22)
            log.check(RUNNER_LOG_MSGS["connecting_remote"].format(
                host=host, port=port,
            ))

        log.check(RUNNER_LOG_MSGS["starting_playbook"].format(
            playbook=playbook, tag=tag or "all",
        ))
        log.check(RUNNER_LOG_MSGS["streaming_output"])

        return self._stream_execute(cmd, playbook, t, tag)

    def run_shell(
        self,
        command: str,
        label: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run a shell command on the target host with live streaming.

        Args:
            command: Shell command to execute.
            label: Human-readable label for logging.
            timeout: Max seconds to wait.

        Returns:
            Dict with success, rc, output, duration, error.
        """
        t = timeout if timeout is not None else self._timeout
        display = label or command
        log = TestLogger("shell_runner")

        if not self._local_mode and not shutil.which("sshpass"):
            return self._fail(
                display, 0.0,
                RUNNER_ASSERT_MSGS["sshpass_missing"],
            )

        cmd = self._wrap_for_execution(command)

        if self._local_mode:
            log.check(RUNNER_LOG_MSGS["connecting_local"])
        else:
            host = self._config["oim_server_ip"]
            port = self._config.get("oim_ssh_port", 22)
            log.check(RUNNER_LOG_MSGS["connecting_remote"].format(
                host=host, port=port,
            ))

        log.check(RUNNER_LOG_MSGS["streaming_output"])
        return self._stream_execute(cmd, display, t)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_ansible_cmd(
        self,
        playbook: str,
        workdir: str,
        verbosity: int,
        extra_vars: Optional[Dict[str, str]],
        tag: Optional[str],
    ) -> str:
        """Build the ansible-playbook command string."""
        v_flag = f" -{('v' * verbosity)}" if verbosity > 0 else ""

        parts = [
            f"cd {workdir} &&",
            f"ansible-playbook {playbook}{v_flag}",
        ]

        if extra_vars:
            for key, val in extra_vars.items():
                parts.append(f'--extra-vars "{key}={val}"')
        if tag:
            parts.append(f"--tags {tag}")

        return " ".join(parts)

    def _wrap_for_execution(self, cmd: str) -> str:
        """Wrap command for local or remote (SSH) execution."""
        if self._local_mode:
            return cmd

        host = self._config["oim_server_ip"]
        user = self._config["oim_ssh_user"]
        port = str(self._config.get("oim_ssh_port", 22))
        password = self._credentials.get("oim_password", "")

        ssh_parts = [
            "sshpass", f"-p '{password}'",
            "ssh", "-tt",
        ] + SSH_OPTIONS + [
            "-p", port,
            f"{user}@{host}",
            f"'{cmd}'",
        ]
        return " ".join(ssh_parts)

    def _stream_execute(
        self, cmd: str, playbook: str, timeout: int,
        tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute command, stream stdout live, return result."""
        pipe_prefix = (
            f"    {Colors.GRAY}{Symbols.PIPE}{Colors.RESET} "
        )
        output_lines: List[str] = []
        start = time.time()
        process = None

        def _read_output():
            try:
                for raw_line in process.stdout:
                    clean = _ANSI_RE.sub(
                        "", raw_line
                    ).rstrip("\n\r")
                    output_lines.append(clean)
                    if not clean:
                        print(pipe_prefix, flush=True)
                        continue
                    while clean:
                        chunk = clean[:LINE_WIDTH]
                        clean = clean[LINE_WIDTH:]
                        print(
                            f"{pipe_prefix}{chunk}", flush=True,
                        )
            except (ValueError, OSError):
                pass

        try:
            process = subprocess.Popen(
                ["bash", "-c", cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                text=True,
                preexec_fn=os.setsid,
            )

            reader = threading.Thread(
                target=_read_output, daemon=True,
            )
            reader.start()

            process.wait(timeout=timeout)
            reader.join(timeout=5)

            duration = time.time() - start
            rc = process.returncode

            if rc == 0:
                return {
                    "success": True,
                    "rc": rc,
                    "output": "\n".join(output_lines),
                    "duration": duration,
                    "error": None,
                    "playbook": playbook,
                }

            return self._fail(
                playbook, duration,
                RUNNER_ASSERT_MSGS["playbook_failed"].format(
                    playbook=playbook,
                    tag=tag or "all",
                    rc=rc, duration=duration,
                    log_path="/opt/omnia/image_build_manager/log/",
                    workdir=self._config.get(
                        "clone_path", ""
                    ) + "/src",
                ),
                rc=rc,
                output="\n".join(output_lines),
            )

        except KeyboardInterrupt:
            duration = time.time() - start
            self._kill_process_group(process)
            print(
                f"\n{pipe_prefix}"
                f"{Colors.BRIGHT_YELLOW}Cancelled by user"
                f"{Colors.RESET}",
                flush=True,
            )
            return self._fail(
                playbook, duration,
                "Command cancelled by user (Ctrl+C)",
                rc=-2, output="\n".join(output_lines),
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start
            self._kill_process_group(process)
            return self._fail(
                playbook, duration,
                RUNNER_ASSERT_MSGS["playbook_timeout"].format(
                    playbook=playbook, timeout=timeout,
                ),
                rc=-1, output="\n".join(output_lines),
            )

        except OSError:
            duration = time.time() - start
            self._kill_process_group(process)
            return self._fail(
                playbook, duration,
                "Command execution encountered an OS error",
                rc=-1, output="\n".join(output_lines),
            )

        finally:
            self._cleanup_process(process)

    @staticmethod
    def _kill_process_group(process):
        """Kill the entire process group."""
        if process is None:
            return
        try:
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            pass
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=3)
        except (subprocess.TimeoutExpired, OSError):
            pass

    @staticmethod
    def _cleanup_process(process):
        """Close all open streams on a process."""
        if process is None:
            return
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream and not stream.closed:
                try:
                    stream.close()
                except OSError:
                    pass

    @staticmethod
    def _fail(
        playbook: str,
        duration: float,
        error: str,
        rc: int = -1,
        output: str = "",
    ) -> Dict[str, Any]:
        """Build a failure result dict."""
        return {
            "success": False,
            "rc": rc,
            "output": output,
            "duration": duration,
            "error": error,
            "playbook": playbook,
        }
