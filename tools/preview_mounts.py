#!/usr/bin/env python3
"""读取SCML的原生变换和原始PNG，生成可编辑SVG场景；不修改位图素材。"""
from pathlib import Path
import base64
import math
import xml.etree.ElementTree as ET
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'美术交付/2026-11-11-v1'
SCML=ART/'anim/aom_tractor_chassis/aom_tractor_chassis.scml'
PREVIEW=ART/'previews'
LABELS=[('empty','未安装'),('plow','犁头'),('seeder','播种机'),('irrigator','洒水挂件'),
        ('fertilizer','施肥挂件'),('weeder','除草挂件'),('harvester','收割台（车头）')]


def layers(kind):
    root=ET.parse(SCML).getroot()
    files={(f.get('id'),i.get('id')):i for f in root.findall('folder') for i in f.findall('file')}
    anim=root.find("entity/animation[@name='idle']")
    timelines={t.get('id'):t for t in anim.findall('timeline')}
    result=[]
    refs=sorted(anim.find('mainline/key').findall('object_ref'),key=lambda r:int(r.get('z_index')))
    for ref in refs:
        timeline=timelines[ref.get('timeline')];name=timeline.get('name')
        if name=='attachment_front' and kind!='harvester':continue
        obj=timeline.find(f"key[@id='{ref.get('key')}']/object")
        file=files[(obj.get('folder'),obj.get('file'))]
        path=SCML.parent/file.get('name')
        if name=='attachment':
            symbol='empty' if kind=='harvester' else kind
            path=ART/f'anim/aom_attachment_symbols/{symbol}/{symbol}-0.png'
        if name=='attachment_front':path=ART/'anim/aom_attachment_symbols/harvester/harvester-0.png'
        w,h=float(file.get('width')),float(file.get('height'))
        px,py=float(file.get('pivot_x'))*w,(1-float(file.get('pivot_y')))*h
        x,y=128+float(obj.get('x')),256-float(obj.get('y'))
        sx,sy=float(obj.get('scale_x')),float(obj.get('scale_y'))
        angle=-float(obj.get('angle'))*math.pi/180
        ca,sa=math.cos(angle),math.sin(angle)
        a,b,c,d=ca*sx,sa*sx,-sa*sy,ca*sy
        e,f=x-a*px-c*py,y-b*px-d*py
        with Image.open(path) as im:bbox=im.getbbox()
        corners=[(a*u+c*v+e,b*u+d*v+f) for u in (bbox[0],bbox[2]) for v in (bbox[1],bbox[3])]
        uri='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()
        result.append((f'<image width="{w}" height="{h}" href="{uri}" transform="matrix({a} {b} {c} {d} {e} {f})"/>',corners))
    return result


def composition(kind,cx,cy,maxw,maxh,scale_limit=1):
    objects=layers(kind);points=[p for _,corners in objects for p in corners]
    x0,x1=min(p[0] for p in points),max(p[0] for p in points)
    y0,y1=min(p[1] for p in points),max(p[1] for p in points)
    s=min(maxw/(x1-x0),maxh/(y1-y0),scale_limit)
    return f'<g transform="translate({cx} {cy}) scale({s}) translate({-(x0+x1)/2} {-(y0+y1)/2})">'+''.join(o for o,_ in objects)+'</g>'


def document(w,h,content):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="#65695a"/>{content}</svg>'


def main():
    PREVIEW.mkdir(exist_ok=True)
    panels=[]
    for i,(kind,label) in enumerate(LABELS):
        x,y=i%4*280,i//4*330
        panels.append(composition(kind,x+140,y+180,252,210))
        panels.append(f'<text x="{x+140}" y="{y+292}" text-anchor="middle" font-family="PingFang SC,Arial,sans-serif" font-size="20" fill="#e2d9b5">{label}</text>')
    (PREVIEW/'挂件装配预览.svg').write_text(document(1120,660,''.join(panels)))
    detail=composition('harvester',320,180,580,315,2)
    detail+='<text x="320" y="378" text-anchor="middle" font-family="PingFang SC,Arial,sans-serif" font-size="24" fill="#e2d9b5">收割台 · 车头安装</text>'
    (PREVIEW/'收割台车头装配.svg').write_text(document(640,400,detail))
    print('SVG预览已从SCML生成，PNG原始素材保持不变。')


if __name__=='__main__':main()
