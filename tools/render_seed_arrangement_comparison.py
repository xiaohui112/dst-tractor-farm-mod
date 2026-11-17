#!/usr/bin/env python3
"""Render measured before/after layouts, using the verifier's native crop icons."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
NAMES = {'screenshot-5x5': '截图：秋季 5×5，各192颗', 'L-full': 'L形农田', 'U-full': 'U形农田', 'ring-full': '环形农田', 'limited-equal': '库存受限：三种各40颗'}
FONT = '/System/Library/Fonts/STHeiti Medium.ttc'


def font(size):
    return ImageFont.truetype(FONT, size)


def panel(canvas, row, label, box):
    draw = ImageDraw.Draw(canvas)
    left, top, right, bottom = box
    draw.rounded_rectangle(box, 14, fill='#302c25', outline='#6b624b', width=2)
    r = row[label][0]
    summary = row['summary'][label]
    draw.text((left + 20, top + 16), '修改前' if label == 'before' else '修改后', font=font(26), fill='#efdfbb')
    draw.text((left + 20, top + 56), f"{r['count']} 株 · 异图案地皮 {summary['mismatched_tiles']} 块", font=font(18), fill='#d4c9ac')
    draw.text((left + 20, top + 85), f"排列 CPU {summary['arrangement_ms']:.1f} ms · 数量 CPU {summary['quantity_ms']:.1f} ms", font=font(16), fill='#b1bd8b')
    scene = row['input']
    width, height = scene['width'], scene['height']
    pitch = min((right-left-64)/(width*3), (bottom-top-150)/(height*3))
    x0 = (left+right-width*3*pitch)/2
    y0 = top + 126 + max(0, (bottom-top-150-height*3*pitch)/2)
    patterns = r['pattern_metrics']['patterns']
    other = row['after' if label == 'before' else 'before'][0]['pattern_metrics']['patterns']
    icons = {}
    for tile, motif in patterns.items():
        tx, tz = map(float, tile.split(','))
        x, y = x0+tx*3*pitch, y0+tz*3*pitch
        changed = motif != other.get(tile)
        draw.rounded_rectangle((x+1, y+1, x+3*pitch-2, y+3*pitch-2), 5, fill='#786d4f', outline=('#dc9a64' if label=='before' else '#b4ca78') if changed else '#ad9b73', width=3 if changed else 1)
        for s, crop in enumerate(motif):
            px, py = x+(s%3+.5)*pitch, y+(s//3+.5)*pitch
            draw.ellipse((px-pitch*.39,py-pitch*.39,px+pitch*.39,py+pitch*.39),fill='#8c805b')
            if crop == '_':
                continue
            if crop not in icons:
                path=ROOT/'web/giant-seed-verifier/static/assets/crops'/f'{crop}_oversized.png'
                image=Image.open(path).convert('RGBA')
                image.thumbnail((round(pitch*.94), round(pitch*.94)), Image.Resampling.LANCZOS)
                icons[crop]=image
            image=icons[crop]
            canvas.paste(image,(round(px-image.width/2),round(py-image.height/2)),image)


def main():
    global FONT
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('report',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--font',default=FONT)
    args=p.parse_args()
    FONT=args.font
    report=json.loads(args.report.read_text())
    rows={c['id']:c for c in report['cases']}
    args.output.mkdir(parents=True,exist_ok=True)
    canvas=Image.new('RGB',(1500,920),'#1e211d');draw=ImageDraw.Draw(canvas)
    draw.text((34,24),'最大播种量不变，优先统一整体图案',font=font(32),fill='#eee4c9')
    draw.text((34,72),NAMES['screenshot-5x5']+' · 胡萝卜 / 玉米 / 土豆',font=font(20),fill='#c7c4aa')
    row=rows['screenshot-5x5']
    panel(canvas,row,'before',(24,118,738,822));panel(canvas,row,'after',(762,118,1476,822))
    draw.text((34,846),'边框高亮本次改变的地皮；25块地皮均种满，三种各75株。',font=font(19),fill='#ded2b2')
    draw.text((34,878),'本机三轮中位数；CPU耗时与网页后端耗时分开记录，不代表游戏内等待或生长实测。',font=font(16),fill='#aaa98e')
    canvas.save(args.output/'screenshot-before-after.png')
    canvas=Image.new('RGB',(1500,1810),'#1e211d');draw=ImageDraw.Draw(canvas)
    draw.text((28,18),'不同库存与不规则农田：新旧布局对照',font=font(29),fill='#eee4c9')
    for i,name in enumerate(('L-full','U-full','ring-full','limited-equal')):
        row=rows[name];y=70+i*430
        draw.text((28,y),NAMES[name],font=font(21),fill='#eee4c9')
        panel(canvas,row,'before',(24,y+32,738,y+415));panel(canvas,row,'after',(762,y+32,1476,y+415))
    canvas.save(args.output/'irregular-before-after.png')
    print(args.output/'screenshot-before-after.png')
    print(args.output/'irregular-before-after.png')


if __name__=='__main__':
    main()
