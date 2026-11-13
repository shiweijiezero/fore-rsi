# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""CLI configuration and command behavior."""

import io
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import cli
from config import Config, UIConfig, WorkflowConfig


class ConfigurationTests(unittest.TestCase):
    def test_combined_options_build_one_typed_configuration(self) -> None:
        config = cli.parse_args(
            [
                "--task", "task folder/task.md",
                "--workflow", "custom",
                "--harness", "pi",
                "--session", "shared display",
            ]
        )

        self.assertEqual(
            config,
            Config(
                workflow=WorkflowConfig(
                    name="custom",
                    task=Path("task folder/task.md"),
                    harness="pi",
                ),
                ui=UIConfig(session="shared display"),
            ),
        )
        self.assertIsInstance(config.workflow.task, Path)

    def test_optional_arguments_use_configuration_defaults(self) -> None:
        self.assertEqual(cli.parse_args([]), Config())
        self.assertEqual(
            cli.parse_args(["--task", "task.md"]),
            Config(workflow=WorkflowConfig(task=Path("task.md"))),
        )

    def test_session_name_is_kept_in_ui_configuration(self) -> None:
        config = cli.parse_args(["--session", "None"])

        self.assertEqual(config.ui.session, "None")
        self.assertEqual(config.workflow, WorkflowConfig())


class CommandTests(unittest.TestCase):
    def test_help_describes_both_groups_and_exits_successfully(self) -> None:
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                output = io.StringIO()
                with redirect_stdout(output):
                    with self.assertRaises(SystemExit) as result:
                        cli.main([flag])

                self.assertEqual(result.exception.code, 0)
                help_text = output.getvalue().lower()
                self.assertIn("workflow", help_text)
                self.assertIn("ui", help_text)
                self.assertIn("--session", help_text)
                self.assertIn("--version", help_text)
                self.assertNotIn("--detach", help_text)

    def test_version_comes_from_package_metadata(self) -> None:
        output = io.StringIO()
        with (
            patch("cli.version", return_value="9.8.7") as version,
            redirect_stdout(output),
        ):
            with self.assertRaises(SystemExit) as result:
                cli.main(["--version"])

        self.assertEqual(result.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), "fore-rsi 9.8.7")
        version.assert_called_once_with("fore-rsi")

    def test_invalid_arguments_report_parse_errors(self) -> None:
        for args in (["--detach"], ["task.md"], ["--unknown"], ["--task"], ["--session"]):
            with self.subTest(args=args):
                with (
                    redirect_stdout(io.StringIO()),
                    redirect_stderr(io.StringIO()),
                ):
                    with self.assertRaises(SystemExit) as result:
                        cli.main(args)

                self.assertEqual(result.exception.code, 2)

    def test_task_command_reports_execution_status_without_a_traceback(self) -> None:
        for args in ([], ["--task", "task.md"]):
            with self.subTest(args=args):
                result = subprocess.run(
                    [sys.executable, cli.__file__, *args], capture_output=True, text=True
                )
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr.strip(), "Workflow execution is not implemented.")


if __name__ == "__main__":
    unittest.main()
