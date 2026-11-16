"""Same latest snapshot, original double inputs, Lua-only causal control."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

import benchmark as b


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seconds', type=float, default=10)
    args = p.parse_args()
    b.FLOAT_MODEL = 'legacy-double'
    frozen = b.freeze(args.snapshot.resolve())
    live = b.manifest()
    report = {'float_model':b.FLOAT_MODEL, 'snapshot':str(args.snapshot.resolve()),
              'mod_sha256':frozen, 'cases':b.scenarios(), 'rows':[],
              'benchmark_sha256':hashlib.sha256(Path(b.__file__).read_bytes()).hexdigest(),
              'quantity_wall_budget_seconds':args.seconds, 'started_at':datetime.now().astimezone().isoformat()}
    for case in report['cases']:
        row = b.run_lua(case,args.seconds)
        row.update(case_id=case['id'],repeat=0)
        report['rows'].append(row)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(case['id'],row['status'],row['count'],row['quantity_wall_seconds'],row['errors'],flush=True)
        assert not row['errors']
    report['summary'] = b.summary(report['rows'])
    report['snapshot_unchanged'] = b.manifest(args.snapshot) == frozen
    report['live_mod_unchanged'] = b.manifest() == live
    report['completed_at'] = datetime.now().astimezone().isoformat()
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    assert report['snapshot_unchanged']


if __name__ == '__main__':
    main()
