-- 模版预览只同步附近完整模块；全田计划与进度仍由服务器保存。
local M={RADIUS=20,MAX_POINTS=512,MAX_MODULES=64,MAX_BYTES=24000}
local Catalog=require('aom_seed_catalog')
local specs={};for _,s in ipairs(Catalog.templates)do specs[s.id]=s end
local function Key(x,z)return x..':'..z end
local function Number(v)return type(v)=='number'and v==v and math.abs(v)<1000000 end
local function Integer(v)return type(v)=='number'and v==v and v>=0 and v%1==0 and v<=9007199254740991 end
local function Split(text,sep)
 local out={};for part in (text..sep):gmatch('(.-)'..sep)do out[#out+1]=part end;return out
end
function M.Prepare(b,yieldfn)
 if b._aom_template_index then return b._aom_template_index end
 local index={tiles={},modules={},bytile={},remaining={}}
 for ti,t in ipairs(b.tiles)do index.tiles[Key(t.x,t.z)]=ti;if ti%32==0 and yieldfn then yieldfn()end end
 for i,p in ipairs(b.slots)do if p.crop and not b.completed[i]then index.remaining[p.crop]=(index.remaining[p.crop]or 0)+1 end;if i%128==0 and yieldfn then yieldfn()end end
 for _,m in ipairs(b.construction and b.construction.modules or {})do
  local spec=specs[m.id];local variant
  for _,v in ipairs(spec and spec.variants or {})do if v.symmetry==m.symmetry then variant=v end end
  if variant then
   local item={source=m,variant=variant,indices={},tiles={}}
   for dz=0,variant.h-1 do for dx=0,variant.w-1 do
    local key=Key(m.origin.x+dx*4,m.origin.z+dz*4);local ti=index.tiles[key]
    if ti then
     item.tiles[#item.tiles+1]=ti;index.bytile[key]=item
     for s=1,9 do item.indices[#item.indices+1]=(ti-1)*9+s end
    end
   end end
   index.modules[#index.modules+1]=item
  end
  if yieldfn then yieldfn()end
 end
 b._aom_template_index=index;return index
end
function M.Complete(b,i)
 if b.completed[i]then return end
 b.completed[i]=true;b.done=b.done+1
 local index=b._aom_template_index;local p=b.slots[i]
 if index and p and p.crop then index.remaining[p.crop]=index.remaining[p.crop]-1 end
end
function M.Position(inst)
 local source=inst._rider or inst
 return source.Transform:GetWorldPosition()
end
function M.Encode(inst,nx,nz)
 local b=inst._block;local index=M.Prepare(b);local x,_,z=M.Position(inst)
 x,_,z=TheWorld.Map:GetTileCenterPoint(x,0,z)
 inst._aom_template_preview_center=Key(x,z)
 local found,seen={},{}
 for dx=-M.RADIUS,M.RADIUS,4 do for dz=-M.RADIUS,M.RADIUS,4 do
  local item=index.bytile[Key(x+dx,z+dz)]
  if item and not seen[item]then seen[item]=true;found[#found+1]=item end
 end end
 table.sort(found,function(a,b)
  local p,q=a.source.origin,b.source.origin;local da,db=(p.x-x)^2+(p.z-z)^2,(q.x-x)^2+(q.z-z)^2
  return da~=db and da<db or da==db and(p.z~=q.z and p.z<q.z or p.z==q.z and p.x<q.x)
 end)
 local encoded,points,bytes={},0,0
 for _,item in ipairs(found)do
  local m=item.source;local bits,offsets={},{};local pending=0
  for localindex,i in ipairs(item.indices)do local p=b.slots[i];local active=p.crop and not b.completed[i]
   bits[localindex]=active and '1'or '0'
   if active then
    pending=pending+1;local s=(i-1)%9
    local px,pz=p.cx+(s%3-1)*4/3,p.cz+(math.floor(s/3)-1)*4/3
    if math.abs(px-p.x)>.00001 or math.abs(pz-p.z)>.00001 then offsets[#offsets+1]=localindex..'@'..string.format('%.4f@%.4f',p.x,p.z)end
   end
  end
  if pending>0 then
   local part=table.concat({m.id,m.symmetry,m.origin.x,m.origin.z,m.crops.A or '',m.crops.B or '',m.crops.C or '',m.crops.D or '',table.concat(bits),table.concat(offsets,'/')},',')
   if #encoded<M.MAX_MODULES and points+pending<=M.MAX_POINTS and bytes+#part+1<M.MAX_BYTES-256 then
    encoded[#encoded+1]=part;points=points+pending;bytes=bytes+#part+1
   end
  end
 end
 return table.concat({'D6',b.total,b.done,b.season,nx or '',nz or '',Catalog.version,table.concat(encoded,'|')},';')
end
function M.Decode(text)
 if type(text)~='string'or #text>M.MAX_BYTES then return end
 local total,done,season,nx,nz,version,raw=text:match('^D6;(%d+);(%d+);([a-z]+);([^;]*);([^;]*);([^;]*);([^;]*)$')
 total,done=tonumber(total),tonumber(done)
 if not Integer(total)or total<1 or not Integer(done)or done>total or version~=Catalog.version then return end
 if season~='autumn'and season~='winter'and season~='spring'and season~='summer'then return end
 local b={dynamic=true,strategy='GIANT_TEMPLATE',total=total,done=done,season=season,confirmed=true,completed={},tiles={},slots={},preview_partial=true}
 if nx~=''or nz~=''then nx,nz=tonumber(nx),tonumber(nz);if not Number(nx)or not Number(nz)then return end;b.next_x,b.next_z=nx,nz end
 local tilekeys,pointkeys,occupied={}, {},{};local count=0
 for part in raw:gmatch('[^|]+')do
  count=count+1;if count>M.MAX_MODULES then return end
  local f=Split(part,',');if #f~=10 then return end
  local spec=specs[f[1]];local symmetry,x,z=tonumber(f[2]),tonumber(f[3]),tonumber(f[4]);local variant
  if not spec or not Number(x)or not Number(z)then return end
  for _,v in ipairs(spec.variants)do if v.symmetry==symmetry then variant=v end end
  if not variant or #f[9]~=#variant.cells or f[9]:find('[^01]')then return end
  local map={A=f[5],B=f[6],C=f[7],D=f[8]};local recipe
  for _,r in ipairs(spec.recipes)do
   local same=true;for _,role in ipairs({'A','B','C','D'})do if (r.map[role]or '')~=map[role]then same=false end end
   if same then for _,s in ipairs(r.seasons)do if s==season then recipe=r end end end
  end
  if not recipe then return end
  local overrides={}
  for offset in f[10]:gmatch('[^/]+')do
   local i,px,pz=offset:match('^(%d+)@([^@]+)@([^@]+)$');i,px,pz=tonumber(i),tonumber(px),tonumber(pz)
   if not i or i<1 or i>#variant.cells or overrides[i]or not Number(px)or not Number(pz)or f[9]:sub(i,i)~='1'then return end
   overrides[i]={x=px,z=pz}
  end
  for t=0,variant.w*variant.h-1 do
   local cx,cz=x+(t%variant.w)*4,z+math.floor(t/variant.w)*4;local key=Key(cx,cz)
   if occupied[key]then return end;occupied[key]=true
   for s=0,8 do local i=t*9+s+1
    if f[9]:sub(i,i)=='1'then
     local crop=recipe.map[variant.cells[i]];if not crop or #b.slots>=M.MAX_POINTS or #b.slots>=total-done then return end
     local p=overrides[i]or {x=cx+(s%3-1)*4/3,z=cz+(math.floor(s/3)-1)*4/3}
     if math.abs(p.x-(cx+(s%3-1)*4/3))>.4001 or math.abs(p.z-(cz+(math.floor(s/3)-1)*4/3))>.4001 then return end
     local pk=string.format('%.4f:%.4f',p.x,p.z);if pointkeys[pk]then return end;pointkeys[pk]=true
     if not tilekeys[key]then tilekeys[key]=true;b.tiles[#b.tiles+1]={x=cx,z=cz}end
     p.cx,p.cz,p.crop,p.index=cx,cz,crop,#b.slots+1;b.slots[#b.slots+1]=p
    end
   end
  end
 end
 return b
end
return M
