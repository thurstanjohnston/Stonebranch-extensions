"""Builds ue-windows-command-1.0.0.zip (template.json + template_icon.png + extension_archive.zip).

Uses the checked-in src/templates/template.json as the skeleton for the top-level keys
(or any exported 8.1 extension template.json passed as argv[1]); all fields are replaced.
"""
import json, os, struct, sys, zlib, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKEL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "src", "templates", "template.json")
PFX = "ue_windows_command_"

tpl = json.load(open(SKEL, encoding="utf-8"))
field_skel = next(f for f in tpl["fields"] if f["fieldType"] == "Text")  # per-field skeleton


def field(seq, name, label, mapping, ftype, hint, **kw):
    f = json.loads(json.dumps(field_skel))
    f.update(fieldMapping=mapping, fieldType=ftype, hint=hint, label=label, name=name,
             sequence=seq, sysId=PFX + name, fieldValue=None, formStartRow=False,
             formColumnSpan=1, required=False, choices=[])
    f.update(kw)
    return f


def choices(vals):
    return [{"fieldValue": v, "fieldValueLabel": v, "sequence": i,
             "sysId": PFX + "cmd_%d" % i, "useFieldValueForLabel": False}
            for i, v in enumerate(vals)]


CMDS = [
    "ipconfig /all", "ping", "hostname", "whoami", "systeminfo", "tasklist", "taskkill",
    "netstat -ano", "nslookup", "tracert", "net user", "net use", "net start", "net stop",
    "sc query", "dir", "type", "copy", "xcopy", "robocopy", "del", "mkdir", "gpupdate /force",
    "schtasks /query", "powershell -Command", "ver", "set", "chkdsk", "ipconfig /flushdns",
    "arp -a", "route print", "wmic logicaldisk get size,freespace,caption",
]
fields = [
    field(0, "win_command", "Command", "Choice Field 1", "Choice",
          "Common Windows CLI commands", required=True, fieldValue=CMDS[0],
          choices=choices(CMDS), formStartRow=True),
    field(1, "custom_command", "Custom Command", "Text Field 1", "Text",
          "Optional. Overrides the drop-down command."),
    field(2, "arguments", "Arguments", "Text Field 2", "Text",
          "Appended to the command, e.g. -n 4 localhost", formStartRow=True),
    field(3, "runtime_dir", "Runtime Directory", "Text Field 3", "Text",
          "Working directory on the agent", fieldValue="C:\Windows\Temp"),
    field(4, "timeout", "Timeout (seconds)", "Integer Field 1", "Integer",
          "Kill the command after this long", fieldValue="600", intFieldMin=1),
]

tpl.update(
    fields=fields, name="Windows Command Runner", description="Run a Windows CLI command on a Windows agent",
    extension="ue-windows-command", sysId="ue_windows_command", variablePrefix="win_cmd",
    exportReleaseLevel="8.1.0.0", minReleaseLevel="8.1.0.0", templateType="Extension",
    agentType="Any", iconFilename="icon.png", outputReturnType="NONE",
)
tpl.pop("iconDateCreated", None)
tpl["iconDateCreated"] = "2026-11-09 00:00:00"


def png(size=48, rgb=(0, 90, 160)):
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
final = os.path.join(HERE, "ue-windows-command-1.0.0.zip")
with zipfile.ZipFile(final, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("template.json", tj)
    z.writestr("template_icon.png", png())
    z.write(inner, "extension_archive.zip")
print("built", final)
