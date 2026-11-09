# ue-awx – Stonebranch UAC Extension for Ansible AWX

Talks to the AWX REST API (`/api/v2`) to launch, monitor and review playbook runs.

## Actions
| Action | What it does |
|---|---|
| `launch_job_template` | Launches a job template (by name or ID) with optional extra vars, inventory, limit, tags, job type, verbosity, SCM branch. Optionally waits for completion. |
| `launch_workflow` | Launches a workflow job template; waiting reports each node's status. |
| `monitor_job` | Polls an existing job/workflow job ID until it reaches a terminal state. |
| `review_job` | One-shot review: status, timings, per-host summary (ok/changed/failed/unreachable) and playbook stdout. |

## Connection
* **AWX URL** – base URL, e.g. `https://awx.example.com`
* **AWX Credentials** (UAC runtime credentials)
  * User + Password → HTTP basic auth
  * Empty User + Password → OAuth2 personal access token (Bearer)
* Verify SSL, request timeout configurable.

## Behaviour
* Task fails (rc=1) if the AWX job ends `failed`, `error` or `canceled` (toggle: *Fail Task if AWX Job Fails*).
* Cancelling the UAC task cancels the AWX job (toggle: *Cancel AWX Job if UAC Task Cancelled*).
* Output includes job URL, host summary and the last N lines of playbook stdout.

## Build / install
```
python build.py        # writes ue-awx-1.0.0.zip (template.json + icon + extension_archive.zip)
```
Import the zip in UAC: *Services -> Universal Templates -> Import* (or Universal Extensions), then create a task from the "Ansible AWX" template. The extension uses only the Python standard library.

## Notes
* Required AWX permissions: Execute on the template, Read on inventories used.
* The build generates a placeholder icon; replace it in `build.py` if desired.
