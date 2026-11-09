# Windows Command Runner (UAC 8.1 Universal Extension)

Runs a common Windows CLI command on the Windows agent a task is assigned to,
as the task's runtime credentials user. The agent and credentials come from the
task's standard Agent Details, so the extension makes no UAC REST calls.

## Fields
| Field | Notes |
|---|---|
| Command | Drop-down of 32 common commands (ipconfig, ping, tasklist, robocopy, ...) |
| Custom Command | Optional; overrides the drop-down |
| Arguments | Appended to the command, e.g. `-n 4 localhost` |
| Runtime Directory | Working directory on the agent (default `C:\Windows\Temp`) |
| Timeout (seconds) | Command is killed after this long (default 600) |

The task succeeds when the command exits with code 0. Combined stdout/stderr is
returned as the task output.

## Layout
```
src/extension.py              runs the command (standard library only)
src/extension.yml             extension metadata
src/templates/template.json   generated template definition (fields)
build.py                      generates template.json and builds the import zip
```

## Build
```
python build.py
```
Produces `ue-windows-command-1.0.0.zip` containing `template.json`,
`template_icon.png` (48x48) and `extension_archive.zip` (`extension.py`,
`extension.yml`). To change the fields or command list, edit `build.py`.
`build.py` takes its top-level keys from the checked-in `src/templates/template.json`
(or any exported extension `template.json` passed as an argument). The zip is a build
output: it is git-ignored, so attach it to a GitHub release instead of committing it.

## Install and use
1. In UAC: Administration > Universal Templates > Import, select the zip.
2. Create a Universal Task from the template.
3. Set Agent and Runtime Credentials in the task's Agent Details.
4. Pick a command (or enter a custom one), add arguments, and run.

## Notes
- The agent must be a Windows agent with Python 3.7+ available to Universal Extensions.
- Commands run through `cmd.exe`, so built-ins like `dir`, `set` and `ver` work.
- Not tested live; verify on a test agent first.
