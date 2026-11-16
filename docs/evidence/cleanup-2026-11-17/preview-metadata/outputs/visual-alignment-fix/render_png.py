from pathlib import Path
import sys
from PIL import Image,ImageDraw,ImageFont
# Reuse decoded local sprites; no further native-asset extraction.
import xml.etree.ElementTree as ET
OUT=Path(__file__).resolve().parent
root=ET.parse(OUT/'driver-and-occlusion.svg').getroot()
canvas=Image.new('RGBA',(1550,990),'#d1bd97')
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',19)
cache={}
def render(e,ox,oy,scale):
 path=e.attrib['{http://www.w3.org/1999/xlink}href']
 if path not in cache:cache[path]=Image.open(path).convert('RGBA')
 im=cache[path];x,y,w,h=[float(e.attrib[k]) for k in ['x','y','width','height']]
 a,b,c,d,tx,ty=map(float,e.attrib['transform'][7:-1].split(','))
 A=scale*a*w/im.width;B=scale*c*h/im.height;C=ox+scale*(a*x+c*y+tx)
 D=scale*b*w/im.width;E=scale*d*h/im.height;F=oy+scale*(b*x+d*y+ty)
 det=A*E-B*D
 if abs(det)<1e-9:return
 inverse=(E/det,-B/det,(B*F-E*C)/det,-D/det,A/det,(D*C-A*F)/det)
 layer=im.transform(canvas.size,Image.AFFINE,inverse,Image.BICUBIC)
 canvas.alpha_composite(layer)
for group in root.iter('{http://www.w3.org/2000/svg}g'):
 transform=group.attrib.get('transform','')
 if not transform:continue
 xy=transform.split('translate(')[1].split(')')[0];ox,oy=map(float,xy.split(','))
 scale=float(transform.split('scale(')[1].split(')')[0])
 for e in group:
  if e.tag.endswith('image'):render(e,ox,oy,scale)
draw=ImageDraw.Draw(canvas)
for e in root.iter('{http://www.w3.org/2000/svg}text'):
 x,y=float(e.attrib['x']),float(e.attrib['y']);draw.text((x,y-20),e.text,fill='#221c13',font=font,anchor='mt')
canvas.convert('RGB').save(OUT/'driver-and-occlusion.png')
print(OUT/'driver-and-occlusion.png')
