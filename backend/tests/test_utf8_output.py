"""UTF-8入口和边界回归；不加载凭证、模型、数据库或Spark。"""

import base64
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.core.encoding import configure_utf8_output

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SAMPLE = '中文评审🚀，引号"，反斜杠\\，换行\n下一行'


def ansi_environment() -> dict[str, str]:
    return {**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "gbk"}


def run_child(code: str, *, cwd: Path = BACKEND) -> subprocess.CompletedProcess:
    # 故意不加-X utf8，验证项目入口能纠正ANSI父环境。
    return subprocess.run(
        [sys.executable, "-B", "-c", code], cwd=cwd, env=ansi_environment(),
        capture_output=True, timeout=20, check=False,
    )


class Utf8OutputTests(unittest.TestCase):
    def assert_entry(self, package: str, cwd: Path) -> None:
        code = (
            f"import {package}; import json,os,sys; "
            f"print(json.dumps({{'value': {SAMPLE!r}, 'stdout': sys.stdout.encoding, "
            "'stderr':sys.stderr.encoding,'io':os.environ['PYTHONIOENCODING'],"
            "'mode':os.environ['PYTHONUTF8']},ensure_ascii=False)); "
            f"print({SAMPLE!r},file=sys.stderr)"
        )
        result = run_child(code, cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(payload["value"], SAMPLE)
        self.assertEqual(payload["stdout"], "utf-8")
        self.assertEqual(payload["stderr"], "utf-8")
        self.assertEqual(payload["io"], "utf-8")
        self.assertEqual(payload["mode"], "1")
        self.assertEqual(result.stderr.decode("utf-8").replace("\r\n", "\n"), SAMPLE + "\n")

    def test_backend_app_entry_overrides_ansi_output(self):
        self.assert_entry("app", BACKEND)

    def test_backend_scripts_entry_overrides_ansi_output(self):
        self.assert_entry("scripts", BACKEND)

    def test_analytics_entry_is_independent_and_utf8(self):
        self.assert_entry("analytics", ROOT)

    def test_existing_capture_streams_are_not_replaced_or_closed(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "stdout", stdout), patch.object(sys, "stderr", stderr):
            configure_utf8_output()
            self.assertIs(sys.stdout, stdout)
            self.assertIs(sys.stderr, stderr)
            print(SAMPLE)
            print(SAMPLE, file=sys.stderr)
        self.assertFalse(stdout.closed)
        self.assertFalse(stderr.closed)
        self.assertEqual(stdout.getvalue(), SAMPLE + "\n")
        self.assertEqual(stderr.getvalue(), SAMPLE + "\n")

    def test_logging_output_is_valid_utf8_json(self):
        result = run_child(
            "from app.core.logging import configure_logging; "
            f"configure_logging('INFO').info({SAMPLE!r})"
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        self.assertEqual(result.stdout, b"")
        self.assertEqual(json.loads(result.stderr.decode("utf-8"))["message"], SAMPLE)

    def test_nested_python_child_inherits_utf8_environment(self):
        inner = f"import sys; print({SAMPLE!r}); print({SAMPLE!r},file=sys.stderr)"
        result = run_child(
            "import app,subprocess,sys; "
            f"p=subprocess.run([sys.executable,'-B','-c',{inner!r}],capture_output=True,check=True); "
            "sys.stdout.buffer.write(p.stdout); sys.stderr.buffer.write(p.stderr)"
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        for output in (result.stdout, result.stderr):
            self.assertEqual(output.decode("utf-8").replace("\r\n", "\n"), SAMPLE + "\n")

    def test_output_encoding_remains_strict(self):
        result = run_child(
            "import app,json,sys; print(json.dumps({'stdout':sys.stdout.errors,'stderr':sys.stderr.errors}))"
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        self.assertEqual(json.loads(result.stdout), {"stdout": "strict", "stderr": "strict"})
        with self.assertRaises(UnicodeDecodeError):
            b'\xff'.decode("utf-8")

    def test_project_powershell_entry_sets_utf8_for_python(self):
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if shell is None:
            self.skipTest("本环境未提供PowerShell，保留Python编码证据")
        script = (ROOT / "scripts/Use-Utf8.ps1").as_posix().replace("'", "''")
        python = Path(sys.executable).as_posix().replace("'", "''")
        code = f"import json,sys; print(json.dumps({SAMPLE!r},ensure_ascii=False))"
        command = f". '{script}'; & '{python}' -B -c '{code.replace(chr(39), chr(39) * 2)}'"
        encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
        result = subprocess.run(
            [shell, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            cwd=ROOT, env=ansi_environment(), capture_output=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        self.assertEqual(json.loads(result.stdout.decode("utf-8-sig")), SAMPLE)

    def test_powershell_file_defaults_and_profiles_remain_unchanged(self):
        shells = list(dict.fromkeys(filter(None, (shutil.which("pwsh"), shutil.which("powershell")))))
        if not shells:
            self.skipTest("本环境未提供PowerShell，保留Python编码证据")
        script = (ROOT / "scripts/Use-Utf8.ps1").as_posix().replace("'", "''")
        sample = SAMPLE.replace("'", "''")
        appended = "追加中文🚀"
        for shell in shells:
            with self.subTest(shell=Path(shell).name), TemporaryDirectory(prefix="scholarhub-utf8-") as directory:
                target = Path(directory)
                redirected = (target / "redirected.txt").as_posix().replace("'", "''")
                content = (target / "content.txt").as_posix().replace("'", "''")
                # 仅比较profile是否存在、长度和修改时刻，不读取其内容。
                command = """
$ErrorActionPreference = 'Stop'
function Get-ScholarHubProfileState {
    $ScholarHubProfilePaths = @($PROFILE.AllUsersAllHosts, $PROFILE.AllUsersCurrentHost, $PROFILE.CurrentUserAllHosts, $PROFILE.CurrentUserCurrentHost)
    $ScholarHubProfileRows = foreach ($ScholarHubProfilePath in $ScholarHubProfilePaths) {
        if (Test-Path -LiteralPath $ScholarHubProfilePath -PathType Leaf) {
            $ScholarHubProfileItem = Get-Item -LiteralPath $ScholarHubProfilePath -Force
            '{0}|{1}|{2}' -f $ScholarHubProfilePath, $ScholarHubProfileItem.Length, $ScholarHubProfileItem.LastWriteTimeUtc.Ticks
        } else {
            '{0}|absent' -f $ScholarHubProfilePath
        }
    }
    return ($ScholarHubProfileRows | ConvertTo-Json -Compress)
}
$ScholarHubProfilesBefore = Get-ScholarHubProfileState
"""
                command += (
                    f". '{script}'\n"
                    f"'{sample}' > '{redirected}'\n"
                    f"Set-Content -LiteralPath '{content}' -Value '{sample}'\n"
                    f"Add-Content -LiteralPath '{content}' -Value '{appended}'\n"
                    "$ScholarHubProfilesAfter = Get-ScholarHubProfileState\n"
                    "$ScholarHubState = @{ profiles_unchanged = ($ScholarHubProfilesBefore -eq $ScholarHubProfilesAfter); "
                    "major = $PSVersionTable.PSVersion.Major; out_file = $PSDefaultParameterValues['Out-File:Encoding']; "
                    "set_content = $PSDefaultParameterValues['Set-Content:Encoding']; "
                    "add_content = $PSDefaultParameterValues['Add-Content:Encoding'] }\n"
                    "[Console]::WriteLine(($ScholarHubState | ConvertTo-Json -Compress))"
                )
                encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
                result = subprocess.run(
                    [shell, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                    cwd=ROOT, env=ansi_environment(), capture_output=True, timeout=20, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                state = json.loads(result.stdout.decode("utf-8-sig"))
                self.assertTrue(state["profiles_unchanged"])
                expected = "utf8NoBOM" if state["major"] >= 6 else "utf8"
                self.assertEqual(state["out_file"], expected)
                self.assertEqual(state["set_content"], expected)
                self.assertEqual(state["add_content"], expected)
                self.assertEqual(target.joinpath("redirected.txt").read_text(encoding="utf-8-sig"), SAMPLE + "\n")
                self.assertEqual(target.joinpath("content.txt").read_text(encoding="utf-8-sig"), SAMPLE + "\n" + appended + "\n")


if __name__ == "__main__":
    unittest.main()
