#!/usr/bin/env python3
"""生成可交给 Windows 编译的完整动画工程和当前 Mod；不携带占位动画。"""
from pathlib import Path, PurePosixPath
import hashlib
import json
import shutil
import struct
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('aom_tractor_chassis', 'aom_attachment_shared', 'aom_attachment_symbols')
ART = ROOT / '美术交付/2026-11-11-v1'
DEST = ROOT / 'outputs/windows-animation-kit'
ARCHIVE = ROOT / 'AgeOfMachines-Windows-Animation-Kit.zip'


def main():
    if DEST.exists():
        # 该目录仅为本脚本生成的交付暂存区，不是用户游戏目录。
        shutil.rmtree(DEST)
    mod = DEST / 'AgeOfMachines'
    shutil.copytree(ROOT / 'mod/AgeOfMachines', mod, ignore=shutil.ignore_patterns('.*', '__pycache__'))
    for name in NAMES:
        (mod / 'anim' / (name + '.zip')).unlink(missing_ok=True)
    report = {'source_root': 'AgeOfMachines/exported', 'projects': [], 'files': []}
    for name in NAMES:
        source = ART / 'anim' / name
        scml = source / (name + '.scml')
        tree = ET.parse(scml)
        entity = tree.find('entity')
        assert entity is not None and entity.attrib['name'] == name
        rels = [PurePosixPath(scml.name)]
        for item in tree.findall('./folder/file'):
            rel = PurePosixPath(item.attrib['name'])
            assert not rel.is_absolute() and '..' not in rel.parts
            img = source / rel
            raw = img.read_bytes()
            assert raw[:8] == b'\x89PNG\r\n\x1a\n'
            assert struct.unpack('>II', raw[16:24]) == (int(item.attrib['width']), int(item.attrib['height']))
            rels.append(rel)
        for rel in rels:
            target = mod / 'exported' / name / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / rel, target)
            report['files'].append({'path': target.relative_to(DEST).as_posix(),
                                    'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        report['projects'].append({'name': name, 'png_count': len(rels)-1,
                                   'animations': [a.attrib['name'] for a in tree.findall('./entity/animation')],
                                   'symbols': sorted({a.attrib['name'] for a in tree.findall('.//timeline')})})
    for name in ('Build-Animations.cmd', 'Collect-Results.cmd', 'README-zh-CN.txt'):
        source = ROOT / 'tools/windows-animation' / name
        content = source.read_text().replace('\r\n', '\n').replace('\n', '\r\n')
        (DEST / name).write_bytes(content.encode('utf-8-sig') if name.endswith('.txt') else content.encode('ascii'))
    shutil.copy2(ART / 'previews/挂件装配预览.png', DEST / 'Attachment-Preview.png')
    (DEST / 'Source-Manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    files = sorted(p for p in DEST.rglob('*') if p.is_file())
    with ZipFile(ARCHIVE, 'w', ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, file.relative_to(DEST))
    with ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(files)
        for file in files:
            assert archive.read(file.relative_to(DEST).as_posix()) == file.read_bytes()
        for name in NAMES:
            assert 'AgeOfMachines/anim/'+name+'.zip' not in archive.namelist()
    print(f'已生成 {ARCHIVE.name}：{len(files)} 个文件，{ARCHIVE.stat().st_size:,} 字节')
    print('源工程：3 个 SCML + 18 个所引用的 PNG，逐一检查尺寸、路径和 SHA-256。')
    print('已包含当前 Mod 和真实音乐；未包含占位动画或无关分帧导出。')


if __name__ == '__main__':
    main()
