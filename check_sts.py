import os, re, boto3
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from botocore.exceptions import ClientError
import getpass
for k, p in (("NEON", "Enter the database url"), ("RK", "Enter access key id"), ("RS", "Enter secret key")):
    if not os.environ.get(k):
        os.environ[k] = getpass.getpass(p + ": ").strip().strip("'\"")
env = dotenv_values(".env")
def fix(u):
    m = re.search(r"postgres(?:ql)?(?:\+\w+)?://[^\s'\"]+", u or "")
    if not m:
        raise SystemExit(f"No postgres URL found in input (length {len(u or '')}, starts with {(u or '')[:6]!r}) -> re-paste; use right-click paste")
    u = re.sub(r"^postgres(?:ql)?(?:\+\w+)?://", "postgresql://", m.group(0))
    u = re.sub(r"([?&])ssl=", r"\1sslmode=", u)
    return u

def rows(url):
    with create_engine(fix(url)).connect() as c:
        return c.execute(text("select id, role_arn, external_id from aws_accounts order by id")).all()

local = rows(env.get("DATABASE_URL") or env.get("DATABASE__URL"))
neon = {r[0]: r for r in rows(os.environ["NEON"])}
n = neon[2]
print("local ids:", [r[0] for r in local], "| neon ids:", list(neon))
for r in local:
    print(f"local {r[0]} == neon 2 -> role_arn: {r[1]==n[1]}, external_id: {r[2]==n[2]}")
print("neon whitespace issue:", n[1] != n[1].strip() or (n[2] or "") != (n[2] or "").strip())

def attempt(s, arn, ext):
    try:
        s.assume_role(RoleArn=arn, RoleSessionName="dwcheck", **({"ExternalId": ext} if ext else {}))
        return "OK"
    except ClientError as e:
        return e.response["Error"]["Code"]

keys = {"LOCAL": (env.get("CLOUD__AWS_ACCESS_KEY_ID"), env.get("CLOUD__AWS_SECRET_ACCESS_KEY")),
        "RENDER": (os.environ.get("RK"), os.environ.get("RS"))}
good = None
for label, (ak, sk) in keys.items():
    if not ak:
        print(label, "not set"); continue
    s = boto3.client("sts", aws_access_key_id=ak, aws_secret_access_key=sk)
    try:
        print(label, "key ...", ak[-4:], "user", s.get_caller_identity()["Arn"].split("/")[-1])
    except ClientError as e:
        print(label, "key ...", ak[-4:], "identity FAIL", e.response["Error"]["Code"]); continue
    print("  vs NEON row 2:", attempt(s, n[1], n[2]))
    for r in local:
        res = attempt(s, r[1], r[2])
        print(f"  vs LOCAL row {r[0]}:", res)
        if res == "OK" and not good:
            good = r

if os.environ.get("FIX") == "1" and good:
    with create_engine(fix(os.environ["NEON"])).begin() as c:
        c.execute(text("update aws_accounts set role_arn=:a, external_id=:e where id=2"), {"a": good[1], "e": good[2]})
    print("NEON row 2 overwritten from local row", good[0])