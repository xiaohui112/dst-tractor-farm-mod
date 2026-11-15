#!/usr/bin/env python3
"""Extract native oversized inventory icons from the local DST atlas (Klei assets)."""
from pathlib import Path
from zipfile import ZipFile
import argparse
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from PIL import Image

HERE = Path(__file__).resolve().parent
CROPS = ('carrot', 'corn', 'potato', 'tomato', 'asparagus', 'eggplant', 'pumpkin',
         'watermelon', 'dragonfruit', 'durian', 'garlic', 'onion', 'pepper', 'pomegranate')
DEFAULT_IMAGES = Path.home() / "Library/Application Support/Steam/steamapps/common/Don't Starve Together/dontstarve_steam.app/Contents/data/databundles/images.zip"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-images', type=Path, default=DEFAULT_IMAGES)
    parser.add_argument('--ktech', type=Path, default=Path.home() / '.local/bin/ktech')
    args = parser.parse_args()
    output = HERE / 'static/assets/crops'
    extracted = set()
    with ZipFile(args.game_images) as bundle, tempfile.TemporaryDirectory() as tmp:
        for name in bundle.namelist():
            if not name.startswith('images/inventoryimages') or not name.endswith('.xml'):
                continue
            root = ET.fromstring(bundle.read(name))
            wanted = {e.get('name'): e for e in root.iter('Element')
                      if e.get('name') in {c + '_oversized.tex' for c in CROPS}}
            if not wanted:
                continue
            texture = 'images/' + root.find('Texture').get('filename')
            tex = Path(tmp) / Path(texture).name
            tex.write_bytes(bundle.read(texture))
            png = tex.with_suffix('.png')
            subprocess.run([str(args.ktech), str(tex), str(png)], check=True, capture_output=True)
            with Image.open(png) as atlas:
                width, height = atlas.size
                for icon, element in wanted.items():
                    uv = {k: float(element.get(k)) for k in ('u1', 'u2', 'v1', 'v2')}
                    box = (round(uv['u1'] * width), round((1 - uv['v2']) * height),
                           round(uv['u2'] * width), round((1 - uv['v1']) * height))
                    atlas.crop(box).save(output / Path(icon).with_suffix('.png').name)
                    extracted.add(icon.removesuffix('_oversized.tex'))
    if extracted != set(CROPS):
        raise RuntimeError('Missing native icons: ' + ', '.join(sorted(set(CROPS) - extracted)))
    print(f'Extracted {len(extracted)} oversized icons to {output}')


if __name__ == '__main__':
    main()
