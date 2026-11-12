#!/usr/bin/env python3
"""Render the compiled equipment timelines, including the game's actual water pixels.

Preview only: native textures are decoded under outputs/ and never enter the Mod.
The SVG compositor uses the same BILD geometry and ANIM matrices as the game.
"""
import json
import os
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

from PIL import Image
from build_directional_art import ROOT,SOURCE,MOD,KTECH,run,VIEWS,KINDS
from build_attachment_animations import RIG,PHASES
from driver_animation import Reader,name_hash,parse_anim,read_game_zip

OUT=ROOT/'outputs/attachment-preview'
LABELS=['Plow','Seeder','Sprinkler','Fertilizer','Weeder','Harvester']


def native_sprites(filename,symbol):
    game=Path(os.environ.get('DST_GAME',str(Path.home()/
        "Library/Application Support/Steam/steamapps/common/Don't Starve Together/dontstarve_steam.app/Contents")))
    with read_game_zip(str(game),filename) as z:
        raw=z.read('build.bin');r=Reader(raw);r.read(8);count,_=r.unpack('2I');r.string()
        atlases=[r.string() for _ in range(r.unpack('I')[0])]
        records=[]
        for _ in range(count):
            key,n=r.unpack('2I');frames=[r.unpack('2I4f2I') for _ in range(n)]
            if key==name_hash(symbol):records=frames
        vertices=[r.unpack('6f') for _ in range(r.unpack('I')[0])]
        images=[]
        for atlas in atlases:
            tex=OUT/(filename+'-'+atlas);tex.write_bytes(z.read(atlas))
            png=tex.with_suffix('.png');run([KTECH,tex,png]);images.append(png)
    result=[]
    for rec in records:
        idx,duration,cx,cy,w,h,first,n=rec;vs=vertices[first:first+n]
        atlas=images[int(vs[0][-1])]
        with Image.open(atlas) as im:aw,ah=im.size
        left=round(min(v[3] for v in vs)*aw);right=round(max(v[3] for v in vs)*aw)
        top=round((1-max(v[4] for v in vs))*ah);bottom=round((1-min(v[4] for v in vs))*ah)
        target=OUT/f'{symbol}-{idx}.png'
        run(['magick',atlas,'-crop',f'{right-left}x{bottom-top}+{left}+{top}','+repage',target])
        result.append((target,cx-w/2,cy-h/2,w,h))
    return result


def layer(e,lookup):
    path,x,y,w,h=lookup[e['symbol']][e['frame']]
    values=','.join(f'{v:.5f}' for v in e['matrix'])
    return f'<image xlink:href="{escape(str(path))}" x="{x}" y="{y}" width="{w}" height="{h}" transform="matrix({values})"/>'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    lookup={}
    for name,paths in json.loads((RIG/'sprites.json').read_text()).items():
        lookup[name_hash(name)]=[]
        for path in paths:
            path=ROOT/path
            with Image.open(path) as im:w,h=im.size
            lookup[name_hash(name)].append((path,-w/2,-h,w,h))
    lookup[name_hash('water')]=native_sprites('player_actions_farming.zip','water')
    banks={}
    for name in ['shared','fx','water']:
        with ZipFile(MOD/'anim'/('aom_attachment_'+name+'.zip')) as z:
            banks[name]=parse_anim(z.read('anim.bin'))
    def get(which,name,mask):
        return next(a for a in banks[which]['animations'] if a['name']==name and a['facing']==mask)
    def cell(kind,index,phase,fx=True):
        _,mask=VIEWS[index];fr=get('shared',kind+'_work_loop',mask)['frames'][phase]
        content=''.join(layer(e,lookup) for e in sorted(fr['elements'],key=lambda e:e['z'],reverse=True))
        if fx:
            name={'seeder':'seed','weeder':'roots','harvester':'chaff','fertilizer':'fertilizer','irrigator':'spray'}.get(kind)
            if name:
                f=get('water' if kind=='irrigator' else 'fx',name,mask)['frames']
                content+=''.join(layer(e,lookup) for e in sorted(f[phase%len(f)]['elements'],key=lambda e:e['z'],reverse=True))
        return content
    def render(path,w,h,content):
        svg=OUT/(path.stem+'.svg')
        svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w}" height="{h}"><rect width="100%" height="100%" fill="#737660"/>'+content+'</svg>')
        run(['magick','-font','/System/Library/Fonts/Supplemental/Arial.ttf','-background','none',svg,path])
    frames=[];belts=[]
    for phase in range(PHASES):
        content=''
        for i,kind in enumerate(KINDS):
            x=150+(i%3)*300;y=195+(i//3)*245
            content+=f'<text x="{x}" y="{y-170}" text-anchor="middle" fill="#f6eacb" font-size="19">{LABELS[i]}</text>'
            content+=f'<g transform="translate({x},{y})">{cell(kind,0,phase)}</g>'
        path=OUT/f'all-{phase:02d}.png';render(path,900,490,content);frames.append(path)
        content=''
        for i,(view,_) in enumerate(VIEWS):
            content+=f'<text x="{140+i*280}" y="25" text-anchor="middle" fill="#f6eacb" font-size="16">{view}</text>'
            content+=f'<g transform="translate({140+i*280},195)">{cell("harvester",i,phase,False)}</g>'
        path=OUT/f'harvester-{phase:02d}.png';render(path,1400,230,content);belts.append(path)
    for paths,target in [(frames,'attachments-working-preview.gif'),(belts,'harvester-working-preview.gif')]:
        run(['magick','-delay','4','-loop','0',*paths,'-layers','Optimize',SOURCE/target])
    cells=[]
    for row,kind in enumerate(KINDS):
        for i,(view,_) in enumerate(VIEWS):
            content=f'<text x="140" y="25" text-anchor="middle" fill="#f6eacb" font-size="16">{LABELS[row]} / {view}</text>'
            content+=f'<g transform="translate(140,195)">{cell(kind,i,8)}</g>'
            target=OUT/f'direction-{kind}-{view}.png';render(target,280,230,content);cells.append(target)
    run(['magick','montage',*cells,'-geometry','+0+0','-tile','5x6',SOURCE/'attachments-working-directions.png'])
    (SOURCE/'attachments-working-directions.svg').unlink(missing_ok=True)
    print(SOURCE/'attachments-working-preview.gif')


if __name__=='__main__':main()
