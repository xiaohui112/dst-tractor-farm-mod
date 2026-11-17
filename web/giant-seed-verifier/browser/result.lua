-- Serialize the native plan; this file contains no placement/search decisions.
local NULL={}
local function array(t)return setmetatable(t or {},{__json_array=true})end
local function quote(s)
 return '"'..s:gsub('[%z\1-\31\\"]',function(c)
  local escapes={['"']='\\"',['\\']='\\\\',['\n']='\\n',['\r']='\\r',['\t']='\\t'}
  return escapes[c]or string.format('\\u%04x',string.byte(c))
 end)..'"'
end
local function json(v)
 if v==NULL or v==nil then return 'null' end
 local kind=type(v)
 if kind=='boolean'then return v and 'true'or'false'end
 if kind=='number'then assert(v==v and math.abs(v)~=math.huge,'非有限数值');return string.format('%.17g',v)end
 if kind=='string'then return quote(v)end
 assert(kind=='table','不可序列化的类型：'..kind)
 local out={}
 if getmetatable(v)and getmetatable(v).__json_array then
  for i=1,#v do out[i]=json(v[i])end;return '['..table.concat(out,',')..']'
 end
 for k,value in pairs(v)do out[#out+1]=quote(tostring(k))..':'..json(value)end
 return '{'..table.concat(out,',')..'}'
end
local function fields(t,names)
 local out={};for _,name in ipairs(names)do
  local value=t and t[name];if value==nil then value=NULL end;out[name]=value
 end;return out
end
local b=r.plan
local construction=r.construction
local out={reason=r.reason or NULL,valid=not not r.valid,ticks=r.ticks,
 timings={quantity_ms=(construction and construction.quantity_seconds or 0)*1000,
 arrangement_ms=(construction and construction.arrangement_seconds or 0)*1000,
 template_prepare_ms=(construction and construction.template_prepare_seconds or 0)*1000,
 template_select_ms=(construction and construction.template_select_seconds or 0)*1000,basis='browser_elapsed'}}
if not b then
 assert(not construction or(construction.total or 0)==0,'最大数量候选没有通过Mod最终校验。')
 out.count=0;out.upper=0;out.optimal=false;out.slots=array();out.tiles=array()
 return json(out)
end
out.count=b.total;out.upper=b.upper;out.optimal=not not b.optimal
out.slots=array();for _,p in ipairs(b.slots)do out.slots[#out.slots+1]=fields(p,{'x','z','cx','cz','crop','index'})end
out.tiles=array();for _,t in ipairs(b.tiles)do out.tiles[#out.tiles+1]={x=t.x,z=t.z}end
out.template_modules=array();for _,m in ipairs(construction and construction.modules or {})do
 out.template_modules[#out.template_modules+1]={id=m.id,tiles=array(m.tiles),symmetry=m.symmetry,origin=m.origin,crops=m.crops}
end
local arrange=b.arrangement
local pattern=arrange.after
if not pattern.pattern_mismatch then
 local board={};for i,p in ipairs(b.slots)do board[i]=p.crop or false end
 local geometry=require('aom_seed_layout').Geometry(b.tiles,b.slots,r.defs)
 pattern=require('aom_seed_arrangement').Metrics(board,geometry)
end
out.layout={score=arrange.after.score,components=arrange.after.components,
 fragmentation=arrange.after.fragmentation,limited=not not arrange.limited,
 family_distance=arrange.after.family,tidy=arrange.after.tidy,search_limited=not not b.construction.limited,
 objective=arrange.objective or(INPUT.strategy=='GIANT_TEMPLATE'and'fixed-templates'or'legacy-compactness'),
 pattern_mismatch=pattern.pattern_mismatch,line_cost=pattern.line_cost,hole_cost=pattern.hole_cost,order_cost=pattern.order_cost}
return json(out)
