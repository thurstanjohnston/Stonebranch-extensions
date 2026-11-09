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
Uses the Stonebranch Universal Extension framework (`uemload`):

```
pip install uemload
ue-create-extension ...   # or copy src/ into an extension project
uemload build             # produces dist/ue-awx-1.0.0.zip
```
Upload the resulting zip in UAC: *Services → Universal Extensions → Import*, then create a task from the "Ansible AWX" template.

## Notes
* Required AWX permissions: Execute on the template, Read on inventories used.
* Add an `awx.png` icon (referenced in `extension.yml`) or remove `extension_icon`.
