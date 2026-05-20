#!/usr/bin/env python3
"""
Probe inventory sync after a freestyle roast POST.

Snapshots stock for (coffee, location), POSTs a roast with that pairing
and a given green-weight, then re-snapshots and prints the delta.

Usage:
    python scripts/test_inventory_sync.py \
        --coffee 00000000-0000-4000-8000-000000000002 \
        --location L1002 \
        --start-kg 0.5 \
        --end-kg 0.42

Defaults probe "Grain non identifié (import desktop)" at L1002 (VLG).
"""

import argparse
import datetime
import pathlib
import sys
import time
import uuid

_SRC = pathlib.Path(__file__).resolve().parent.parent / 'src'
sys.path.insert(0, str(_SRC))

from PyQt6.QtCore import QCoreApplication  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

_app = QApplication(sys.argv[:1])
QCoreApplication.setApplicationName('Artisan')
QCoreApplication.setOrganizationName('Artisan-Scope')

from plus import config, connection  # noqa: E402


def snapshot() -> dict[tuple[str, str], float]:
    today = datetime.date.today().isoformat()
    r = connection.getData(f'{config.stock_url}?today={today}')
    if r is None:
        raise RuntimeError('snapshot failed: getData returned None')
    data = r.json()['result']
    out: dict[tuple[str, str], float] = {}
    for c in data.get('coffees', []):
        for s in c.get('stock', []):
            out[(c.get('hr_id'), s.get('location_hr_id'))] = s.get('amount', 0)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--coffee', default='00000000-0000-4000-8000-000000000002',
                   help="hr_id (or UUID) of the coffee to consume")
    p.add_argument('--location', default='L1002',
                   help="hr_id of the store to debit from")
    p.add_argument('--start-kg', type=float, default=0.5,
                   help="green weight (kg)")
    p.add_argument('--end-kg', type=float, default=None,
                   help="roasted weight (kg) — defaults to start * 0.84")
    p.add_argument('--batch-prefix', default='TEST',
                   help="prefix for the roast (so it's easy to clean up later)")
    p.add_argument('--delay', type=float, default=3.0,
                   help="seconds to wait between POST and re-snapshot")
    args = p.parse_args()

    end_kg = args.end_kg if args.end_kg is not None else round(args.start_kg * 0.84, 3)

    connection.authentify()

    before = snapshot()
    key = (args.coffee, args.location)
    before_amount = before.get(key, 0)
    print(f'AVANT  @ ({args.coffee}, {args.location}): {before_amount:.3f} kg')

    roast_id = str(uuid.uuid4())
    payload = {
        'id': roast_id,
        'batch_number': 9990,
        'batch_prefix': args.batch_prefix,
        'date': datetime.datetime.now().astimezone().isoformat(),
        'label': f'inventory sync probe — {args.coffee[:8]}',
        'machine': 'TEST',
        'start_weight': args.start_kg,
        'end_weight': end_kg,
        'defects_weight': 0.0,
        'coffee': args.coffee,
        'location': args.location,
        'blend': None,
    }
    print(f'POST  id={roast_id}  start={args.start_kg}kg  end={end_kg}kg')
    resp = connection.sendData(config.roast_url, payload, 'POST')
    if resp is None:
        print('FAIL: POST returned None')
        return 1
    print(f'      status={resp.status_code} body={resp.text[:200]}')

    time.sleep(args.delay)

    after = snapshot()
    after_amount = after.get(key, 0)
    delta = after_amount - before_amount
    print(f'APRES  @ ({args.coffee}, {args.location}): {after_amount:.3f} kg')
    print(f'DELTA  : {delta:+.3f} kg   (expected: {-args.start_kg:+.3f} kg)')

    if abs(delta + args.start_kg) < 0.001:
        print('PASS  inventory sync working')
        return 0
    print('FAIL  inventory delta does not match start_weight')
    return 2


if __name__ == '__main__':
    sys.exit(main())
