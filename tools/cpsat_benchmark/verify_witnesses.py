"""Check representative CP witnesses through the scalar FindEntities test surface."""
import argparse
import json
from pathlib import Path

import benchmark as b


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    report=json.loads(args.input.read_text())
    b.freeze(Path(report['snapshot']))
    chosen={r['case_id'] for r in report.get('cross_model_count_disagreements',[])}
    chosen.add('autumn/square-3/all-40/GIANT')
    results=[]
    for case in report['cases']:
        if case['id'] not in chosen:continue
        row=next(r for r in report['rows'] if r['case_id']==case['id'] and r['solver']=='cp-sat-8')
        assert row['optimal']
        w,slots=b.context(case);L=w.lua
        L.globals().witness=L.table_from(row['board'])
        outcome=L.execute('''
ENTITIES={};local planted={}
for i,crop in ipairs(witness)do if crop then
 local e=SpawnPrefab('farm_plant_'..crop);e.crop=crop;e.slot=i
 e:AddTag('family_'..crop);e.Transform:SetPosition(slots[i].x,0,slots[i].z)
 planted[#planted+1]=e
end end
local failures={}
for _,e in ipairs(planted)do
 local x,y,z=e.Transform:GetWorldPosition();local def=DEFS[e.crop]
 local family=#TheSim:FindEntities(x,y,z,def.family_check_dist,{'family_'..e.crop})
 if family<def.family_min_count then failures[#failures+1]={slot=e.slot,count=family}end
end
return #planted,#failures
''')
        assert outcome==(row['count'],0), (case['id'],outcome)
        results.append({'case_id':case['id'],'cp_count':row['count'],
                        'queried_plants':outcome[0],'family_failures':outcome[1],
                        'original_lua_validation_errors':row['metrics']['runtime_validation_errors']})
    args.output.write_text(json.dumps({'type':'offline scalar FindEntities emulation, not live engine',
                                      'cases':results},ensure_ascii=False,indent=2))
    print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
