#!/usr/bin/env python3
"""Build six directional equipment rigs, particles and a native-water animation bank.

Existing painted sprites stay the source of truth. Masks split mechanical parts;
SVGs add editable spokes, soil and particles. Native water textures stay in DST:
the water ZIP only contains our animation and references player_actions_farming.
"""
import hashlib
import json
import math
import os
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image
from build_directional_art import (ROOT, SOURCE, MOD, STAGE, VIEWS, KINDS, run,
    compile_build, element, frame, animation, bank, save)
from driver_animation import Reader, name_hash, parse_anim, read_game_zip, write_anim

RIG=SOURCE/'attachment-rig'
PHASES=24
# Coordinates are fractions of the unchanged, trimmed five-view source sprites.
# These are the *single* exposed cutter row; rear views naturally hide the cutter.
CUTTER=[[(.08,.61),(.60,.70),(.60,.995),(.005,.89)],
        [(.015,.85),(.28,.70),(.34,.87),(.005,.995)],
        [(.87,.70),(.995,.76),(.995,.88),(.90,.85)],
        [(.075,.665),(.92,.665),(.90,.995),(.09,.995)],
        [(.15,.95),(.85,.95),(.85,.985),(.15,.985)]]
NOZZLES=[[(.32,.91),(.64,.87)],[(.31,.91),(.64,.91)],
         [(.11,.80),(.22,.82),(.34,.84),(.46,.86),(.58,.87)],
         [(.29,.94),(.70,.94)],
         [(.22,.87),(.36,.87),(.50,.87),(.65,.87),(.79,.87)]]
DISCS=[(.36,.80,.21,.063),(.42,.84,.23,.045),(.41,.80,.20,.065),
       (.50,.81,.27,.07),(.50,.80,.27,.047)]
PLOW_TIPS=[[(.21,.87),(.49,.94),(.77,.99)],[(.23,.98),(.53,.98),(.82,.98)],
           [(.20,.99),(.49,.86),(.76,.74)],[(.20,.99),(.50,.99),(.80,.99)],
           [(.20,.99),(.50,.99),(.80,.99)]]


def svg(path,w,h,content):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" '
                    f'xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}">'
                    +content+'</svg>')
    out=path.with_suffix('.png')
    run(['magick','-background','none',path,'PNG32:'+str(out)])
    return out


def polygon(w,h,points):
    return ' '.join(f'{x*w:.4f},{y*h:.4f}' for x,y in points)


def split(path,kind,view,points):
    with Image.open(path) as im:w,h=im.size
    mask=svg(RIG/f'{kind}-{view}-mask.svg',w,h,
        '<rect width="100%" height="100%" fill="black"/>'
        f'<polygon points="{polygon(w,h,points)}" fill="white"/>')
    moving=RIG/f'{kind}-{view}-moving.png';body=RIG/f'{kind}-{view}-body.png'
    # Multiply alpha instead of replacing it: transparent holes stay transparent.
    for out,invert in [(moving,False),(body,True)]:
        run(['magick',path,'(',mask,*(['-negate'] if invert else []),')',
             '-alpha','off','-compose','CopyOpacity','-composite',
             path,'-compose','DstIn','-composite','PNG32:'+str(out)])
    return body,moving


def spinning(symbol,index,cx,cy,angle,rx,ry,z=-.2):
    # Rotate the drawing inside a 32px sprite, then flatten it into the disc.
    # Axis-aligned matrices keep the pivot stable in both engine and preview.
    phase=round(angle/math.tau*PHASES)%PHASES
    out=element(symbol,phase,z=z)
    out['matrix']=[rx/16,0,0,ry/16,cx,cy+ry]
    return out


def rig_parts(sprites):
    parts={};sizes={}
    for kind in KINDS:
        sizes[kind]=[]
        for i,(view,_) in enumerate(VIEWS):
            path=sprites[kind][i]
            with Image.open(path) as im:w,h=im.size
            sizes[kind].append((w,h))
            if kind in ('plow','weeder','harvester','seeder'):
                if kind=='harvester':points=CUTTER[i]
                elif kind=='seeder':
                    points=[(.12,0),(.83,0),(.83,.26),(.67,.49),(.30,.49),(.12,.27)]
                else:
                    top=.49 if kind=='plow' else .50
                    points=[(0,top),(1,top),(1,1),(0,1)]
                body,moving=split(path,kind,view,points)
                parts.setdefault(kind+'_body',[]).append(body)
                parts.setdefault(kind+'_moving',[]).append(moving)
                if kind=='harvester':
                    # Translate the one original tooth strip to the right along its
                    # rail. A second tiled copy wraps under the ends, not a second row.
                    a,b=CUTTER[i][:2];dx=(b[0]-a[0])*w;dy=(b[1]-a[1])*h
                    for phase in range(PHASES):
                        shift=phase/PHASES/6
                        content=f'<defs><clipPath id="rail"><polygon points="{polygon(w,h,points)}"/></clipPath></defs>'
                        content+='<g clip-path="url(#rail)">'
                        for wrap in (-1,0,1):
                            content+=f'<image xlink:href="{moving}" width="{w}" height="{h}" '
                            content+=f'transform="translate({(shift+wrap)*dx:.5f},{(shift+wrap)*dy:.5f})"/>'
                        content+='</g>'
                        out=svg(RIG/f'harvester-{view}-belt-{phase:02d}.svg',w,h,content)
                        # ImageMagick's built-in SVG renderer does not consistently
                        # clip image nodes. Enforce the rail mask in the raster too.
                        mask=RIG/f'harvester-{view}-mask.png'
                        run(['magick',out,mask,'-alpha','off','-compose','CopyOpacity',
                             '-composite',out,'-compose','DstIn','-composite','PNG32:'+str(out)])
                        parts.setdefault('harvester_belt',[]).append(out)
            if kind=='plow':
                soil=''
                for cx,tip_y in PLOW_TIPS[i]:
                    cy=tip_y*h
                    soil+=f'<ellipse cx="{w*cx:.2f}" cy="{cy-3.5:.2f}" rx="{w*.125:.2f}" ry="3.2" fill="#61503a" stroke="#3f362b" stroke-width="1"/>'
                    soil+=f'<path d="M{w*(cx-.06):.2f},{cy-4.5:.2f} l3,-2 4,1 4,-1 3,2" fill="#756047" stroke="#51412e" stroke-width=".8"/>'
                parts.setdefault('plow_soil',[]).append(svg(RIG/f'plow-{view}-soil.svg',w,h,soil))
    parts['aom_meter']=[]
    for phase in range(PHASES):
        cog='<circle cx="16" cy="16" r="14" fill="none" stroke="#44392a" stroke-width="2"/>'
        for i in range(5):
            a=(i/5+phase/PHASES)*math.tau
            cog+=f'<path d="M16,16 L{16+12*math.cos(a):.4f},{16+12*math.sin(a):.4f}" stroke="#d6b66f" stroke-width="2"/>'
        cog+='<circle cx="16" cy="16" r="3" fill="#50402c" stroke="#d6b66f"/>'
        parts['aom_meter'].append(svg(RIG/f'meter-{phase:02d}.svg',32,32,cog))
    return parts,sizes


def equipment_frame(kind,index,phase,engaged,sizes):
    w,h=sizes[kind][index];angle=phase/PHASES*math.tau
    wave=math.sin(angle*2)
    if kind=='plow':
        blade=element('plow_moving',index,z=-.1)
        stretch=(7+wave*.7)*engaged/(h*.51)
        blade['matrix'][3]=1+stretch
        blade['matrix'][5]=h*.51*stretch
        es=[element('plow_body',index),blade]
        if engaged>.3:es.append(element('plow_soil',index,y=8,z=-.2))
    elif kind=='seeder':
        es=[element('seeder_body',index),element('seeder_moving',index,y=wave*1.2*engaged,z=-.1)]
        cx,cy=(.19,.65) if index<3 else (.50,.64)
        es.append(spinning('aom_meter',0,(cx-.5)*w,(cy-1)*h,angle*engaged,5,5))
    elif kind=='weeder':
        es=[element('weeder_body',index),element('weeder_moving',index,
            x=wave*2.4*engaged,y=(1+math.cos(angle*2))*engaged,z=-.1)]
    elif kind=='harvester':
        es=[element('harvester_body',index),
            element('harvester_belt',index*PHASES+phase,z=-.1)]
    elif kind=='fertilizer':
        cx,cy,rx,ry=DISCS[index]
        es=[element(kind,index),spinning('aom_meter',0,(cx-.5)*w,(cy-1)*h,
            angle*engaged,rx*w,ry*h)]
    else:
        es=[element(kind,index)]
        # Small pressure valve turns; tank stays rigid. Water is a separate native FX.
        es.append(spinning('aom_meter',0,-w*.03,-h*.16,angle*engaged,3.3,3.3))
    return frame(es)


def particle_assets():
    return {
        'aom_seed':[svg(RIG/'seed.svg',12,10,
            '<path d="M1,8 Q1,1 10,1 Q11,8 1,8Z" fill="#d3b376" stroke="#57452f" stroke-width="1.5"/>')],
        'aom_pellet':[svg(RIG/'pellet.svg',10,10,
            '<path d="M1,4 L4,1 L8,2 L9,7 L6,9 L2,8Z" fill="#745337" stroke="#392d23" stroke-width="1.3"/>')],
        'aom_leaf':[svg(RIG/'leaf.svg',15,12,
            '<path d="M1,10 Q2,0 14,1 Q12,12 1,10Z" fill="#829144" stroke="#3e482b" stroke-width="1.2"/>'
            '<path d="M2,10 L12,2" stroke="#c1bb71"/>')],
        'aom_root':[svg(RIG/'root.svg',16,14,
            '<path d="M2,1 Q14,4 6,12 M8,5 L14,8 M9,7 L2,9" fill="none" stroke="#6f5638" stroke-width="2"/>')],
    }


def build_particles():
    name='aom_attachment_fx';symbols=particle_assets();an=[]
    for index,(_,mask) in enumerate(VIEWS):
        for kind in ['seed','fertilizer','roots','chaff']:
            fs=[]
            for f in range(20):
                es=[]
                count=3 if kind=='seed' else 14 if kind=='fertilizer' else 9
                for j in range(count):
                    t=(f+(j%4)*4)%20/20 if kind=='fertilizer' else max(0,(f-j*.7)/20)
                    if kind=='seed':
                        symbol='aom_seed';x=(j-1)*5;y=-48+48*t*t;scale=.65*(1-t*.4)
                    else:
                        symbol='aom_pellet' if kind=='fertilizer' else 'aom_root' if kind=='roots' and j%3==0 else 'aom_leaf'
                        # Backward fan follows the facing, with separate screen spread.
                        backward=[(-.40,-.10),(-.70,0),(-.35,.18),(0,-.32),(0,.35)][index]
                        spread=(j/(count-1)-.5)
                        x=spread*70*t+backward[0]*t*45
                        y=-16+backward[1]*t*45-42*math.sin(t*math.pi)+22*t
                        scale=(.45 if kind=='fertilizer' else .65)*(1-t*.4)
                    es.append(element(symbol,0,x=x,y=y,scale=scale,z=-j*.001))
                fs.append(frame(es))
            an.append(animation(name,kind,mask,fs))
    b,t=compile_build(name,symbols,compact=True)
    return save(name,b,bank(name,an,symbols),t)


def build_water(sizes):
    game=Path(os.environ.get('DST_GAME',str(Path.home()/
        "Library/Application Support/Steam/steamapps/common/Don't Starve Together/dontstarve_steam.app/Contents")))
    # Verify the owning native build rather than guessing symbol names/indices.
    with read_game_zip(str(game),'player_actions_farming.zip') as native:
        raw=native.read('build.bin');native_anim=parse_anim(native.read('anim.bin'))
    r=Reader(raw);r.read(8);ns,_=r.unpack('2I');assert r.string()=='player_actions_farming'
    for _ in range(r.unpack('I')[0]):r.string()
    water=None
    for _ in range(ns):
        key,n=r.unpack('2I');records=[r.unpack('2I4f2I') for _ in range(n)]
        if key==name_hash('water'):water=records
    if not water or len(water)!=4:raise ValueError('Native watering-can water symbol changed')
    assert any(a['name']=='water' for a in native_anim['animations'])
    an=[];name='aom_attachment_water'
    for index,(_,mask) in enumerate(VIEWS):
        w,h=sizes['irrigator'][index];fs=[]
        for f in range(PHASES):
            es=[]
            for j,(nx,ny) in enumerate(NOZZLES[index]):
                e=element('water',(f//3+j)%4,x=(nx-.5)*w,y=(ny-1)*h,
                          scale=.20,z=0)
                # Native water begins near y=-15 and falls about 220px in build space.
                # Anisotropic scale forms a small downward shower at each real nozzle.
                e['matrix'][0]=.17
                e['matrix'][2]=[-.04,-.05,.025,0,0][index]
                es.append(e)
            fs.append(frame(es))
        an.append(animation(name,'spray',mask,fs))
    rawanim=write_anim(bank(name,an,['water']))
    with ZipFile(MOD/'anim'/(name+'.zip'),'w',ZIP_DEFLATED) as z:z.writestr('anim.bin',rawanim)
    return hashlib.sha256((MOD/'anim'/(name+'.zip')).read_bytes()).hexdigest(),{
        'native_build':'player_actions_farming','native_symbol':'water',
        'native_build_sha256':hashlib.sha256(raw).hexdigest(),
        'native_frames':[v[0] for v in water],'textures_copied':False}


def sync_reports(digest):
    # Standalone equipment rebuilds also invalidate this entry in the older
    # combined vehicle reports. Keep their retained vehicle hashes untouched.
    for path in [MOD/'Driver-Build-Report.json',SOURCE/'build.json']:
        if not path.exists():continue
        report=json.loads(path.read_text())
        report.setdefault('sha256',{}).update(digest)
        report['attachment_report']='Attachment-Build-Report.json'
        path.write_text(json.dumps(report,indent=2)+'\n')


def build(sprites=None):
    STAGE.mkdir(parents=True,exist_ok=True)
    RIG.mkdir(parents=True,exist_ok=True)
    if sprites is None:
        sprites={k:[SOURCE/'sprites'/k/(view+'.png') for view,_ in VIEWS] for k in KINDS}
        sprites['empty']=[SOURCE/'sprites/empty.png']
    parts,sizes=rig_parts(sprites)
    symbols={k:sprites[k] for k in KINDS};symbols['empty']=sprites['empty']*5
    symbols.update(parts);name='aom_attachment_shared';an=[]
    (RIG/'sprites.json').write_text(json.dumps({k:[p.relative_to(ROOT).as_posix() for p in v]
        for k,v in {**symbols,**particle_assets()}.items()},indent=2)+'\n')
    for kind in KINDS+['empty']:
        for index,(_,mask) in enumerate(VIEWS):
            an.append(animation(name,kind,mask,[frame([element(kind,index)])]))
            if kind=='empty':continue
            for suffix,length in [('pre',6),('loop',PHASES),('pst',6)]:
                fs=[]
                for f in range(length):
                    engaged=(f+1)/length if suffix=='pre' else 1-(f+1)/length if suffix=='pst' else 1
                    phase=f if suffix=='loop' else 0
                    if suffix=='pst' and f==length-1:fr=frame([element(kind,index)])
                    else:fr=equipment_frame(kind,index,phase,engaged,sizes)
                    fs.append(fr)
                an.append(animation(name,kind+'_work_'+suffix,mask,fs))
    b,t=compile_build(name,symbols,compact=True)
    digest={name:save(name,b,bank(name,an,symbols),t),
            'aom_attachment_fx':build_particles()}
    digest['aom_attachment_water'],native=build_water(sizes)
    report={'schema':1,'facing_masks':[m for _,m in VIEWS],'work_phases':PHASES,
            'equipment':KINDS,'harvester':'single_row_left_to_right_wrapping_belt',
            'native_water':native,'native_soil':{'bank':'mole_fx','build':'mole_move_fx','animation':'move'},
            'sha256':digest,'dst_client_verified':False,'multiplayer_verified':False}
    report['atlas_sizes']={}
    for package in ['aom_attachment_shared','aom_attachment_fx']:
        with Image.open(STAGE/(package+'.png')) as im:report['atlas_sizes'][package]=list(im.size)
    (MOD/'Attachment-Build-Report.json').write_text(json.dumps(report,indent=2)+'\n')
    (RIG/'build.json').write_text(json.dumps(report,indent=2)+'\n')
    sync_reports(digest)
    return digest


if __name__=='__main__':print(json.dumps(build(),indent=2))
