#!/usr/bin/env python3
"""编译矢量水滴及软管；只构建本次资源，不执行发布/安装。"""
from pathlib import Path
from build_directional_art import ROOT,MOD,KTECH,STAGE,run,compile_build,element,frame,animation,bank,save

def main():
    source=ROOT/'assets/ui';source.mkdir(parents=True,exist_ok=True);STAGE.mkdir(parents=True,exist_ok=True)
    drop=source/'water-drop.svg';hose=source/'refill-hose.svg'
    drop.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><path d="M32 5 C28 15 12 29 12 41 C12 64 53 64 53 41 C53 28 37 15 32 5Z" fill="#45a1b7" stroke="#332a20" stroke-width="4"/><path d="M27 28 Q18 42 25 49" fill="none" stroke="#b8d7c3" stroke-width="4" stroke-linecap="round"/></svg>')
    hose.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="16"><rect x="0" y="2" width="64" height="12" rx="5" fill="#28271f" stroke="#151713" stroke-width="2"/><path d="M3 5 L61 5" stroke="#69634d" stroke-width="2"/><path d="M4 2 V14 M59 2 V14" stroke="#ac8c56" stroke-width="3"/></svg>')
    for svg in (drop,hose):run(['magick','-background','none',svg,'PNG32:'+str(STAGE/(svg.stem+'.png'))])
    run([KTECH,STAGE/'water-drop.png',MOD/'images/aom_water.tex'])
    (MOD/'images/aom_water.xml').write_text('<Atlas><Texture filename="aom_water.tex"/><Elements><Element name="water_drop.tex" u1="0" u2="1" v1="0" v2="1"/></Elements></Atlas>\n')
    symbols={'hose':[STAGE/'refill-hose.png']};b,t=compile_build('aom_refill_hose',symbols,compact=True)
    data=bank('aom_refill_hose',[animation('aom_refill_hose','idle',255,[frame([element('hose',y=8)])])],symbols)
    save('aom_refill_hose',b,data,t)
    print('水滴图标和软管动画已编译')
if __name__=='__main__':main()
