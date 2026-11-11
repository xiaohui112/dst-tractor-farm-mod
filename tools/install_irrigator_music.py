#!/usr/bin/env python3
"""安装 FMOD Designer 导出的音频包；不把 WAV/MP3 伪装成 FEV/FSB。"""
import argparse
from pathlib import Path
import shutil
from music_bank import inspect_pair

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / 'mod/AgeOfMachines'
EVENT = 'aom_irrigator_music/irrigator/lanhuacao'


def install(export_dir: Path):
    names = ('aom_irrigator_music.fev', 'aom_irrigator_music.fsb')
    files = [export_dir / name for name in names]
    for path in files:
        if not path.is_file() or path.stat().st_size < 64:
            raise ValueError(f'缺少完整导出文件：{path}')
    fev, fsb = [path.read_bytes() for path in files]
    inspect_pair(fev, fsb)
    manifest = MOD / 'scripts/aom_irrigator_music_bank.lua'
    text = manifest.read_text()
    if 'available=false' not in text and 'available=true' not in text:
        raise ValueError('音频清单格式异常，未启用音频')
    sound = MOD / 'sound'
    sound.mkdir(exist_ok=True)
    for path in files:
        if path.resolve() != (sound / path.name).resolve():
            shutil.copy2(path, sound / path.name)
    manifest.write_text(text.replace('available=false', 'available=true'))
    print('已安装音频包并启用：' + EVENT)
    print('音频包结构、事件名称和编译配对检查通过；DST 中的实际混音仍需实机试听。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export_dir', type=Path, help='包含两个同名 FEV/FSB 导出文件的目录')
    args = parser.parse_args()
    try:
        install(args.export_dir)
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
