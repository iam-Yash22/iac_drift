import asyncio
import inspect
import json
import threading
import time

from app.db.session import SessionLocal
from app.models.scan import Scan
from app.models.terraform_baseline import TerraformBaseline
from app.parsers import normalizer
from app.services import drift_orchestrator as d
from app.crud import crud_resource

F1 = {
    'resources': [
        {
            'mode': 'managed',
            'type': 'aws_s3_bucket',
            'name': 'contract_bucket',
            'instances': [{'attributes': {'id': 'contract-bucket', 'bucket': 'contract-bucket'}}],
        },
        {
            'mode': 'managed',
            'type': 'aws_instance',
            'name': 'contract_instance',
            'instances': [{'attributes': {'id': 'i-contract', 'instance_type': 't3.micro'}}],
        },
    ]
}

orig = d.aws_client_factory.get_clients_for_account

async def delayed_get_clients_for_account(account):
    print('SCAN: sleeping before AWS fetch...', flush=True)
    await asyncio.sleep(10)
    result = orig(account)
    if inspect.isawaitable(result):
        return await result
    return result

d.aws_client_factory.get_clients_for_account = delayed_get_clients_for_account

with SessionLocal() as db:
    scan = Scan(account_id=1, status='queued', triggered_by_id=7)
    db.add(scan)
    db.commit()
    db.refresh(scan)
    print('SCAN ID', scan.id, flush=True)

    def runner():
        try:
            asyncio.run(d.orchestrate_account_scan('1', 'manual', db=db, scan_id=scan.id))
        except Exception as exc:
            print('THREAD ERROR', type(exc).__name__, exc, flush=True)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()

    deadline = time.time() + 20
    while time.time() < deadline:
        db.refresh(scan)
        if scan.status == 'running':
            print('SCAN: running before upload', flush=True)
            parsed = d._state_document_resources(F1)
            resources = normalizer.normalize_resources(parsed)
            resource_rows = [resource.to_dict() for resource in resources]
            crud_resource.crud_resource.replace_terraform_baseline(db, account_id=1, resources=resource_rows)
            db.commit()
            print('UPLOAD RESPONSE', {'resources_parsed': len(resource_rows)}, flush=True)
            break
        time.sleep(0.2)

    thread.join(timeout=50)
    db.refresh(scan)
    print('FINAL SCAN STATUS', scan.status, flush=True)
    print('FINAL SCAN RESULT', json.dumps(scan.result, default=str), flush=True)
    current = db.query(TerraformBaseline).filter(TerraformBaseline.account_id == 1).order_by(TerraformBaseline.id).all()
    print('CURRENT BASELINE ROWS', [(row.resource_type, row.resource_id, row.name) for row in current], flush=True)
