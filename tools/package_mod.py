#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 mod/AgeOfMachines 打成可直接解压进 mods 目录的 AgeOfMachines.zip。"""
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / 'mod' / 'AgeOfMachines'
ARCHIVE = ROOT / 'AgeOfMachines.zip'
SKIP_PARTS = {'__pycache__', '.DS_Store'}
REQUIRED = ('modinfo.lua', 'modmain.lua', 'modicon.tex', 'scripts/aom_driver_visual_bank.lua',
            'anim/aom_tractor_chassis.zip', 'anim/aom_attachment_shared.zip',
            'anim/aom_attachment_symbols.zip', 'sound/aom_irrigator_music.fsb')


def main():
    files = sorted(p for p in MOD.rglob('*')
                   if p.is_file() and not (set(p.relative_to(MOD).parts) & SKIP_PARTS))
    for name in REQUIRED:
        if not (MOD / name).is_file():
            raise SystemExit('ERROR: 缺少 ' + name)
    with ZipFile(ARCHIVE, 'w', ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, 'AgeOfMachines/' + file.relative_to(MOD).as_posix())
    with ZipFile(ARCHIVE) as archive:
        if archive.testzip() is not None:
            raise SystemExit('ERROR: 压缩包 CRC 校验失败')
        names = archive.namelist()
        if len(names) != len(files):
            raise SystemExit('ERROR: 压缩包文件数与目录不一致')
        for file in files:
            entry = 'AgeOfMachines/' + file.relative_to(MOD).as_posix()
            if archive.read(entry) != file.read_bytes():
                raise SystemExit('ERROR: 内容不一致 ' + entry)
        if not any(n.endswith('anim/aom_tractor_driver.zip') for n in names):
            # 驾驶动画未接入时仍应可打包；这里只提醒，不阻断。
            print('提示：本包未包含驾驶动画，安装后驾驶室坐姿保持原版。')
    digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    print('已生成 %s：%d 个文件，%.1f MiB'
          % (ARCHIVE.name, len(files), ARCHIVE.stat().st_size / 1024.0 / 1024.0))
    print('SHA-256 ' + digest)


if __name__ == '__main__':
    main()
