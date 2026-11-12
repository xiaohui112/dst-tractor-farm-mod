#!/usr/bin/env python3
"""把生成的三视图整理为可编译 SCML；SVG 定义座椅、锚点及层次。"""
from pathlib import Path
import json
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/driver/aom_tractor_cabin'
VIEWS=[('downside',0,[(145,425),(189,422),(194,507),(130,511)],(-45,-150)),
       ('side',1,[(136,430),(213,426),(211,519),(126,519)],(-43,-150)),
       ('upside',2,[(145,434),(214,435),(217,526),(138,526)],(-38,-147))]


def main():
    for part in ('aom_cabin_back','aom_cabin_front','aom_driver_attachment_rear','aom_driver_attachment_front'):
        (OUT/part).mkdir(parents=True,exist_ok=True)
    sheet=ROOT/'assets/driver/tractor-views.png'
    for _,index,points,_ in VIEWS:
        subprocess.run(['magick',str(sheet),'-crop','512x1024+%d+0'%(index*512),'+repage',
                        str(OUT/'aom_cabin_front'/('front-%d.png'%index))],check=True)
        coords=' '.join('%d,%d'%p for p in points)
        svg='<svg xmlns="http://www.w3.org/2000/svg" width="512" height="1024"><polygon points="%s" fill="#272821"/><path d="M145 510 Q170 475 196 510 L200 530 L140 530 Z" fill="#3e382f"/></svg>'%coords
        path=OUT/'aom_cabin_back'/('back-%d.svg'%index);path.write_text(svg)
        subprocess.run(['magick','-background','none',str(path),str(path.with_suffix('.png'))],check=True)
    for part in ('aom_driver_attachment_rear','aom_driver_attachment_front'):
        # PNG32 forces an 8-bit RGBA file; plain PNG output can collapse the fully
        # transparent placeholder to 1-bit grey and drop alpha, which makes the
        # Mod Tools atlasing step fail with "'int' object is not subscriptable".
        subprocess.run(['magick','-size','256x256','xc:none',
                        'PNG32:'+str(OUT/part/'empty.png')],check=True)
    root=ET.Element('spriter_data',{'scml_version':'1.0','generator':'Tractor Driver Export','generator_version':'1'})
    parts=['aom_cabin_back','aom_cabin_front','aom_driver_attachment_rear','aom_driver_attachment_front']
    for folder_id,part in enumerate(parts):
        folder=ET.SubElement(root,'folder',id=str(folder_id),name=part)
        count=3 if folder_id<2 else 1
        for i in range(count):
            name=('back-%d.png'%i if folder_id==0 else 'front-%d.png'%i) if folder_id<2 else 'empty.png'
            ET.SubElement(folder,'file',id=str(i),name=part+'/'+name,width='512' if folder_id<2 else '256',height='1024' if folder_id<2 else '256',pivot_x='0.5',pivot_y='0.21875' if folder_id<2 else '0')
    entity=ET.SubElement(root,'entity',id='0',name='aom_tractor_cabin')
    for number,(view,index,_,_) in enumerate(VIEWS):
        anim=ET.SubElement(entity,'animation',id=str(number),name='idle_'+view,length='100',looping='true')
        main=ET.SubElement(ET.SubElement(anim,'mainline'),'key',id='0',time='0')
        # rear attachment -> cabin interior -> rider (inserted by composer) -> shell -> front attachment
        for i,(part,z) in enumerate(zip(parts,[1,3,0,4])):
            ET.SubElement(main,'object_ref',id=str(i),timeline=str(i),key='0',z_index=str(z))
            timeline=ET.SubElement(anim,'timeline',id=str(i),name=part,object_type='sprite')
            key=ET.SubElement(timeline,'key',id='0',time='0',spin='0',curve_type='instant')
            rear=(-125,25) if view!='upside' else (-70,15)
            front=(130,8) if view!='upside' else (85,45)
            xy=(0,0) if i<2 else (rear if i==2 else front)
            ET.SubElement(key,'object',folder=str(i),file=str(index if i<2 else 0),x=str(xy[0]),y=str(xy[1]),angle='0',scale_x='0.5' if i<2 else '0.7',scale_y='0.5' if i<2 else '0.7',a='1')
    ET.indent(root)
    ET.ElementTree(root).write(OUT/'aom_tractor_cabin.scml',encoding='utf-8',xml_declaration=True)
    config={'driver_scale':0.24,'views':{view:{'neck':list(neck)} for view,_,_,neck in VIEWS}}
    (ROOT/'assets/driver/seat-layout.json').write_text(json.dumps(config,indent=2)+'\n')
    print('驾驶室三视图、前后遮挡层、SCML 与座位锚点已生成。')

if __name__=='__main__':main()
