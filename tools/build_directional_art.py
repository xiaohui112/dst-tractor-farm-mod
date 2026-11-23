#!/usr/bin/env python3
"""Compile generated five-view sprites into BILD v6 / ANIM v4 / KTEX assets.

ImageMagick performs deterministic sprite slicing/packing. No game compiler or
runtime file download is needed. Original imagegen sheets remain untouched.
"""
import copy
import hashlib
import gzip
import io
import json
import math
import os
from pathlib import Path
import struct
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image
from driver_animation import Reader, parse_anim, write_anim, name_hash, read_game_zip

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'assets/directional-v2'
STAGE=ROOT/'outputs/directional-build'
MOD=ROOT/'mod/Tractor'
VIEWS=[('downside',192),('side',5),('upside',48),('down',8),('up',2)]
KINDS=['plow','seeder','irrigator','fertilizer','weeder','harvester']
KTECH=Path.home()/'.local/bin/ktech'


def run(args):
    subprocess.run([str(v) for v in args],check=True,capture_output=True)


def prepare():
    STAGE.mkdir(parents=True,exist_ok=True)
    sprites={};layout={}
    for kind in ['tractor']+KINDS:
        path=SOURCE/(kind+'-five-views.png')
        # Read alpha only to find robust gutters; never alter generated pixels.
        with Image.open(path) as im:
            alpha=im.getchannel('A');w,h=im.size
            mass=[sum(v>128 for v in alpha.crop((x,0,x+1,h)).getdata()) for x in range(w)]
            bounds=[0]
            for i in range(1,5):
                target=i*w/5
                bounds.append(min(range(int(target-60),int(target+60)),
                    key=lambda x:(sum(mass[max(0,x-2):x+3]),abs(x-target))))
            bounds.append(w)
            boxes=[]
            for lo,hi in zip(bounds,bounds[1:]):
                box=alpha.crop((lo,0,hi,h)).point(lambda n:255 if n>128 else 0).getbbox()
                if box is None:raise ValueError('Empty directional view: '+kind)
                boxes.append((max(lo,lo+box[0]-2),max(0,box[1]-2),
                              min(hi,lo+box[2]+2),min(h,box[3]+2)))
        maxw=max(b[2]-b[0] for b in boxes);maxh=max(b[3]-b[1] for b in boxes)
        scale=min(260/maxw,300/maxh) if kind=='tractor' else min((220 if kind=='harvester' else 180)/maxw,165/maxh)
        sprites[kind]=[]
        for (view,_),box in zip(VIEWS,boxes):
            out=SOURCE/'sprites'/kind/(view+'.png');out.parent.mkdir(parents=True,exist_ok=True)
            x,y,x2,y2=box
            run(['magick',path,'-crop',f'{x2-x}x{y2-y}+{x}+{y}','+repage',
                 '-resize',f'{scale*100:.8f}%', 'PNG32:'+str(out)])
            sprites[kind].append(out)
        layout[kind]={'bounds':bounds,'boxes':boxes,'scale':scale,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    empty=SOURCE/'sprites/empty.png';run(['magick','-size','1x1','xc:none','PNG32:'+str(empty)])
    sprites['empty']=[empty]
    (SOURCE/'source-layout.json').write_text(json.dumps(layout,indent=2)+'\n')
    return sprites


def string(value):
    data=value.encode();return struct.pack('<I',len(data))+data


def compile_build(name,symbols,compact=False):
    entries=[]
    for symbol,paths in sorted(symbols.items(),key=lambda x:name_hash(x[0])):
        for index,path in enumerate(paths):
            with Image.open(path) as image:w,h=image.size
            entries.append((symbol,index,path,w,h))
    cellw,cellh=320,320;cols=6
    width=2048;height=1
    if compact:
        # Equipment rigs contain many small layers. Shelf packing avoids a huge
        # mostly transparent texture (and exceeding older GPUs' texture limits).
        placed={};x,y,rowh=4,4,0
        for i in sorted(range(len(entries)),key=lambda i:(-entries[i][4],-entries[i][3],i)):
            w,h=entries[i][3:]
            if x+w+4>width:x=4;y+=rowh+8;rowh=0
            placed[i]=(x,y,w,h);x+=w+8;rowh=max(rowh,h)
        used_height=y+rowh+4
    else:
        placed={i:((i%cols)*cellw+4,(i//cols)*cellh+4,w,h)
                for i,(_,_,_,w,h) in enumerate(entries)}
        used_height=math.ceil(len(entries)/cols)*cellh
    while height<used_height:height*=2
    png=STAGE/(name+'.png');tex=STAGE/(name+'.tex')
    command=['magick','-size',f'{width}x{height}','xc:none']
    rects=[]
    for i,(_,_,path,w,h) in enumerate(entries):
        x,y,_,_=placed[i]
        rects.append((x,y,w,h));command += [path,'-geometry',f'+{x}+{y}','-composite']
    run(command+['PNG32:'+str(png)])
    run([KTECH,png,tex])
    build=[b'BILD'+struct.pack('<3I',6,len(symbols),len(entries)),string(name),struct.pack('<I',1),string('atlas-0.tex')]
    vertices=[]
    for symbol,paths in sorted(symbols.items(),key=lambda x:name_hash(x[0])):
        build.append(struct.pack('<2I',name_hash(symbol),len(paths)))
        for index,_ in enumerate(paths):
            i=next(i for i,e in enumerate(entries) if e[0]==symbol and e[1]==index)
            x,y,w,h=rects[i];first=len(vertices)
            # ANIM / BILD use screen Y down; ground is y=0. KTEX UV is Y up.
            for px,py,u,v in [(0,0,0,0),(w,0,1,0),(w,h,1,1),(0,0,0,0),(w,h,1,1),(0,h,0,1)]:
                vertices.append((px-w/2,py-h,0.,(x+u*w)/width,1-(y+v*h)/height,0.))
            build.append(struct.pack('<2I4f2I',index,1,0.,-h/2,w,h,first,6))
    build.append(struct.pack('<I',len(vertices)))
    build += [struct.pack('<6f',*v) for v in vertices]
    build.append(struct.pack('<I',len(symbols)))
    for symbol in sorted(symbols,key=name_hash):build.extend([struct.pack('<I',name_hash(symbol)),string(symbol)])
    return b''.join(build),tex.read_bytes()


def element(symbol,index=0,x=0,y=0,scale=1,z=0):
    return {'symbol':name_hash(symbol),'frame':index,'layer':name_hash(symbol),
            'matrix':[scale,0.,0.,scale,float(x),float(y)],'z':float(z)}


def frame(elements):return {'bbox':(0.,-150.,850.,700.),'events':[],'elements':sorted(elements,key=lambda e:e['z'])}


def bank(name,animations,symbols):
    strings={name_hash(s):s for s in [name]+list(symbols)}
    return {'animations':animations,'strings':strings}


def animation(bankname,name,mask,frames):
    return {'name':name,'bank':name_hash(bankname),'facing':mask,'rate':30.,'frames':frames}


def save(name,build,anim,texture):
    target=MOD/'anim'/(name+'.zip')
    with ZipFile(target,'w',ZIP_DEFLATED) as z:
        if not name.startswith('aom_tractor_driver'):
            z.writestr('build.bin',build);z.writestr('atlas-0.tex',texture)
        z.writestr('anim.bin',write_anim(anim))
    return hashlib.sha256(target.read_bytes()).hexdigest()


def wheel_layers(sprites):
    # Vector rig: rotating brass spokes and bolt marks sit over the generated rims.
    # Centers and radii measured on the visible wheel hubs in the cropped sprites.
    wheels=[[(43.5/248,211/288,8/248,21/288),(131/248,237.5/288,10/248,16/288)],
            [(59.5/260,197/268,26/260,27/268),(193/260,219.5/268,19/260,19/268)],
            [(156.5/239,215/282,8/239,22/282),(215/239,221/282,6/239,15/282)],
            [(.18,.84,.055,.10),(.82,.84,.055,.10)],
            [(.24,.80,.075,.13),(.76,.80,.075,.13)]]
    result=[]
    for vi,path in enumerate(sprites['tractor']):
        with Image.open(path) as im:w,h=im.size
        for phase in range(12):
            shapes=[]
            for cx,cy,rx,ry in wheels[vi]:
                cx*=w;cy*=h;rx*=w;ry*=h
                for n in range(5):
                    angle=(n/5+phase/12)*2*math.pi
                    x=cx+rx*.78*math.cos(angle);y=cy+ry*.78*math.sin(angle)
                    shapes.append(f'<path d="M{cx:.3f} {cy:.3f} L{x:.3f} {y:.3f}" stroke="#786144" stroke-width="1.5"/>')
                    shapes.append(f'<ellipse cx="{x:.3f}" cy="{y:.3f}" rx="1.6" ry="2" fill="#cfb685" stroke="#423c32" stroke-width=".8"/>')
            svg=SOURCE/'rig'/f'wheel-{vi}-{phase}.svg';svg.parent.mkdir(exist_ok=True)
            svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'+''.join(shapes)+'</svg>')
            out=svg.with_suffix('.png');run(['magick','-background','none',svg,'PNG32:'+str(out)])
            result.append(out)
    return result


def vehicle_layers(index,mask,phase=None,cabin=False):
    view=VIEWS[index][0]
    rear={'side':(-115,-12),'downside':(-90,-28),'upside':(-35,-10),'down':(0,-70),'up':(0,20)}[view]
    # 独立配件不使用空前挂点；此符号供排气位置读取。
    from mount_geometry import exhaust
    front=exhaust(index)
    moving=phase is not None
    bob=math.sin(phase/12*4*math.pi)*1.6 if moving else 0
    jiggle=math.sin(phase/12*6*math.pi)*2 if moving else 0
    body='aom_cabin_front' if cabin else 'body'
    tail='aom_driver_attachment_rear' if cabin else 'attachment'
    nose='aom_driver_attachment_front' if cabin else 'attachment_front'
    # Rear view has the rear implement nearest the camera; front view the front header.
    rz=-.3 if mask in (48,2) else 1.2
    fz=1.2 if mask in (48,2) else -.3
    es=[element(body,index,y=bob),element(tail,index,*rear,y_scale(index),rz),
        element(nose,index,*front,y_scale(index),fz)]
    es[1]['matrix'][5]+=jiggle;es[2]['matrix'][5]+=bob
    if cabin:es.append(element('aom_cabin_back',0,z=1))
    if moving and mask not in (8,2):
        es.append(element('aom_wheels',index*12+phase,y=bob,z=-.1))
    return es


def y_scale(index):return 1.


def build_chassis(sprites,wheels):
    # Use the supplied wreck image at normal vehicle width; packed art alone is half size.
    source=ROOT/'assets/images/source-art/death.png'
    wreck=SOURCE/'sprites/tractor/death.png'
    with Image.open(source) as im:
        box=im.getchannel('A').point(lambda n:255 if n>128 else 0).getbbox()
    x,y,x2,y2=box
    run(['magick',source,'-crop',f'{x2-x}x{y2-y}+{x}+{y}','+repage',
         '-resize','260x288','PNG32:'+str(wreck)])
    symbols={'body':sprites['tractor'],'wreck':[wreck],
             'attachment':sprites['empty']*5,'attachment_front':sprites['empty']*5,'aom_wheels':wheels}
    b,t=compile_build('aom_tractor_chassis',symbols);an=[]
    for index,(_,mask) in enumerate(VIEWS):
        for name in ['idle','work','run_loop','idle_packed','death']:
            moving=name in ('run_loop','work')
            fs=[frame(vehicle_layers(index,mask,p if moving else None)) for p in range(12 if moving else 1)]
            if name=='idle_packed':fs=[frame([element('body',index,scale=.5)])]
            elif name=='death':fs=[frame([element('wreck')])]
            an.append(animation('aom_tractor_chassis',name,mask,fs))
    return save('aom_tractor_chassis',b,bank('aom_tractor_chassis',an,symbols),t)


def stable_driver(name):
    return name.startswith(('run_','walk_','sprint_','idle_','dial_','dialog_','sand_idle')) or name=='alert_idle'


def seated_driver(by_key,anim,frame_index,owned,anchor,scale,side_pose):
    """按人物姿势选方向，不能把原版idle的207宽掩码当作侧面/背面姿势。"""
    mask=anim['facing']
    source_mask={2:48,8:192}.get(mask,mask)
    stable=stable_driver(anim['name'])
    # 骑牛idle和run的侧面都是正脸。使用真正的原版侧向idle，身体下部由车身遮住。
    pose_name='idle_loop' if stable else anim['name']
    source=by_key.get((pose_name,source_mask),anim)
    pose=source['frames'][0 if stable else frame_index%len(source['frames'])]
    if stable and source_mask==5:pose=side_pose
    reference=pose if stable else by_key['idle_loop',source_mask]['frames'][0]
    head=next(e for e in reference['elements'] if e['symbol']==name_hash('headbase'))
    matrix=head['matrix'];hx,hy=matrix[4:6]
    # 统一变换整个姿势，人物/皮肤/帽子保持相对关系；左右镜像仍由引擎处理。
    angle=math.atan2(matrix[1],matrix[0]) if matrix[0]>=0 else math.atan2(-matrix[1],-matrix[0])
    angle=-angle if stable else 0
    ratio=scale/math.hypot(matrix[0],matrix[1]) if stable else scale/.24
    c,s=math.cos(angle)*ratio,math.sin(angle)*ratio
    driver=copy.deepcopy([e for e in pose['elements'] if e['symbol'] not in owned])
    driver.sort(key=lambda e:e['z'],reverse=True)
    for i,e in enumerate(driver):e['z']=.6-.2*i/max(1,len(driver)-1)
    for e in driver:
        a,b,x,y,tx,ty=e['matrix'];tx-=hx;ty-=hy
        e['matrix']=[c*a-s*b,s*a+c*b,c*x-s*y,s*x+c*y,
                     c*tx-s*ty+anchor[0],s*tx+c*ty+anchor[1]]
    return driver


def main():
    sprites=prepare();wheels=wheel_layers(sprites)
    digest={}
    symbols={k:sprites[k] for k in KINDS};symbols['empty']=sprites['empty']*5
    for name in ['aom_attachment_symbols']:
        b,t=compile_build(name,symbols);an=[]
        for kind in symbols:
            for index,(_,mask) in enumerate(VIEWS):an.append(animation(name,kind,mask,[frame([element(kind,index)])]))
        digest[name]=save(name,b,bank(name,an,symbols),t)
    from build_attachment_animations import build as build_attachments
    digest.update(build_attachments(sprites))
    digest['aom_tractor_chassis']=build_chassis(sprites,wheels)
    symbols={'aom_cabin_front':sprites['tractor'],'aom_cabin_back':sprites['empty'],
             'aom_driver_attachment_rear':sprites['empty']*5,'aom_driver_attachment_front':sprites['empty']*5,'aom_wheels':wheels}
    b,t=compile_build('aom_tractor_cabin',symbols);an=[]
    for index,(_,mask) in enumerate(VIEWS):
        for name in ['idle','run_loop']:
            fs=[frame(vehicle_layers(index,mask,p if name=='run_loop' else None,True)) for p in range(12 if name=='run_loop' else 1)]
            an.append(animation('aom_tractor_cabin',name,mask,fs))
    cabin=bank('aom_tractor_cabin',an,symbols)
    digest['aom_tractor_cabin']=save('aom_tractor_cabin',b,cabin,t)
    # Runtime scales the complete AnimState with the vehicle. Inverse character
    # scaling keeps characters and equipped symbols at their native world size.
    config={'driver_scale':1/2.5,'driver_world_scale':1,
            'vehicle_scales':{'aom_tractor_driver':2.5,'aom_tractor_driver_075':1.875,
                              'aom_tractor_driver_125':3.125,'aom_tractor_driver_150':3.75},
            'views':{v:{'neck':[-35 if v=='side' else -25 if v=='downside' else 0,-174]} for v,_ in VIEWS}}
    (SOURCE/'seat-layout.json').write_text(json.dumps(config,indent=2)+'\n')
    # 只保留构建所需的原始人物时间线，不依赖已清理的整套Windows交付ZIP。
    source=ROOT/'assets/driver/build/windows-2026-11-11/native-riding-source.anim.bin.gz'
    old=parse_anim(gzip.decompress(source.read_bytes()))
    owned={name_hash(s) for s in ['aom_cabin_front','aom_cabin_back','aom_driver_attachment_rear','aom_driver_attachment_front']}
    output=copy.deepcopy(old);output['strings'].update(cabin['strings'])
    # Vanilla running only supplies six-facing poses. Straight front/back use
    # their native seated idle character pose plus the new vehicle's run rig,
    # retaining each run action's frame count, rate and frame events.
    by_key={(a['name'],a['facing']):a for a in old['animations']}
    game=Path(os.environ.get('DST_GAME',str(Path.home()/
        "Library/Application Support/Steam/steamapps/common/Don't Starve Together/dontstarve_steam.app/Contents")))
    with read_game_zip(str(game),'player_idles.zip') as archive:
        idle=parse_anim(archive.read('anim.bin'))
    side_pose=next(a['frames'][0] for a in idle['animations'] if a['name']=='idle_loop' and a['facing']==5)
    for e in side_pose['elements']:
        output['strings'][e['symbol']]=idle['strings'][e['symbol']]
    moving_names={a['name'] for a in old['animations'] if a['name'].startswith(('run_','walk_','sprint_'))}
    for name in sorted(moving_names):
        for mask,source_mask in [(2,48),(8,192)]:
            if (name,mask) in by_key or (name,source_mask) not in by_key:continue
            extra=copy.deepcopy(by_key[name,source_mask]);extra['facing']=mask
            seat=by_key['idle_loop',mask]['frames']
            for fi,f in enumerate(extra['frames']):
                f['elements']=copy.deepcopy(seat[fi%len(seat)]['elements'])
            output['animations'].append(extra)
    for a in output['animations']:
        mask=a['facing'];index=next(i for i,(_,m) in enumerate(VIEWS) if m==mask)
        view=VIEWS[index][0];after=config['views'][view]['neck']
        motion=a['name'].startswith(('run_','walk_','sprint_'))
        for fi,f in enumerate(a['frames']):
            phase=int(fi*30/a['rate'])%12 if motion else None
            vehicle=vehicle_layers(index,mask,phase,True)
            shell=next(e for e in vehicle if e['symbol']==name_hash('aom_cabin_front'))
            # Stable seated pose: remove beefalo gait/leaning from every body part.
            # Only the vehicle's suspension translation moves the entire driver.
            stable=stable_driver(a['name'])
            driver=seated_driver(by_key,a,fi,owned,after,config['driver_scale'],side_pose)
            for e in driver:
                if stable:
                    e['matrix'][4]+=shell['matrix'][4];e['matrix'][5]+=shell['matrix'][5]
            f['elements']=sorted(vehicle+driver,key=lambda e:e['z'])
            f['bbox']=(0.,-150.,850.,700.)
    digest['aom_tractor_driver']=save('aom_tractor_driver',b,output,t)
    # Only the selected archive is loaded at runtime. Vehicle matrices remain
    # identical across size options; compensate every character/skin/hat matrix.
    previous_scale=2.5
    vehicle_symbols=owned|{name_hash('aom_wheels')}
    for bankname,world_scale in config['vehicle_scales'].items():
        if bankname=='aom_tractor_driver':continue
        ratio=previous_scale/world_scale
        output['strings'][name_hash(bankname)]=bankname
        for a in output['animations']:
            a['bank']=name_hash(bankname)
            view=next(v for v,mask in VIEWS if mask==a['facing'])
            anchor=config['views'][view]['neck']
            stable=stable_driver(a['name'])
            for f in a['frames']:
                shell=next(e for e in f['elements'] if e['symbol']==name_hash('aom_cabin_front'))
                x=anchor[0]+(shell['matrix'][4] if stable else 0)
                y=anchor[1]+(shell['matrix'][5] if stable else 0)
                for e in f['elements']:
                    if e['symbol'] in vehicle_symbols:continue
                    m=e['matrix']
                    e['matrix']=[m[0]*ratio,m[1]*ratio,m[2]*ratio,m[3]*ratio,
                                 (m[4]-x)*ratio+x,(m[5]-y)*ratio+y]
        digest[bankname]=save(bankname,b,output,t)
        previous_scale=world_scale
    report={'schema':2,'views':[v for v,_ in VIEWS],'facing_masks':[m for _,m in VIEWS],
            'native_source':'assets/driver/build/windows-2026-11-11/native-riding-source.anim.bin.gz','driver_scale':config['driver_scale'],
            'driver_animations':len(output['animations']),'driving_phases':12,
            'world_scale':2.5,'driver_world_scale':1,'vehicle_scales':config['vehicle_scales'],
            'driver_motion':'fixed_seated_pose_with_vehicle_suspension',
            'driver_facing':'directional_side_pose_and_rear_pose_with_upright_head',
            'side_pose_source':'player_idles.zip/idle_loop/5/frame0',
            'rear_attachments_front_view':'occluded_in_mounted_banks_only',
            'wreck_source':'assets/images/source-art/death.png',
            'sha256':digest,'game_validation':False}
    (SOURCE/'build.json').write_text(json.dumps(report,indent=2)+'\n')
    (MOD/'Driver-Build-Report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
