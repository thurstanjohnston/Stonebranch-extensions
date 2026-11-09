"""Windows Command Runner - Universal Extension for Stonebranch UAC 8.1.

Runs a common Windows CLI command directly on the agent the task is assigned to,
as the task's runtime credentials user. Agent and credentials are the standard
Agent Details of the task - no UAC REST connection is needed.
"""
import subprocess

from universal_extension import UniversalExtension, ExtensionResult
from universal_extension import logger


def _text(v):
    """Field values may be str, list (choice fields) or None; return a stripped str."""
    if isinstance(v, (list, tuple)):
        v = v[0] if v else ""
    return str(v).strip() if v is not None else ""


class Extension(UniversalExtension):

    def extension_start(self, fields):
        command = _text(fields.get("custom_command")) or _text(fields.get("win_command"))
        if not command:
            return ExtensionResult(rc=1, message="No command selected. Fields received: %s"
                                   % sorted(fields.keys()))
        args = _text(fields.get("arguments"))
        full = f"{command} {args}".strip()
        cwd = _text(fields.get("runtime_dir")) or None
        timeout = int(_text(fields.get("timeout")) or 600)

        logger.info("Running: %s (cwd=%s)", full, cwd)
        try:
            p = subprocess.run(full, shell=True, cwd=cwd, timeout=timeout,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except subprocess.TimeoutExpired:
            return ExtensionResult(rc=1, message=f"'{full}' timed out after {timeout}s")
        except Exception as e:  # noqa: BLE001
            return ExtensionResult(rc=1, message=f"Could not run '{full}': {e}")

        out = p.stdout.decode("oem", "replace") if p.stdout else ""
        logger.info("Exit code %s\n%s", p.returncode, out)
        return ExtensionResult(
            rc=0 if p.returncode == 0 else 1,
            message=f"'{full}' exited with code {p.returncode}",
            unv_output=out)
