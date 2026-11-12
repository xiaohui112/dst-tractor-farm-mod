#!/usr/bin/env python3
"""Render previews from the same sprite indices and transforms as the game bank."""
from pathlib import Path
import subprocess
from PIL import Image
from build_directional_art import ROOT,SOURCE,VIEWS,vehicle_layers


def run(args):subprocess.run([str(v) for v in args],check=True,capture_output=True)


def main():
    out=ROOT/'outputs/vehicle-preview';out.mkdir(parents=True,exist_ok=True)
    frames=[]
    for index,(view,mask) in enumerate(VIEWS):
        for phase in range(12):
            args=['magick','-size','640x440','xc:#676958']
            layers=vehicle_layers(index,mask,phase)
            for e in sorted(layers,key=lambda e:e['z'],reverse=True):
                from driver_animation import name_hash
                if e['symbol']==name_hash('body'):path=SOURCE/'sprites/tractor'/(view+'.png')
                elif e['symbol']==name_hash('aom_wheels'):path=SOURCE/'rig'/f'wheel-{index}-{phase}.png'
                else:continue
                with Image.open(path) as im:w,h=im.size
                matrix=e['matrix'];x=320+matrix[4]-w/2;y=395+matrix[5]-h
                args += [path,'-geometry',f'{int(x):+d}{int(y):+d}','-composite']
            frame=out/f'{index}-{phase:02d}.png'
            run(args+[frame]);frames.append(frame)
    gif=SOURCE/'tractor-driving-preview.gif'
    run(['magick','-delay','7','-loop','0',*frames,'-layers','Optimize',gif])
    rows=[]
    for kind in ['tractor','plow','seeder','irrigator','fertilizer','weeder','harvester']:
        row=out/(kind+'.png')
        sources=[SOURCE/'sprites'/kind/(v+'.png') for v,_ in VIEWS]
        run(['magick','montage',*sources,'-background','#676958','-gravity','center',
             '-geometry','280x310+8+8','-tile','5x1',row]);rows.append(row)
    run(['magick',*rows,'-append',SOURCE/'all-directions-preview.png'])
    print(gif)


if __name__=='__main__':main()
