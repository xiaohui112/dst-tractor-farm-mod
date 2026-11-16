"""Preserve interrupted measurements and rerun their entire matched triplet."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

import benchmark as b


def gap(row):
    if 'solve_wall_seconds' not in row:return 0
    return row['solve_wall_seconds']-(row['quantity_wall_seconds']-row['model_wall_seconds'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('report',type=Path)
    args=p.parse_args()
    original=args.report.read_bytes();report=json.loads(original)
    groups=sorted({(r['repeat'],r['case_id']) for r in report['rows'] if abs(gap(r))>.5})
    assert groups,'No clock anomalies found'
    backup=args.report.with_name(args.report.stem+'-interrupted.json')
    assert not backup.exists(),'Do not overwrite prior evidence'
    backup.write_bytes(original)
    b.FLOAT_MODEL=report['float_model']
    assert b.freeze(Path(report['snapshot']))==report['mod_sha256']
    assert hashlib.sha256(Path(b.__file__).read_bytes()).hexdigest()==report['benchmark_sha256']
    before=b.manifest()
    report['clock_anomalies']=[{k:r[k] for k in ('case_id','repeat','solver','quantity_wall_seconds','model_wall_seconds','solve_wall_seconds')}
                               for r in report['rows'] if abs(gap(r))>.5]
    report['interrupted_original_report']=str(backup.resolve())
    for repeat,case_id in groups:
        index=next(i for i,c in enumerate(report['cases']) if c['id']==case_id)
        case=report['cases'][index]
        methods=[('lua',None),('cp',1),('cp',8)]
        shift=(index+repeat)%3;methods=methods[shift:]+methods[:shift]
        for method,workers in methods:
            row=b.run_lua(case,report['quantity_wall_budget_seconds']) if method=='lua' else b.run_cp(case,workers,report['quantity_wall_budget_seconds'])
            assert abs(gap(row))<=.5, ('Clock anomaly recurred',row['solver'],gap(row))
            assert not row['errors']
            row.update(case_id=case_id,repeat=repeat,
                       proof_scope='unmodified-lua-planner' if method=='lua' else b.FLOAT_MODEL,
                       remeasured_due_to_clock_anomaly=True)
            old_index=next(i for i,r in enumerate(report['rows']) if r['case_id']==case_id and r['repeat']==repeat and r['solver']==row['solver'])
            report['rows'][old_index]=row
            print(case_id,repeat,row['solver'],row['status'],row['count'],row['quantity_wall_seconds'],flush=True)
    report['remeasured_triplets']=[{'repeat':r,'case_id':c} for r,c in groups]
    report['summary']=b.summary(report['rows'])
    report['snapshot_unchanged']=b.manifest(Path(report['snapshot']))==report['mod_sha256']
    report['live_mod_unchanged']=report['live_mod_unchanged'] and b.manifest()==before
    report['completed_at']=datetime.now().astimezone().isoformat()
    assert report['snapshot_unchanged']
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
