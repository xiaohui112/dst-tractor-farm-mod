#!/usr/bin/env python3
"""从同一连接点配置生成六设备×五视图装配检查图（非游戏截图）。"""
import base64
from pathlib import Path
from PIL import Image
from mount_geometry import ROOT,SOURCE,LAYOUT,MASKS,point,offset,exhaust,occluded


def sprite(kind,view,dx=0,dy=0,mirror=False):
    p=SOURCE/'sprites'/kind/(view+'.png')
    with Image.open(p) as im:w,h=im.size
    uri='data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()
    return f'<g transform="translate({dx} {dy}) scale({-1 if mirror else 1} 1)"><image x="{-w/2}" y="{-h}" width="{w}" height="{h}" href="{uri}"/></g>'


def main():
    out=ROOT/'outputs/mount-geometry';out.mkdir(parents=True,exist_ok=True)
    kinds=list(LAYOUT['hitches']);parts=[]
    for row,kind in enumerate(kinds):
        for col,view in enumerate(LAYOUT['views']):
            i=col;dx,dy=offset(kind,i)
            tractor=sprite('tractor',view)
            tool='' if occluded(kind,MASKS[i]) else sprite(kind,view,dx,dy,kind=='harvester' and i in (0,1))
            rear_front=(kind!='harvester' and view in ('up','upside')) or (kind=='harvester' and view in ('down','downside','side'))
            x,y=point('tractor',i,LAYOUT['tractor']['front' if kind=='harvester' else 'rear'][i])
            ex,ey=exhaust(i)
            content=(tractor+tool if rear_front else tool+tractor)
            content+=f'<circle cx="{x}" cy="{y}" r="3" fill="#63e6b4"/><circle cx="{ex}" cy="{ey}" r="3" fill="#f3cf6f"/>'
            parts.append(f'<g transform="translate({col*430+215} {row*430+285}) scale(.72)">{content}</g>')
            parts.append(f'<text x="{col*430+215}" y="{row*430+410}" text-anchor="middle" font-family="sans-serif" font-size="18" fill="#e5ddc5">{kind} / {view}</text>')
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="2150" height="2580"><rect width="100%" height="100%" fill="#4b493a"/>'+''.join(parts)+'</svg>'
    (out/'all-equipment.svg').write_text(svg)
    print(out/'all-equipment.svg')


if __name__=='__main__':main()
