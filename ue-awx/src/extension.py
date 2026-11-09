"""Stonebranch Universal Extension: Ansible AWX / AAP Controller.

Launch, monitor and review job templates and workflow job templates through
the AWX REST API (/api/v2).
"""
import json
import time

import requests
from universal_extension import UniversalExtension, ExtensionResult, logger

TERMINAL = {"successful", "failed", "error", "canceled"}


class AwxError(Exception):
    pass


class Extension(UniversalExtension):
    def __init__(self):
        super().__init__()
        self.session = None
        self.base = None
        self.timeout = 60
        self.cancelled = False
        self.kind = "jobs"  # "jobs" or "workflow_jobs"
        self.job_id = None
        self.cancel_on_abort = True

    # ------------------------------------------------------------------ entry
    def extension_start(self, fields):
        self._connect(fields)
        action = fields.get("action")
        logger.info("AWX action: %s", action)

        try:
            if action == "launch_job_template":
                self.kind = "jobs"
                job = self._launch("job_templates", fields)
                return self._maybe_wait(job, fields)
            if action == "launch_workflow":
                self.kind = "workflow_jobs"
                job = self._launch("workflow_job_templates", fields)
                return self._maybe_wait(job, fields)
            if action == "monitor_job":
                self.kind = "workflow_jobs" if fields.get("job_kind") == "workflow" else "jobs"
                self.job_id = int(fields["job_id"])
                return self._monitor(fields)
            if action == "review_job":
                self.kind = "workflow_jobs" if fields.get("job_kind") == "workflow" else "jobs"
                self.job_id = int(fields["job_id"])
                job = self._get(f"{self.kind}/{self.job_id}/")
                return self._result(job, fields, review=True)
            raise AwxError(f"Unknown action: {action}")
        except AwxError as e:
            logger.error(str(e))
            return ExtensionResult(rc=1, message=str(e), unv_output=str(e))

    def extension_cancel(self):
        """Task cancelled in UAC: optionally cancel the AWX job as well."""
        self.cancelled = True
        if self.cancel_on_abort and self.job_id and self.session:
            try:
                self.session.post(
                    f"{self.base}/{self.kind}/{self.job_id}/cancel/", timeout=self.timeout
                )
                logger.info("Cancel requested for AWX %s %s", self.kind, self.job_id)
            except Exception as e:  # noqa: BLE001
                logger.warning("Cancel request failed: %s", e)

    # ------------------------------------------------------------ connection
    def _connect(self, fields):
        url = (fields.get("awx_url") or "").rstrip("/")
        if not url:
            raise AwxError("AWX URL is required")
        self.base = url + "/api/v2"
        self.timeout = int(fields.get("request_timeout") or 60)
        self.cancel_on_abort = bool(fields.get("cancel_on_abort", True))

        creds = fields.get("credentials") or {}
        user = creds.get("user") or creds.get("username") or ""
        secret = creds.get("password") or creds.get("token") or creds.get("key") or ""
        if not secret:
            raise AwxError("AWX credentials are required (password or token)")

        s = requests.Session()
        s.verify = bool(fields.get("verify_ssl", True))
        s.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
        if user:
            s.auth = (user, secret)  # basic auth
        else:
            s.headers["Authorization"] = f"Bearer {secret}"  # OAuth2 personal access token
        self.session = s

        # Verify connectivity / auth.
        self._get("ping/")
        self._get("me/")

    # ----------------------------------------------------------- REST helpers
    def _req(self, method, path, **kw):
        try:
            r = self.session.request(method, f"{self.base}/{path.lstrip('/')}",
                                     timeout=self.timeout, **kw)
        except requests.RequestException as e:
            raise AwxError(f"Connection error calling {path}: {e}") from e
        if r.status_code in (401, 403):
            raise AwxError(f"AWX authentication/authorisation failed ({r.status_code}) for {path}")
        if r.status_code >= 400:
            raise AwxError(f"AWX returned {r.status_code} for {path}: {r.text[:500]}")
        return r

    def _get(self, path, **params):
        return self._req("GET", path, params=params or None).json()

    def _lookup(self, collection, name):
        """Resolve a template by name (or numeric id)."""
        if str(name).isdigit():
            return int(name)
        res = self._get(f"{collection}/", name=name)
        if res.get("count", 0) != 1:
            raise AwxError(f"Expected exactly one {collection} named '{name}', found {res.get('count', 0)}")
        return res["results"][0]["id"]

    # ----------------------------------------------------------------- launch
    def _launch(self, collection, fields):
        tid = self._lookup(collection, fields.get("template"))
        body = {}
        ev = fields.get("extra_vars")
        if ev:
            try:
                body["extra_vars"] = json.loads(ev) if isinstance(ev, str) else ev
            except ValueError:
                body["extra_vars"] = ev  # pass YAML through as a string
        if collection == "job_templates":
            for key in ("limit", "job_tags", "skip_tags", "job_type", "scm_branch"):
                if fields.get(key):
                    body[key] = fields[key]
            if fields.get("verbosity") not in (None, ""):
                body["verbosity"] = int(fields["verbosity"])
            if fields.get("inventory"):
                body["inventory"] = self._lookup("inventories", fields["inventory"])
        elif fields.get("limit"):
            body["limit"] = fields["limit"]

        r = self._req("POST", f"{collection}/{tid}/launch/", data=json.dumps(body))
        job = r.json()
        self.job_id = job.get("id") or job.get("workflow_job") or job.get("job")
        if not self.job_id:
            raise AwxError(f"Launch did not return a job id: {job}")
        logger.info("Launched AWX %s %s", self.kind, self.job_id)
        return job

    def _maybe_wait(self, job, fields):
        if fields.get("wait_for_completion", True):
            return self._monitor(fields)
        job = self._get(f"{self.kind}/{self.job_id}/")
        return self._result(job, fields, launched_only=True)

    # ---------------------------------------------------------------- monitor
    def _monitor(self, fields):
        interval = max(2, int(fields.get("poll_interval") or 10))
        max_wait = int(fields.get("max_wait") or 0)  # 0 = unlimited
        start = time.time()
        last = None
        while True:
            job = self._get(f"{self.kind}/{self.job_id}/")
            status = job.get("status")
            if status != last:
                logger.info("AWX %s %s status: %s", self.kind, self.job_id, status)
                last = status
            if status in TERMINAL:
                return self._result(job, fields)
            if self.cancelled:
                return ExtensionResult(rc=1, message="Task cancelled", unv_output="Task cancelled")
            if max_wait and time.time() - start > max_wait:
                raise AwxError(
                    f"Timed out after {max_wait}s waiting for job {self.job_id} (status {status})")
            time.sleep(interval)

    # ----------------------------------------------------------------- result
    def _result(self, job, fields, review=False, launched_only=False):
        status = job.get("status")
        lines = [
            f"Job ID:    {job.get('id')}",
            f"Name:      {job.get('name')}",
            f"Status:    {status}",
            f"Started:   {job.get('started')}",
            f"Finished:  {job.get('finished')}",
            f"Elapsed:   {job.get('elapsed')}s",
            f"URL:       {self.base.replace('/api/v2', '')}/#/jobs/"
            f"{'workflow' if self.kind == 'workflow_jobs' else 'playbook'}/{job.get('id')}",
        ]

        if not launched_only and self.kind == "jobs":
            lines += self._host_summary(job)
            if fields.get("include_stdout", True) and (review or status in TERMINAL):
                lines += ["", "---- Playbook output ----", self._stdout(job, fields)]
        elif not launched_only and self.kind == "workflow_jobs":
            lines += self._workflow_nodes(job)

        text = "\n".join(lines)
        if launched_only:
            return ExtensionResult(rc=0, message=f"Launched job {job.get('id')}", unv_output=text)
        if review:
            return ExtensionResult(rc=0, message=f"Job {job.get('id')}: {status}", unv_output=text)

        ok = status == "successful"
        if not ok and not fields.get("fail_on_failure", True):
            ok = True
        return ExtensionResult(
            rc=0 if ok else 1,
            message=f"Job {job.get('id')} finished: {status}",
            unv_output=text,
        )

    def _host_summary(self, job):
        out = ["", "---- Host summary ----"]
        try:
            res = self._get(f"jobs/{job['id']}/job_host_summaries/", page_size=200)
        except AwxError as e:
            return out + [f"(unavailable: {e})"]
        for h in res.get("results", []):
            out.append(
                f"{h.get('host_name')}: ok={h.get('ok')} changed={h.get('changed')} "
                f"failures={h.get('failures')} dark={h.get('dark')} skipped={h.get('skipped')}")
        if len(out) == 2:
            out.append("(no host summaries)")
        return out

    def _stdout(self, job, fields):
        limit = int(fields.get("max_output_lines") or 500)
        try:
            r = self._req("GET", f"jobs/{job['id']}/stdout/", params={"format": "txt"})
        except AwxError as e:
            return f"(stdout unavailable: {e})"
        lines = r.text.splitlines()
        if len(lines) > limit:
            lines = [f"... truncated, showing last {limit} of {len(lines)} lines ..."] + lines[-limit:]
        return "\n".join(lines)

    def _workflow_nodes(self, job):
        out = ["", "---- Workflow nodes ----"]
        try:
            res = self._get(f"workflow_jobs/{job['id']}/workflow_nodes/", page_size=200)
        except AwxError as e:
            return out + [f"(unavailable: {e})"]
        for n in res.get("results", []):
            sj = (n.get("summary_fields") or {}).get("job") or {}
            out.append(f"node {n.get('id')}: {sj.get('name', '(not run)')} -> "
                       f"{sj.get('status', 'n/a')} (job {sj.get('id', '-')})")
        return out
