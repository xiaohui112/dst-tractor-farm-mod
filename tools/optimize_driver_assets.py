#!/usr/bin/env python3
"""Share the cabin build/atlas without changing any animation bytes or actions."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
DRIVERS=['aom_tractor_driver','aom_tractor_driver_075','aom_tractor_driver_125','aom_tractor_driver_150']

def optimize(folder):
    with ZipFile(folder/'aom_tractor_cabin.zip') as shared:
        common={n:shared.read(n) for n in shared.namelist() if n!='anim.bin'}
    if not {'build.bin','atlas-0.tex'}<=common.keys():raise ValueError('Shared cabin is incomplete')
    animations={};before=0
    # Validate every source before writing anything. Reject a different skin/build.
    for name in DRIVERS:
        path=folder/(name+'.zip');before+=path.stat().st_size
        with ZipFile(path) as z:
            if z.testzip() is not None:raise ValueError('Invalid ZIP: '+name)
            for n in z.namelist():
                if n!='anim.bin' and (n not in common or z.read(n)!=common[n]):raise ValueError('Different shared build/atlas: '+name)
            animations[name]=z.read('anim.bin')
    hashes={}
    for name,raw in animations.items():
        with tempfile.NamedTemporaryFile(dir=folder,suffix='.zip',delete=False) as f:temp=Path(f.name)
        try:
            with ZipFile(temp,'w',ZIP_DEFLATED,compresslevel=9) as z:
                entry=ZipInfo('anim.bin',(1980,1,1,0,0,0));entry.compress_type=ZIP_DEFLATED
                z.writestr(entry,raw,compresslevel=9)
            with ZipFile(temp) as z:
                if z.read('anim.bin')!=raw:raise ValueError('Animation changed')
            os.replace(temp,folder/(name+'.zip'))
        finally:temp.unlink(missing_ok=True)
        hashes[name]=hashlib.sha256((folder/(name+'.zip')).read_bytes()).hexdigest()
    after=sum((folder/(name+'.zip')).stat().st_size for name in DRIVERS)
    return {'before_bytes':before,'after_bytes':after,'saved_bytes':before-after,
            'animation_sha256':{n:hashlib.sha256(raw).hexdigest() for n,raw in animations.items()},'sha256':hashes}

if __name__=='__main__':
    result=optimize(ROOT/'mod/Tractor/anim')
    for path in [ROOT/'mod/Tractor/Driver-Build-Report.json',ROOT/'assets/directional-v2/build.json']:
        report=json.loads(path.read_text());report['sha256'].update(result['sha256'])
        report['shared_driver_build']='aom_tractor_cabin';path.write_text(json.dumps(report,indent=2)+'\n')
    out=ROOT/'outputs/driver-optimization.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
