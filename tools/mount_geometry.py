"""五视图连接点；挂载动画与独立落地动画共用原始贴图。"""
import copy
import json
from pathlib import Path
from PIL import Image
from driver_animation import name_hash

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'assets/directional-v2'
LAYOUT=json.loads((SOURCE/'mount-layout.json').read_text())
MASKS=[192,5,48,8,2]


def point(kind,index,uv):
    with Image.open(SOURCE/'sprites'/kind/(LAYOUT['views'][index]+'.png')) as im:
        w,h=im.size
    return (uv[0]-.5)*w,(uv[1]-1)*h


def exhaust(index):
    return point('tractor',index,LAYOUT['tractor']['exhaust'][index])


def offset(kind,index):
    target=point('tractor',index,LAYOUT['tractor']['front' if kind=='harvester' else 'rear'][index])
    hook=point(kind,index,LAYOUT['hitches'][kind][index])
    if kind=='harvester' and index in (0,1):hook=(-hook[0],hook[1])
    return target[0]-hook[0],target[1]-hook[1]


def mounted_bank(data,base,mounted,kind_for_animation):
    """只变换挂载bank；原地设备的动画/贴图和工作时间线保持独立。"""
    data['animations']=[a for a in data['animations'] if a['bank']!=name_hash(mounted)]
    result=[]
    for a in data['animations']:
        if a['bank']!=name_hash(base):continue
        kind=kind_for_animation(a['name'])
        if kind not in LAYOUT['hitches']:continue
        item=copy.deepcopy(a);item['bank']=name_hash(mounted)
        dx,dy=offset(kind,MASKS.index(a['facing']))
        for frame in item['frames']:
            for e in frame['elements']:
                e['matrix'][4]+=dx;e['matrix'][5]+=dy
        result.append(item)
    data['animations'].extend(result);data['strings'][name_hash(mounted)]=mounted
    return data


def exhaust_markers(data,marker):
    for a in data['animations']:
        if a['facing'] not in MASKS:continue
        x,y=exhaust(MASKS.index(a['facing']))
        for frame in a['frames']:
            body=next((e for e in frame['elements'] if e['symbol'] in
                       (name_hash('body'),name_hash('aom_cabin_front'))),None)
            if not body:continue
            for e in frame['elements']:
                if e['symbol']==name_hash(marker):
                    e['matrix'][4]=x+body['matrix'][4];e['matrix'][5]=y+body['matrix'][5]
    return data
