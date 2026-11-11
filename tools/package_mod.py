#!/usr/bin/env python3
"""先运行全部自检，再原子生成安装包；清单和源码逐文件 SHA-256 校验。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/'mod/AgeOfMachines'
ARCHIVE=ROOT/'AgeOfMachines.zip'
MANIFEST='AgeOfMachines/INSTALL-MANIFEST.json'


def source_files(source):
    return {p.relative_to(source).as_posix():p for p in sorted(source.rglob('*'))
            if p.is_file() and not any(part.startswith('.') or part=='__pycache__'
                                      for part in p.relative_to(source).parts)
            and p.suffix not in ('.pyc','.log')}


def verify_archive(source,archive):
    files=source_files(source)
    with ZipFile(archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or z.testzip() is not None:
            raise ValueError('Duplicate archive entries or invalid ZIP CRC')
        expected={'AgeOfMachines/'+name for name in files}|{MANIFEST}
        if set(names)!=expected:
            raise ValueError('Archive file list differs from source')
        manifest=json.loads(z.read(MANIFEST))
        if set(manifest['files'])!=set(files):
            raise ValueError('Manifest file list differs from source')
        for name,p in files.items():
            raw=z.read('AgeOfMachines/'+name)
            digest=hashlib.sha256(raw).hexdigest()
            if raw!=p.read_bytes() or manifest['files'][name]!={'sha256':digest,'bytes':len(raw)}:
                raise ValueError('Archive/source/manifest mismatch: '+name)
    return manifest


def build_archive(source,archive):
    files=source_files(source)
    manifest={'schema':1,'files':{}}
    archive.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=archive.parent,suffix='.zip',delete=False) as f:
        temp=Path(f.name)
    try:
        with ZipFile(temp,'w',ZIP_DEFLATED,compresslevel=9) as z:
            def write(name,raw):
                info=ZipInfo(name,date_time=(1980,1,1,0,0,0))
                info.compress_type=ZIP_DEFLATED;info.external_attr=0o100644<<16
                z.writestr(info,raw)
            for name,p in files.items():
                raw=p.read_bytes()
                manifest['files'][name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
                write('AgeOfMachines/'+name,raw)
            write(MANIFEST,(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
        verify_archive(source,temp)
        os.replace(temp,archive)
    finally:
        temp.unlink(missing_ok=True)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    if args.verify_only:
        manifest=verify_archive(MOD,ARCHIVE)
    else:
        subprocess.run([sys.executable,str(ROOT/'tools/selfcheck.py')],cwd=ROOT,check=True)
        manifest=build_archive(MOD,ARCHIVE)
    report=ROOT/'outputs/install-validation.json'
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps({'archive':ARCHIVE.name,'source_files':len(manifest['files']),
        'sha256':hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),'zip_crc':True,
        'all_source_bytes_match':True},indent=2)+'\n')
    print('安装包校验通过：%d个源文件逐字节一致；%s'%(len(manifest['files']),ARCHIVE))


if __name__=='__main__':main()
