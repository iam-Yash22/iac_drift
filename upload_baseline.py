import os, sys, json, getpass, urllib.request, urllib.error

SKIP = {".venv", "venv", "node_modules", ".git", ".git-old-backup", ".terraform", "$RECYCLE.BIN", "System Volume Information", "Windows", "Program Files", "Program Files (x86)"}
REAL = ["i-08b1029548fc82f67", "sg-0fcd7a69b5e3ae5a9", "driftwatch-test-fn"]

files, explicit = [], set()
for root in (sys.argv[1:] or ["D:\\"]):
    if os.path.isfile(root):
        files.append(root)
        explicit.add(root)
        continue
    for d, dirs, fs in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP]
        files += [os.path.join(d, f) for f in fs if f.endswith(".tfstate")]

out, seen = [], set()
for p in files:
    try:
        raw = open(p, encoding="utf-8-sig").read()
        st = json.loads(raw)
    except Exception:
        print("SKIP unreadable ", p)
        continue
    res = [r for r in st.get("resources", []) if r.get("mode", "managed") == "managed"]
    fake = "1234567890abcdef0" in raw and p not in explicit
    print(("SKIP fixture  " if fake else "USE           ") + p, len(res), sorted({r["type"] for r in res}))
    if fake or not res:
        continue
    for r in res:
        k = (r.get("module"), r["type"], r["name"])
        if k not in seen:
            seen.add(k)
            out.append(r)

body = json.dumps({"resources": out})
body = body.replace("b1-example-bucket", "b1-740122274365")
print("merged:", len(out), sorted({r["type"] for r in out}))
print("real ids present:", {k: k in body for k in REAL}, "| bucket b1-:", "b1-" in body)
if not out:
    raise SystemExit("No usable state files found.")
if input("Upload to account 2 (replaces its whole baseline)? y/n: ").lower() != "y":
    raise SystemExit("Aborted.")
tok = getpass.getpass("Access token: ").strip().strip("'\"")
req = urllib.request.Request(
    "https://iac-drift.onrender.com/api/v1/accounts/2/terraform-plan",
    data=body.encode(), method="POST",
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + tok},
)
try:
    r = urllib.request.urlopen(req, timeout=120)
    print(r.status, r.read().decode()[:500])
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode()[:500])