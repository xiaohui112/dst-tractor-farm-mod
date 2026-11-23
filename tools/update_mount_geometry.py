#!/usr/bin/env python3
"""仅更新已编译动画的连接点/烟筒定位，不重绘贴图，不生成发布包。"""
import hashlib
import json
from zipfile import ZipFile
from driver_animation import name_hash,parse_anim,write_anim
from mount_geometry import ROOT,mounted_bank,exhaust_markers

MOD=ROOT/'mod/Tractor'


def update(path,transform):
    with ZipFile(path) as z:entries=[(i,z.read(i.filename)) for i in z.infolist()]
    temp=path.with_suffix('.tmp')
    try:
        with ZipFile(temp,'w') as z:
            for info,raw in entries:
                if info.filename=='anim.bin':raw=write_anim(transform(parse_anim(raw)))
                z.writestr(info,raw)
        temp.replace(path)
    finally:temp.unlink(missing_ok=True)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def equipment(data):
    for a in data['animations']:
        if a['bank']!=name_hash('aom_attachment_shared') or not a['name'].startswith('harvester') or a['facing']!=192:continue
        for frame in a['frames']:
            # 旧包只修过side；按基底矩阵符号判断，重复运行不二次镜像。
            if frame['elements'][0]['matrix'][0]<0:continue
            for e in frame['elements']:
                m=e['matrix'];m[0]=-m[0];m[2]=-m[2];m[4]=-m[4]
    return mounted_bank(data,'aom_attachment_shared','aom_attachment_mounted',lambda n:n.split('_work_')[0])


def main():
    hashes={}
    transforms={
        'aom_attachment_shared':equipment,
        'aom_attachment_water':lambda d:mounted_bank(d,'aom_attachment_water','aom_attachment_water_mounted',lambda n:'irrigator'),
        'aom_attachment_fx':lambda d:mounted_bank(d,'aom_attachment_fx','aom_attachment_fx_mounted',lambda n:'fertilizer' if n=='fertilizer' else None),
        'aom_tractor_chassis':lambda d:exhaust_markers(d,'attachment_front'),
        'aom_tractor_cabin':lambda d:exhaust_markers(d,'aom_driver_attachment_front'),
    }
    for name in ('aom_tractor_driver','aom_tractor_driver_075','aom_tractor_driver_125','aom_tractor_driver_150'):
        transforms[name]=lambda d:exhaust_markers(d,'aom_driver_attachment_front')
    for name,transform in transforms.items():hashes[name]=update(MOD/'anim'/(name+'.zip'),transform)
    for path in (MOD/'Attachment-Build-Report.json',MOD/'Driver-Build-Report.json',ROOT/'assets/directional-v2/build.json'):
        report=json.loads(path.read_text())
        keys=report.setdefault('sha256',{})
        keys.update({k:v for k,v in hashes.items() if k in keys})
        report['mount_geometry']='assets/directional-v2/mount-layout.json'
        path.write_text(json.dumps(report,indent=2)+'\n')
    print(f'已更新{len(hashes)}个动画文件的挂载/烟筒几何；贴图与发布安装包未改动。')


if __name__=='__main__':main()
