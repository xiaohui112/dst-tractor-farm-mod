#!/usr/bin/env python3
"""将 KeshS 四季图表中的 OR 分支展开，并生成经空间约束验证的固定布局。

引用：https://kleiforums.com/forums/topic/126274-giant-crop-cheat-sheet/
生成结果不是原图逐像素复刻；保留株数，逐地皮校验养分、逐株校验家族。
图中本身养分不平衡的条目保留 reference_only，禁止自动播种。
"""
from pathlib import Path
from itertools import product
from collections import Counter
import hashlib
import json
import math
import random
from giant_layout_variants import enhance_catalog

ROOT = Path(__file__).resolve().parents[1]
# nutrient_consumption 的三个通道，顺序与游戏原始数组一致。
CONSUME = dict(carrot=(4,0,0), corn=(0,4,0), potato=(0,0,4), tomato=(2,2,0),
    asparagus=(0,4,0), eggplant=(0,0,4), pumpkin=(4,0,0), watermelon=(0,2,2),
    dragonfruit=(0,0,8), durian=(0,8,0), garlic=(0,8,0), onion=(8,0,0),
    pepper=(0,0,8), pomegranate=(8,0,0))
PATTERNS = []
def panel(season, number, *groups, not_giant=()):
    PATTERNS.append((season, number, groups, not_giant))
def g(n, *crops): return n, crops

panel('autumn',1,g(4,'tomato'),g(4,'eggplant','potato'))
panel('autumn',2,g(4,'onion'),g(4,'garlic'),g(4,'pepper'))
panel('autumn',3,g(4,'pepper'),g(8,'corn'),g(8,'carrot','pumpkin'))
panel('autumn',4,g(4,'corn'),g(4,'carrot','pumpkin'),g(4,'eggplant','potato'))
panel('autumn',5,g(4,'pepper'),g(8,'tomato'))
panel('autumn',6,g(4,'garlic'),g(8,'carrot'),g(8,'eggplant','potato'))
panel('autumn',7,g(4,'garlic'),g(4,'pepper'),g(8,'carrot','pumpkin'))
panel('autumn',8,g(4,'onion'),g(4,'pepper'),g(8,'corn'))
panel('autumn',9,g(4,'garlic'),g(4,'onion'),g(8,'eggplant','potato'))
panel('autumn',10,g(16,'tomato'),g(16,'eggplant','potato'))
panel('autumn',11,g(4,'onion'),g(8,'corn'),g(8,'eggplant','potato'))

panel('winter',1,g(4,'asparagus'),g(4,'potato'),g(4,'carrot','pumpkin'))
# 原图确实标为芦笋4，不能偷偷换成大蒜：保留原文并标记无法免施肥。
panel('winter',2,g(4,'asparagus'),g(8,'potato'),g(8,'carrot','pumpkin'))

panel('spring',1,g(4,'carrot'),g(4,'watermelon'))
panel('spring',2,g(4,'tomato'),g(4,'eggplant','potato'))
panel('spring',3,g(4,'carrot'),g(4,'asparagus','corn'),g(4,'eggplant','potato'))
panel('spring',4,g(8,'watermelon'),g(8,'eggplant','potato'),g(8,'pomegranate','onion'),g(8,'asparagus','corn'))
panel('spring',5,g(4,'dragonfruit'),g(4,'durian','garlic'),g(4,'pomegranate','onion'))
panel('spring',6,g(4,'dragonfruit'),g(8,'tomato'))
panel('spring',7,g(8,'watermelon'),g(4,'pomegranate','onion'))
panel('spring',8,g(8,'dragonfruit'),g(16,'carrot'),g(8,'durian','garlic'))
panel('spring',9,g(4,'dragonfruit'),g(4,'pomegranate','onion'),g(8,'asparagus','corn'))
panel('spring',10,g(4,'dragonfruit'),g(8,'carrot'),g(4,'durian','garlic'))
panel('spring',11,g(4,'durian','garlic'),g(4,'pomegranate','onion'),g(8,'eggplant','potato'))
panel('spring',12,g(8,'durian','garlic'),g(8,'pomegranate','onion'),g(16,'eggplant','potato'))
panel('spring',13,g(8,'carrot'),g(8,'tomato'),g(8,'dragonfruit'),g(8,'asparagus','corn'))
panel('spring',14,g(16,'asparagus'),g(8,'dragonfruit'),g(8,'pomegranate','onion'))
# 同配比在原图出现第二种排布，生成器会复用经过校验的布局。
panel('spring',15,g(8,'durian','garlic'),g(8,'pomegranate','onion'),g(16,'eggplant','potato'))
panel('spring',16,g(4,'dragonfruit'),g(8,'carrot'),g(8,'asparagus','corn'))
panel('spring',17,g(4,'pomegranate','onion'),g(8,'eggplant','potato'),g(8,'asparagus','corn'))
panel('spring',18,g(4,'watermelon'),g(8,'carrot'),g(4,'asparagus','corn'),g(4,'eggplant','potato'))

panel('summer',1,g(4,'garlic'),g(4,'pomegranate','onion'),g(4,'dragonfruit','pepper'))
panel('summer',2,g(4,'pomegranate','onion'),g(8,'watermelon'))
panel('summer',3,g(8,'tomato'),g(4,'dragonfruit','pepper'))
panel('summer',4,g(8,'corn'),g(4,'pomegranate','onion'),g(4,'dragonfruit','pepper'))
panel('summer',5,g(8,'tomato'),g(8,'corn'),g(8,'watermelon'),g(8,'dragonfruit'),g(8,'pomegranate','onion'),not_giant=('tomato',))

# 大于原版1.25的邻坑破坏半径，跨地块也必须检查。
TILL_SPACING = 1.25
GRID = [(x*4/3,z*4/3) for z in (-1,0,1) for x in (-1,0,1)]
HEX = [(x*1.28,z*1.28) for x,z in
       [(-1,-1),(0,-1),(1,-1),(-1.5,0),(-.5,0),(.5,0),(1.5,0),(-1,1),(0,1),(1,1)]]
def delta(crop):
    consume = CONSUME[crop]
    restore = sum(consume) // consume.count(0)
    return [-n if n else restore for n in consume]
def net(ratio):return [sum(n*delta(c)[i] for c,n in ratio.items()) for i in range(3)]

def solve(ratio, not_giant):
    """每格保持同一正确比例；随机交换只离线生成，运行时不做搜索。"""
    total=sum(ratio.values())
    common=math.gcd(*ratio.values())
    signature=json.dumps([ratio,not_giant],sort_keys=True)
    rng=random.Random(int(hashlib.sha256(signature.encode()).hexdigest()[:16],16))
    for tiles in (1,2,4,8,16):
        if common%tiles or total//tiles>10:continue
        per={c:n//tiles for c,n in ratio.items()}
        # 两格十株布局纵向相邻，避免四列的横向边缘互相毁坑。
        for shape,offsets in [('grid',GRID),('hex',HEX)]:
            if sum(per.values())>len(offsets):continue
            width=1 if tiles==1 or (tiles==2 and shape=='hex') else 2
            height=tiles//width
            points=[(tx*4+x,tz*4+z,tx,tz,x,z) for tz in range(height) for tx in range(width) for x,z in offsets]
            neighbors=[[j for j,b in enumerate(points) if (a[0]-b[0])**2+(a[1]-b[1])**2<=16+1e-8] for a in points]
            conflicts=[(i,j) for i,a in enumerate(points) for j,b in enumerate(points[:i])
                       if (a[0]-b[0])**2+(a[1]-b[1])**2<=TILL_SPACING**2+1e-8]
            crops=['']+sorted(per)
            exempt={crops.index(c) for c in not_giant}
            base=[crops.index(c) for c,n in sorted(per.items()) for _ in range(n)]+[0]*(len(offsets)-sum(per.values()))
            # 整数邻居计数，交换时只更新受影响的邻居；保持生成结果确定性。
            for restart in range(16):
                colors=[]
                for _ in range(tiles):
                    row=base[:];rng.shuffle(row);colors+=row
                counts=[[0]*len(crops) for _ in points]
                for i,near in enumerate(neighbors):
                    for j in near:counts[i][colors[j]]+=1
                def deficit(i):
                    c=colors[i]
                    return max(0,4-counts[i][c])**2 if c and c not in exempt else 0
                def conflict_cost():return sum(40 for i,j in conflicts if colors[i] and colors[j])
                score=sum(deficit(i) for i in range(len(points)))+conflict_cost()
                for step in range(24000):
                    if score==0:
                        return [{'tx':p[2],'tz':p[3],'x':p[4],'z':p[5],'crop':crops[c] or False} for p,c in zip(points,colors)],shape,width,height
                    tile=rng.randrange(tiles);i=tile*len(offsets)+rng.randrange(len(offsets));j=tile*len(offsets)+rng.randrange(len(offsets))
                    a,b=colors[i],colors[j]
                    if a==b:continue
                    affected=set(neighbors[i])|set(neighbors[j])
                    before=sum(deficit(k) for k in affected)+conflict_cost()
                    for k in neighbors[i]:counts[k][a]-=1;counts[k][b]+=1
                    for k in neighbors[j]:counts[k][b]-=1;counts[k][a]+=1
                    colors[i],colors[j]=b,a
                    nxt=score-before+sum(deficit(k) for k in affected)+conflict_cost()
                    temperature=max(.08,1.8*(1-step/24000))
                    if nxt<=score or rng.random()<math.exp((score-nxt)/temperature):score=nxt
                    else:
                        colors[i],colors[j]=a,b
                        for k in neighbors[i]:counts[k][b]-=1;counts[k][a]+=1
                        for k in neighbors[j]:counts[k][a]-=1;counts[k][b]+=1
    return None

def lua(value):
    if value is None:return 'nil'
    if value is True:return 'true'
    if value is False:return 'false'
    if isinstance(value,str):return json.dumps(value,ensure_ascii=False)
    if isinstance(value,(int,float)):return str(value)
    if isinstance(value,list):return '{'+','.join(lua(v) for v in value)+'}'
    return '{'+','.join('['+lua(k)+']='+lua(v) for k,v in sorted(value.items()))+'}'

def main():
    data={s:[] for s in ('autumn','winter','spring','summer')};cache={}
    for season,number,groups,exceptions in PATTERNS:
        for variant,crops in enumerate(product(*(options for n,options in groups)),1):
            ratio=dict(zip(crops,[n for n,options in groups]))
            entry={'id':f'{season}-{number:02d}-{variant:02d}','panel':number,'ratio':ratio,'not_giant':list(exceptions),'net':net(ratio)}
            key=json.dumps([ratio,exceptions],sort_keys=True)
            if any(entry['net']):entry['reference_only']='NUTRIENT_IMBALANCE'
            else:
                if key not in cache:cache[key]=solve(ratio,exceptions)
                found=cache[key]
                if found:
                    entry['slots'],entry['shape'],entry['width'],entry['height']=found
                    entry['self_sustaining']=True
                else:entry['reference_only']='NO_VALID_LAYOUT'
            data[season].append(entry)
            print(entry['id'],entry.get('reference_only',entry.get('shape')),flush=True)
    enhance_catalog(data, CONSUME)
    out=ROOT/'mod/Tractor/scripts/aom_giant_layouts.lua'
    out.write_text('-- 由 tools/generate_giant_layouts.py 生成；OR 已展开，false 为留空坑。\n-- 来源：https://kleiforums.com/forums/topic/126274-giant-crop-cheat-sheet/\nreturn '+lua(data)+'\n')
    print({s:{'catalog':len(v),'automatic':sum('slots'in e for e in v)} for s,v in data.items()})

if __name__=='__main__':main()
