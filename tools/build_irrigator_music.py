#!/usr/bin/env python3
"""使用 FMOD Designer 命令行重建《兰花草》音频包（支持原生 Windows 或 Wine）。"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import tempfile
from install_irrigator_music import install
from music_bank import inspect_pair

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--designer', type=Path, required=True, help='fmod_designercl.exe 的路径')
    parser.add_argument('--wine', type=Path, help='macOS/Linux 上可用的 Wine 可执行文件')
    args = parser.parse_args()
    project = ROOT / 'assets/audio/fmod/aom_irrigator_music.fdp'
    def platform_path(path):
        absolute = str(path.resolve())
        return 'Z:' + absolute.replace('/', '\\') if args.wine else absolute
    with tempfile.TemporaryDirectory(prefix='aom-music-') as out:
        command = ([str(args.wine.resolve())] if args.wine else []) + [str(args.designer.resolve()),
                    '-pc', '-b', platform_path(Path(out)), platform_path(project)]
        result = subprocess.run(command, cwd=project.parent, capture_output=True, text=True, errors='replace')
        print(result.stdout)
        if result.returncode:
            raise SystemExit(result.stderr or 'FMOD Designer 编译失败')
        install(Path(out))
        record = project.with_name('build.json')
        previous = json.loads(record.read_text()) if record.exists() else {}
        info = inspect_pair((Path(out) / 'aom_irrigator_music.fev').read_bytes(),
                            (Path(out) / 'aom_irrigator_music.fsb').read_bytes())
        previous.update(info)
        version = re.search(r"FMOD Designer [0-9.]+", result.stdout)
        previous.update(compiler=version.group(0) if version else 'FMOD Designer',
                        compiler_sha256=hashlib.sha256(args.designer.read_bytes()).hexdigest(),
                        project=str(project.relative_to(ROOT)),
                        project_sha256=hashlib.sha256(project.read_bytes()).hexdigest())
        record.write_text(json.dumps(previous, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
