#!/usr/bin/env python3
"""Build the field rain barrel's world sprite and crafting icon."""
from PIL import Image

from build_directional_art import KTECH, MOD, ROOT, STAGE, animation, bank, compile_build, element, frame, run, save


NAME = 'aom_rain_barrel'
SOURCE = ROOT / 'assets/images/source-art' / f'{NAME}.png'


def main():
    STAGE.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE) as original:
        sprite = original.convert('RGBA')
    bounds = sprite.getchannel('A').getbbox()
    if not bounds or bounds == (0, 0, sprite.width, sprite.height):
        raise ValueError('The barrel source needs a transparent border around the prop')
    sprite = sprite.crop(bounds)
    sprite.thumbnail((240, 240), Image.Resampling.LANCZOS)
    world_sprite = STAGE / f'{NAME}-world.png'
    sprite.save(world_sprite)

    symbols = {'barrel': [world_sprite]}
    pose = frame([element('barrel')])
    pose['bbox'] = (0., -sprite.height / 2, float(sprite.width), float(sprite.height))
    build, texture = compile_build(NAME, symbols, compact=True)
    save(NAME, build, bank(NAME, [animation(NAME, 'idle', 255, [pose])], symbols), texture)

    sprite.thumbnail((116, 116), Image.Resampling.LANCZOS)
    icon = Image.new('RGBA', (128, 128))
    icon.paste(sprite, ((128 - sprite.width) // 2, (128 - sprite.height) // 2))
    icon_path = STAGE / f'{NAME}-icon.png'
    icon.save(icon_path)
    run([KTECH, icon_path, MOD / f'images/{NAME}.tex'])
    (MOD / f'images/{NAME}.xml').write_text(
        f'<Atlas><Texture filename="{NAME}.tex"/><Elements>'
        f'<Element name="{NAME}.tex" u1="0" u2="1" v1="0" v2="1"/>'
        '</Elements></Atlas>\n'
    )


if __name__ == '__main__':
    main()
