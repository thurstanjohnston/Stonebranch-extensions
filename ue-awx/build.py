"""Builds ue-awx-1.0.0.zip (template.json + template_icon.png + extension_archive.zip).

Uses the checked-in src/templates/template.json as the skeleton for the top-level keys
(or any exported 8.1 extension template.json passed as argv[1]); all fields are replaced.
Same package layout as ue-windows-command.
"""
import json, os, struct, sys, zlib, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKEL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "src", "templates", "template.json")
PFX = "ue_awx_"

tpl = json.load(open(SKEL, encoding="utf-8"))
field_skel = next(f for f in tpl["fields"] if f["fieldType"] == "Text")


def field(seq, name, label, mapping, ftype, hint, **kw):
    f = json.loads(json.dumps(field_skel))
    f.update(fieldMapping=mapping, fieldType=ftype, hint=hint, label=label, name=name,
             sequence=seq, sysId=PFX + name, fieldValue=None, formStartRow=False,
             formColumnSpan=1, required=False, choices=[])
    f.update(kw)
    return f


def choices(name, vals):
    return [{"fieldValue": v, "fieldValueLabel": v or "(default)", "sequence": i,
             "sysId": "%s%s_%d" % (PFX, name, i), "useFieldValueForLabel": False}
            for i, v in enumerate(vals)]


_n = {"Text": 0, "Choice": 0, "Integer": 0, "Boolean": 0}
fields = []


def add(name, label, ftype, hint, **kw):
    _n[ftype] += 1
    fields.append(field(len(fields), name, label, "%s Field %d" % (ftype, _n[ftype]),
                        ftype, hint, **kw))


def text(name, label, hint, **kw): add(name, label, "Text", hint, **kw)
def integer(name, label, hint, default=None, **kw):
    add(name, label, "Integer", hint, fieldValue=None if default is None else str(default), **kw)
def boolean(name, label, hint, default):
    add(name, label, "Boolean", hint, fieldValue="true" if default else "false")
def choice(name, label, hint, vals, default, **kw):
    add(name, label, "Choice", hint, fieldValue=default, choices=choices(name, vals), **kw)


choice("action", "Action", "What to do in AWX",
       ["launch_job_template", "launch_workflow", "monitor_job", "review_job"],
       "launch_job_template", required=True, formStartRow=True)
text("awx_url", "AWX URL", "Base URL, e.g. https://awx.example.com", required=True, formStartRow=True)
boolean("verify_ssl", "Verify SSL", "Validate the AWX TLS certificate", True)
integer("request_timeout", "Request Timeout (s)", "Timeout per REST call", 60, intFieldMin=1)

text("template", "Template Name or ID",
     "Launch actions: job template / workflow template name or numeric ID", formStartRow=True)
text("extra_vars", "Extra Vars", "Launch actions: JSON (or YAML) extra variables")
text("inventory", "Inventory Name or ID", "Job template launch only (template must allow prompt)")
text("limit", "Limit", "Host pattern limit (template must allow prompt)")
text("job_tags", "Job Tags", "Job template launch only")
text("skip_tags", "Skip Tags", "Job template launch only")
text("scm_branch", "SCM Branch", "Job template launch only")
choice("job_type", "Job Type", "Job template launch only", ["", "run", "check"], "")
integer("verbosity", "Verbosity (0-5)", "Job template launch only", intFieldMin=0, intFieldMax=5)
boolean("wait_for_completion", "Wait for Completion", "Launch actions: monitor until the job finishes", True)

integer("job_id", "AWX Job ID", "monitor_job / review_job: ID of an existing job", formStartRow=True)
choice("job_kind", "Job Kind", "monitor_job / review_job: playbook job or workflow job",
       ["playbook", "workflow"], "playbook")

integer("poll_interval", "Poll Interval (s)", "Seconds between status checks", 10, intFieldMin=1,
        formStartRow=True)
integer("max_wait", "Max Wait (s)", "0 = wait indefinitely", 0, intFieldMin=0)
boolean("fail_on_failure", "Fail Task if AWX Job Fails", "rc=1 when status is failed/error/canceled", True)
boolean("cancel_on_abort", "Cancel AWX Job if Task Cancelled", "Cancel the AWX job when the UAC task is cancelled", True)
boolean("include_stdout", "Include Playbook Output", "Append job stdout to task output", True)
integer("max_output_lines", "Max Output Lines", "Keep only the last N lines of stdout", 500, intFieldMin=1)

tpl.update(
    fields=fields, name="Ansible AWX",
    description="Launch, monitor and review Ansible AWX job templates and workflows",
    extension="ue-awx", sysId="ue_awx", variablePrefix="awx",
    exportReleaseLevel="8.1.0.0", minReleaseLevel="8.1.0.0", templateType="Extension",
    agentType="Any", iconFilename="icon.png", outputReturnType="NONE",
)
tpl["iconDateCreated"] = "2026-11-09 00:00:00"


def png(size=48, rgb=(200, 40, 40)):
    row = b"\x00" + bytes(rgb) * size
    raw = zlib.compress(row * size)
    def ch(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + ch(b"IDAT", raw) + ch(b"IEND", b""))


out = os.path.join(HERE, "build")
os.makedirs(out, exist_ok=True)
inner = os.path.join(out, "extension_archive.zip")
with zipfile.ZipFile(inner, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(os.path.join(HERE, "src", "extension.py"), "extension.py")
    z.write(os.path.join(HERE, "src", "extension.yml"), "extension.yml")

tj = json.dumps(tpl, indent=2)
open(os.path.join(HERE, "src", "templates", "template.json"), "w", encoding="utf-8").write(tj)
final = os.path.join(HERE, "ue-awx-1.0.0.zip")
with zipfile.ZipFile(final, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("template.json", tj)
    z.writestr("template_icon.png", png())
    z.write(inner, "extension_archive.zip")
print("built", final, "-", len(fields), "fields")
