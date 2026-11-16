import sys
from pathlib import Path
from zipfile import ZipFile
from PIL import Image
from xml.sax.saxutils import escape
sys.path.insert(0,str(Path.cwd()/'tools'))
from driver_animation import Reader,name_hash,parse_anim,read_game_zip
from build_directional_art import run,KTECH,SOURCE
OUT=Path.cwd()/'outputs/visual-alignment-fix'
GAME=str(Path.home()/"Library/Application Support/Steam/steamapps/common/Don't Starve Together/dontstarve_steam.app/Contents")

def unpack(z,tag):
 r=Reader(z.read('build.bin'));r.read(8);count,_=r.unpack('2I');r.string()
 names=[r.string() for _ in range(r.unpack('I')[0])]
 records={}
 for _ in range(count):
  key,n=r.unpack('2I');records[key]=[r.unpack('2I4f2I') for _ in range(n)]
 vs=[r.unpack('6f') for _ in range(r.unpack('I')[0])]
 atlases=[]
 for i,n in enumerate(names):
  tex=OUT/f'{tag}-{i}.tex';tex.write_bytes(z.read(n));png=tex.with_suffix('.png');run([KTECH,tex,png]);atlases.append(Image.open(png).convert('RGBA'))
 lookup={}
 for key,frames in records.items():
  for idx,duration,cx,cy,w,h,first,n in frames:
   vertices=vs[first:first+n]
   if not vertices:continue
   im=atlases[int(vertices[0][-1])];aw,ah=im.size
   box=(round(min(v[3] for v in vertices)*aw),round((1-max(v[4] for v in vertices))*ah),round(max(v[3] for v in vertices)*aw),round((1-min(v[4] for v in vertices))*ah))
   path=OUT/f'{tag}-{key}-{idx}.png';im.crop(box).save(path)
   for f in range(idx,idx+duration):lookup[key,f]=(path,cx-w/2,cy-h/2,w,h)
 return lookup
with read_game_zip(GAME,'wilson.zip') as z:lookup=unpack(z,'native-wilson')
with ZipFile('mod/Tractor/anim/aom_tractor_cabin.zip') as z:lookup.update(unpack(z,'cabin'))
with ZipFile('mod/Tractor/anim/aom_attachment_shared.zip') as z:
 lookup.update(unpack(z,'equipment'));equipment=parse_anim(z.read('anim.bin'))['animations']
with ZipFile('mod/Tractor/anim/aom_tractor_driver.zip') as z:driver=parse_anim(z.read('anim.bin'))['animations']

def layer(e):
 data=lookup.get((e['symbol'],e['frame']))
 if not data:return ''
 path,x,y,w,h=data
 matrix=','.join(str(v) for v in e['matrix'])
 return f'<image xlink:href="{escape(str(path))}" x="{x}" y="{y}" width="{w}" height="{h}" transform="matrix({matrix})"/>'

def cell(mask,kind=None):
 a=next(a for a in driver if a['name']=='idle_loop' and a['facing']==mask)
 es=list(a['frames'][0]['elements'])
 rear=''
 if kind:
  a=next(a for a in equipment if a['name']==kind and a['bank']==name_hash('aom_attachment_mounted') and a['facing']==mask)
  rear=''.join(layer(e) for e in sorted(a['frames'][0]['elements'],key=lambda e:e['z'],reverse=True))
 return rear+''.join(layer(e) for e in sorted(es,key=lambda e:e['z'],reverse=True))
views=[('Front',8),('Front diagonal',192),('Side',5),('Rear diagonal',48),('Rear',2)]
svg=['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1550" height="990"><rect width="100%" height="100%" fill="#d1bd97"/><g font-family="Arial" text-anchor="middle" fill="#221c13">']
svg.append('<text x="775" y="32" font-size="23">Compiled driver poses and mounted equipment — local resource preview</text>')
for i,(label,mask) in enumerate(views):
 x=155+i*310
 svg.append(f'<text x="{x}" y="70" font-size="19">{label}</text><g transform="translate({x},425) scale(1.1)">{cell(mask)}</g>')
for i,kind in enumerate(['weeder','plow','irrigator','fertilizer','seeder']):
 x=155+i*310
 svg.append(f'<text x="{x}" y="500" font-size="19">{kind}: front occlusion</text><g transform="translate({x},865) scale(1.1)">{cell(8,kind)}</g>')
svg.append('<text x="775" y="940" font-size="18">Rear implements are hidden only in the mounted front view. Harvester is unchanged.</text>')
svg.append('<text x="775" y="970" font-size="15">Native character textures are extracted for local inspection only; this preview is not an in-game screenshot.</text></g></svg>')
p=OUT/'driver-and-occlusion.svg';p.write_text(''.join(svg));run([sys.executable,OUT/'render_png.py']);print(p.with_suffix('.png'))
