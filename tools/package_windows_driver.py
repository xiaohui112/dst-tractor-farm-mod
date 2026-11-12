#!/usr/bin/env python3
"""交付驾驶室三视图、原版坐姿合成器与当前 Mod，供 Windows 一次构建。"""
from pathlib import Path, PurePosixPath
import hashlib
import json
import shutil
import struct
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'outputs/windows-driver-kit'
ARCHIVE=ROOT/'AgeOfMachines-Windows-Driver-Kit.zip'


def main():
    if DEST.exists():
        shutil.rmtree(DEST)
    mod=DEST/'Tractor'
    shutil.copytree(ROOT/'mod/Tractor',mod,ignore=shutil.ignore_patterns('.*','__pycache__'))
    for name in ('aom_tractor_driver.zip','aom_tractor_cabin.zip'):
        (mod/'anim'/name).unlink(missing_ok=True)
    source=ROOT/'assets/driver/aom_tractor_cabin'
    scml=source/'aom_tractor_cabin.scml'
    tree=ET.parse(scml)
    sources=[PurePosixPath(scml.name)]
    for entry in tree.findall('./folder/file'):
        rel=PurePosixPath(entry.attrib['name'])
        assert not rel.is_absolute() and '..' not in rel.parts
        data=(source/rel).read_bytes()
        assert data[:8]==b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>II',data[16:24])==(int(entry.attrib['width']),int(entry.attrib['height']))
        sources.append(rel)
    manifest={'project':'aom_tractor_cabin','native_game_assets_included':False,'files':[]}
    for rel in sources:
        target=mod/'exported/aom_tractor_cabin'/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source/rel,target)
        manifest['files'].append({'path':target.relative_to(DEST).as_posix(),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    for name in ('Build-Driver.cmd','Collect-Driver-Results.cmd','README-zh-CN.txt'):
        text=(ROOT/'tools/windows-driver'/name).read_text().replace('\r\n','\n').replace('\n','\r\n')
        (DEST/name).write_bytes(text.encode('utf-8-sig') if name.endswith('.txt') else text.encode('ascii'))
    shutil.copy2(ROOT/'tools/driver_animation.py',DEST/'driver_animation.py')
    shutil.copy2(ROOT/'assets/driver/seat-layout.json',DEST/'seat-layout.json')
    pending=ROOT/'mod/Tractor/scripts/aom_driver_visual_bank.lua'
    # 交付总是从未启用状态开始，只有成功合成了原版动作后才由 Windows 脚本启用。
    text='-- Pending Windows build.\nreturn { available=false, bank="aom_tractor_driver", build="aom_tractor_cabin" }\n'
    (DEST/'Driver-Pending.lua').write_text(text)
    (mod/'scripts/aom_driver_visual_bank.lua').write_text(text)
    (DEST/'Source-Manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    files=sorted(p for p in DEST.rglob('*') if p.is_file())
    with ZipFile(ARCHIVE,'w',ZIP_DEFLATED) as archive:
        for file in files:archive.write(file,file.relative_to(DEST))
    with ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None
        for file in files:assert archive.read(file.relative_to(DEST).as_posix())==file.read_bytes()
        assert len(files)==len(archive.namelist())
        for name in ('aom_tractor_chassis','aom_attachment_shared','aom_attachment_symbols'):
            assert 'Tractor/anim/'+name+'.zip' in archive.namelist()
    print('已生成 %s：%d 个文件，%.2f MiB，1 SCML + 8 PNG，保留三个已有世界动画。'%(ARCHIVE.name,len(files),ARCHIVE.stat().st_size/1024/1024))


if __name__=='__main__':main()
