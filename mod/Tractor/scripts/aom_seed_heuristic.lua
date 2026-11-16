-- 仅生成可行下界；截断不作为数量最优证明，不调用排列整理。
-- 按逐地皮互补组合装填库存，在真实坑位上验证同族并提供可行下界。
local M={}
local function Empty(n)local a={};for i=1,n do a[i]=false end;return a end
function M.Balanced(crops,stock,tiles,slots,defs,yieldfn,refined,initialboard,initialreport,warmLimit)
 local Balance=require('aom_seed_balance')
 local Layout=require('aom_seed_layout')
 local patterns,vectors=Balance.Patterns(crops,stock,defs,yieldfn)
 if #patterns==0 then return nil,{upper=0,nodes=0,limited=false} end
 local upper=Balance.Upper(crops,stock,vectors,#tiles*patterns[1].n)
 local geometry=Layout.Geometry(tiles,slots,defs,yieldfn);geometry.balanced=true
 local remaining,used={},{};for i,k in ipairs(crops) do remaining[i]=stock[k];used[i]=0 end
 local bins,best,bestn,bestmetrics,arrangement={},nil,0,nil,nil
 if refined and initialboard then
  best={};for i,k in ipairs(initialboard) do best[i]=k end
  bestn=initialreport.total;bestmetrics=initialreport.arrangement.after;arrangement=initialreport.arrangement
  upper=math.min(upper,initialreport.upper)
 end
 local nodes,layouts,limited=0,0,false
 local goal_layouts=0
 local effort,worktotal=0,0
 local function LayoutLimit()if warmLimit and worktotal>=warmLimit then limited=true;return true end;return (refined and goal_layouts or layouts)>=96 end
 local function Budget(n)effort=effort+(n or 1);worktotal=worktotal+(n or 1);if effort>800000 or worktotal>8000000 or warmLimit and worktotal>=warmLimit then limited=true;return false end;return true end
 local proposals={};local largest=0
 local nodebudget=#tiles>16 and 1000 or 4000
 local state=17
 local function Rand(n)state=state*16807%2147483647;return state%n+1 end
 -- 差量维护同族支持数；拒绝试探后的回滚也在下一次差量中校正。
 local lastboard,lastcopy,family,missing,lastbad=nil,{}, {}, {},0
 local neighbors={}
 for _,k in ipairs(crops) do neighbors[k]={};for i=1,#slots do local a={};for _,q in ipairs(geometry.near[i]) do if Layout.InRange(geometry,i,q.j,(defs[k].family_check_dist or 4)^2) then a[#a+1]=q.j end end;neighbors[k][i]=a end end
 local function Penalty(k,n)
  if not k then return 0 end
  local missing=math.max(0,(defs[k].family_min_count or 4)-n)
  return missing*missing
 end
 local function Bad(board)
  if board~=lastboard then
   lastboard=board;lastcopy={};family={};missing={};lastbad=0
   for _,k in ipairs(crops) do family[k]={};for i=1,#slots do family[k][i]=0 end end
   for i,k in ipairs(board) do lastcopy[i]=k;if k then for _,j in ipairs(neighbors[k][i]) do family[k][j]=family[k][j]+1 end end end
   for i,k in ipairs(board) do missing[i]=Penalty(k,k and family[k][i] or 0);lastbad=lastbad+missing[i] end
  else
   local affected={}
   for i,k in ipairs(board) do local old=lastcopy[i]
    if old~=k then
     affected[i]=true
     if old then for _,j in ipairs(neighbors[old][i]) do family[old][j]=family[old][j]-1;affected[j]=true end end
     if k then for _,j in ipairs(neighbors[k][i]) do family[k][j]=family[k][j]+1;affected[j]=true end end
     lastcopy[i]=k
    end
   end
   for i in pairs(affected) do local k=board[i];local n=Penalty(k,k and family[k][i] or 0);lastbad=lastbad+n-missing[i];missing[i]=n end
  end
  local violations={};for i,n in ipairs(missing) do if n>0 then violations[#violations+1]=i end end
  return lastbad,violations
 end
 -- 恰好四株的同族必须两两在原版半径内。按各格配额枚举真实四元组，
 -- 再做不重叠覆盖，补齐随机交换难以同时移动多个同族的情形。
 local function QuadCover(order)
  for _,n in ipairs(used) do if n>0 and n~=4 then return nil end end
  local available={};for i=1,#slots do available[i]=true end
  for t,index in ipairs(order) do
   local p=bins[index];local four=0;for _,n in ipairs(p.counts) do if n==4 then four=four+1 end end
   if p.n==8 and four==2 then available[(t-1)*9+5]=false end
  end
  local domains={};local generated=0
  for k,crop in ipairs(crops) do if used[k]>0 then
   local requirements={}
   for t,index in ipairs(order) do if bins[index].counts[k]>0 then requirements[#requirements+1]={t=t,n=bins[index].counts[k]} end end
   local domain={crop=crop,groups={}};local group={};local radius=(defs[crop].family_check_dist or 4)^2
   local function Generate(at,position,left)
    generated=generated+1;if generated%256==0 and yieldfn then yieldfn() end
    if generated>120000 then return end
    if at>#requirements then
     local copy,cost={},0;for i,p in ipairs(group) do copy[i]=p;for j=1,i-1 do local q=slots[group[j]];cost=cost+(slots[p].x-q.x)^2+(slots[p].z-q.z)^2 end end
     domain.groups[#domain.groups+1]={points=copy,cost=cost};return
    end
    local r=requirements[at]
    if left==0 then Generate(at+1,1,requirements[at+1] and requirements[at+1].n or 0);return end
    for s=position,10-left do local i=(r.t-1)*9+s
     if available[i] then
      local ok=true;for _,j in ipairs(group) do if not Layout.InRange(geometry,i,j,radius) then ok=false;break end end
      if ok then group[#group+1]=i;Generate(at,s+1,left-1);group[#group]=nil end
     end
    end
   end
   Generate(1,1,requirements[1].n)
   if #domain.groups==0 then return nil end
   table.sort(domain.groups,function(a,b)return a.cost<b.cost end);domains[#domains+1]=domain
  end end
  local board=Empty(#slots);local covered={};local steps=0
  local function Search(left)
   steps=steps+1;if steps>1500 or not Budget() then return false end
   if steps%64==0 and yieldfn then yieldfn() end
   if left==0 then return true end
   local chosen,options=nil,nil
   for i,d in ipairs(domains) do if not covered[i] then
    local candidates={}
    for _,g in ipairs(d.groups) do
     if not Budget() then return false end
     local ok=true;for _,p in ipairs(g.points) do if board[p] then ok=false;break end end
     if ok then candidates[#candidates+1]=g end
    end
    if #candidates==0 then return false end
    if not options or #candidates<#options then chosen,options=i,candidates end
   end end
   covered[chosen]=true
   for _,g in ipairs(options) do
    for _,p in ipairs(g.points) do board[p]=domains[chosen].crop end
    if Search(left-1) then return true end
    for _,p in ipairs(g.points) do board[p]=false end
   end
   covered[chosen]=nil;return false
  end
  if Search(#domains) then return board end
 end
 -- 联合求解四株同族覆盖和逐格互补，避免先锁定数量分格漏掉可行组合。
 local groupcache,grouporder,groupcount={}, {},0
 local function FamilyField(allocation,total,catalog,offset)
  local started=effort;local trial_steps=0
  local function TrialExhausted()return refined and trial_steps>140000 or not refined and effort-started>140000 end
  if #slots>144 then return nil end
  local pieces,remainingquota={},{}
  local extra={};local ceiling=refined and (offset or 0)%2==0 and 7 or 9
  for k,n in ipairs(allocation) do
   if not refined and n>9 then return nil end
   remainingquota[k]=n
   local count=math.max(1,math.ceil(n/ceiling));local base=math.floor(n/count);local rem=n%count
   pieces[k]={k=k,n=base+(rem>0 and 1 or 0)}
   for i=2,count do extra[#extra+1]={k=k,n=base+(i<=rem and 1 or 0)} end
  end
  for _,piece in ipairs(extra) do pieces[#pieces+1]=piece end
  local board=Empty(#slots);local free={};for i=1,#slots do free[i]=true end
  local taken,localcounts={},{};for t=1,#tiles do localcounts[t]={};for k=1,#crops do localcounts[t][k]=0 end end
  local groups,quadindex={},nil;local visits=0;local blanks=#slots-total
  local feasible={};local radius=math.huge
  for t=1,#tiles do
   feasible[t]={};for _,p in ipairs(catalog) do if p.n>=9-blanks then feasible[t][#feasible[t]+1]=p end end
   local zero={counts={},n=0};for k=1,#crops do zero.counts[k]=0 end;if blanks>=9 then feasible[t][#feasible[t]+1]=zero end
  end
  for k,n in ipairs(allocation) do if n>0 then radius=math.min(radius,(defs[crops[k]].family_check_dist or 4)^2) end end
  local function Groups(first,size)
   local key=first..':'..size
   if size==4 and groups[key] then return groups[key] end
   if size>4 then
    local out,seen={},{}
    for axis=0,4 do
     local indices={};for i=first+1,#slots do if free[i] then indices[#indices+1]=i end end
     local function Cost(i)
      local dx,dz=slots[i].x-slots[first].x,slots[i].z-slots[first].z
      local cross=axis==1 and dx or axis==2 and dz or axis==3 and dx+dz or axis==4 and dx-dz or 0
      return dx*dx+dz*dz+cross*cross*.8
     end
     table.sort(indices,function(a,b)local x,y=Cost(a),Cost(b);return x~=y and x<y or x==y and a<b end)
     while #indices>size+3 do indices[#indices]=nil end
     table.sort(indices);local selected={first}
     local function Generate(at)
      if warmLimit and worktotal>=warmLimit then out.incomplete=true;return end
      if #selected==size then
       local signature=table.concat(selected,',');if seen[signature] then return end;seen[signature]=true
       local cost=0
       for _,i in ipairs(selected) do
        local family=0;for _,j in ipairs(selected) do local d=(slots[i].x-slots[j].x)^2+(slots[i].z-slots[j].z)^2;if Layout.InRange(geometry,i,j,radius)then family=family+1 end;cost=cost+d end
        if family<4 then return end
       end
       local points={};for i,p in ipairs(selected) do points[i]=p end;out[#out+1]={points=points,cost=cost}
       return
      end
      for j=at,#indices-(size-#selected)+1 do selected[#selected+1]=indices[j];Generate(j+1);selected[#selected]=nil end
     end
     Generate(1)
     if yieldfn then yieldfn() end
    end
    -- 五、六株并不一定含四株两两相邻的小团。补充完整的锚点三邻居支持集，
    -- 其余成员允许在锚点半径外，只逐株检查至少四个同族。
    if refined and size<=6 then
     local nearby,available={},{}
     for i=first+1,#slots do if free[i] then
      available[#available+1]=i
      if Layout.InRange(geometry,i,first,radius) then nearby[#nearby+1]=i end
     end end
     local selected,inside={first},{[first]=true};local generated=0
     local function Complete(at,left)
      generated=generated+1;if generated>30000 then limited=true;return end
      if not Budget() then return end
      if effort%256==0 and yieldfn then yieldfn() end
      for _,i in ipairs(selected) do
       local family=0;for _,j in ipairs(selected) do if Layout.InRange(geometry,i,j,radius) then family=family+1 end end
       if family+left<4 then return end
      end
      if left==0 then
       local points={};for i,p in ipairs(selected) do points[i]=p end;table.sort(points)
       local signature=table.concat(points,',');if seen[signature] then return end;seen[signature]=true
       local cost=0;for _,i in ipairs(points) do for _,j in ipairs(points) do cost=cost+(slots[i].x-slots[j].x)^2+(slots[i].z-slots[j].z)^2 end end
       out[#out+1]={points=points,cost=cost};return
      end
      for j=at,#available-left+1 do local i=available[j]
       if not inside[i] then inside[i]=true;selected[#selected+1]=i;Complete(j+1,left-1);selected[#selected]=nil;inside[i]=nil end
       if effort>800000 or generated>30000 then return end
      end
     end
     for a=1,#nearby-2 do for b=a+1,#nearby-1 do for c=b+1,#nearby do
      selected={first,nearby[a],nearby[b],nearby[c]};inside={[first]=true,[nearby[a]]=true,[nearby[b]]=true,[nearby[c]]=true}
      Complete(1,size-4)
      if effort>800000 or generated>30000 then out.incomplete=true;table.sort(out,function(x,y)return x.cost<y.cost end);return out end
     end end end
    end
    -- 五至七株还可能由两个四株同族团共享成员构成；不能只搜索锚点附近的小团。
    if size<=7 then
     if not quadindex then
      quadindex={};for i=1,#slots do quadindex[i]={} end
      for i=1,#slots do for _,q in ipairs(Groups(i,4)) do for _,p in ipairs(q.points) do quadindex[p][#quadindex[p]+1]=q end end end
     end
     for _,a in ipairs(Groups(first,4)) do
      local available=true;for _,i in ipairs(a.points) do if not free[i] then available=false;break end end
      if available then for _,shared in ipairs(a.points) do for _,b in ipairs(quadindex[shared]) do
       if not Budget() then out.incomplete=true;table.sort(out,function(a,b)return a.cost<b.cost end);return out end
       if effort%256==0 and yieldfn then yieldfn() end
       local union,points={},{};local ok=true
       for _,q in ipairs({a,b}) do for _,i in ipairs(q.points) do
        if i<first or not free[i] then ok=false;break end
        if not union[i] then union[i]=true;points[#points+1]=i end
       end end
       if ok and #points==size then
        table.sort(points);local signature=table.concat(points,',')
        if not seen[signature] then
         seen[signature]=true;local cost=0
         for _,i in ipairs(points) do for _,j in ipairs(points) do cost=cost+(slots[i].x-slots[j].x)^2+(slots[i].z-slots[j].z)^2 end end
         out[#out+1]={points=points,cost=cost}
        end
       end
      end end end
     end
    end
    table.sort(out,function(a,b)return a.cost<b.cost end);return out
   end
   local neighbors={};for _,q in ipairs(geometry.near[first]) do if q.j>first and Layout.InRange(geometry,first,q.j,radius) then neighbors[#neighbors+1]=q.j end end
   local out={}
   for a=1,#neighbors-2 do local i=neighbors[a]
    for b=a+1,#neighbors-1 do local j=neighbors[b]
     if Layout.InRange(geometry,i,j,radius) then
      for c=b+1,#neighbors do local k=neighbors[c]
       if Layout.InRange(geometry,i,k,radius) and Layout.InRange(geometry,j,k,radius) then
        local points={first,i,j,k};local cost=0
        for x=1,4 do for y=1,x-1 do cost=cost+(slots[points[x]].x-slots[points[y]].x)^2+(slots[points[x]].z-slots[points[y]].z)^2 end end
        out[#out+1]={points=points,cost=cost}
       end
      end
     end
    end
   end
   table.sort(out,function(a,b)return a.cost<b.cost end);groups[key]=out;return out
  end
  local generate=Groups
  Groups=function(first,size)
   if size==4 then return generate(first,size) end
   local bits={};for i,v in ipairs(free) do bits[i]=v and '1' or '0' end
   local key=radius..':'..first..':'..size..':'..table.concat(bits)
   if groupcache[key] then return groupcache[key] end
   local out=generate(first,size)
   if not out.incomplete and #out<=12000 then
    while (#grouporder>=256 or groupcount+#out>24000) and #grouporder>0 do local old=table.remove(grouporder,1);groupcount=groupcount-#groupcache[old];groupcache[old]=nil end
    groupcache[key]=out;grouporder[#grouporder+1]=key;groupcount=groupcount+#out
   end
   return out
  end
  local function Search(left,holes)
   visits=visits+1;trial_steps=trial_steps+1;if visits>1000 or TrialExhausted() or not Budget() then return false end
   if visits%32==0 and yieldfn then yieldfn() end
   if left==0 then return Balance.Board(board,defs) end
   local first;for i,v in ipairs(free) do if v then first=i;break end end
   if not first then return false end
   local function SkipHole()
    if holes<=0 then return false end
    local t=math.floor((first-1)/9)+1;local previous=feasible[t];free[first]=false
    local capacity=0;for i=(t-1)*9+1,t*9 do if free[i] or board[i] then capacity=capacity+1 end end
    local allowed={};for _,p in ipairs(previous) do if p.n<=capacity then allowed[#allowed+1]=p end end
    feasible[t]=allowed;local ok=#allowed>0 and Search(left,holes-1);feasible[t]=previous;free[first]=true;return ok
   end
   local holesfirst=refined and (offset or 0)%2==1
   if holesfirst and SkipHole() then return true end
   local sizes={};for index,piece in ipairs(pieces) do if piece.n>0 and not taken[index] then sizes[piece.n]=true end end
   for phase=0,5 do local size=(phase+(offset or 0))%6+4;if sizes[size] then for _,group in ipairs(Groups(first,size)) do
    trial_steps=trial_steps+1
    if not Budget() then return false end
    local ok=true;for _,i in ipairs(group.points) do if not free[i] then ok=false;break end end
    if ok then
     local affected={};for _,i in ipairs(group.points) do affected[math.floor((i-1)/9)+1]=true end
     local equivalent={}
     for ci=1,#pieces do
      local index=(ci-1+(offset or 0))%#pieces+1;local piece=pieces[index];local k=piece.k;local crop=crops[k]
      trial_steps=trial_steps+1
      if TrialExhausted() or not Budget() then return false end
      local signature=table.concat(vectors[k],',')..':'..(defs[crop].family_check_dist or 4)
      if refined then signature=signature..':'..remainingquota[k]..':'..(remainingquota[k]<allocation[k] and crop or '') end
      if piece.n==size and not taken[index] and not equivalent[signature] then
      equivalent[signature]=true
      taken[index]=true;remainingquota[k]=remainingquota[k]-size
      for _,i in ipairs(group.points) do local t=math.floor((i-1)/9)+1;board[i]=crop;free[i]=false;localcounts[t][k]=localcounts[t][k]+1 end
      local extend=true;local previous={}
      for t=1,#tiles do
       previous[t]=feasible[t];local allowed={}
       for _,p in ipairs(feasible[t]) do if p.counts[k]>=localcounts[t][k] and p.counts[k]<=localcounts[t][k]+remainingquota[k] and not (p.center_gap and board[(t-1)*9+5]) then allowed[#allowed+1]=p end end
       feasible[t]=allowed;if #allowed==0 then extend=false end
      end
      if extend then
       local minimum,maximum=0,0
       for t=1,#tiles do local lo,hi=9,0;for _,p in ipairs(feasible[t]) do lo=math.min(lo,p.n);hi=math.max(hi,p.n) end;minimum=minimum+lo;maximum=maximum+hi end
       extend=minimum<=total and maximum>=total
      end
      if extend and Search(left-1,holes) then return true end
      for t=1,#tiles do feasible[t]=previous[t] end
      for _,i in ipairs(group.points) do local t=math.floor((i-1)/9)+1;board[i]=false;free[i]=true;localcounts[t][k]=localcounts[t][k]-1 end
      taken[index]=nil;remainingquota[k]=remainingquota[k]+size
      if visits>1000 then return false end
     end end
    end
   end
   end end
   if not holesfirst and SkipHole() then return true end
   return false
  end
  local species=0;for _,piece in ipairs(pieces) do if piece.n>0 then species=species+1 end end
  if Search(species,blanks) then return board end
 end
 -- 交换净变化相同的种子组，解开“每格数量已锁定”造成的同族死局。
 -- 一换一、一换二或二换二都保持整片用量、总株数和逐格互补。
 local vectorbycrop={};for i,k in ipairs(crops) do vectorbycrop[k]=vectors[i] end
 local function Exchange(board,a,b)
  if a==b then return nil end
  local function Bundles(t)
   local count,keys,holes={}, {},0
   for s=1,9 do local k=board[(t-1)*9+s];if k then if not count[k] then keys[#keys+1]=k;count[k]=0 end;count[k]=count[k]+1 else holes=holes+1 end end
   table.sort(keys);local bundles={{ids={},net='0,0,0',key=''}}
   local function Add(ids)
    local v={0,0,0};for _,k in ipairs(ids) do for j=1,3 do v[j]=v[j]+vectorbycrop[k][j] end end
    bundles[#bundles+1]={ids=ids,net=table.concat(v,','),key=table.concat(ids,',')}
   end
   for i,k in ipairs(keys) do
    Add({k})
    for j=i,#keys do if j~=i or count[k]>=2 then Add({k,keys[j]}) end end
   end
   return bundles,holes
  end
  local aa,ah=Bundles(a);local bb,bh=Bundles(b);local options={}
  for _,x in ipairs(aa) do for _,y in ipairs(bb) do
   if x.net==y.net and x.key~=y.key and ah+#x.ids>=#y.ids and bh+#y.ids>=#x.ids then options[#options+1]={x=x,y=y} end
  end end
  if #options==0 then return nil end
  local option=options[Rand(#options)];local old={}
  for _,t in ipairs({a,b}) do for s=1,9 do local i=(t-1)*9+s;old[i]=board[i] end end
  local function Remove(t,ids)
   for _,k in ipairs(ids) do for s=1,9 do local i=(t-1)*9+s;if board[i]==k then board[i]=false;break end end end
  end
  local function Add(t,ids)
   for _,k in ipairs(ids) do
    local empty={};for s=1,9 do local i=(t-1)*9+s;if not board[i] then empty[#empty+1]=i end end
    board[empty[Rand(#empty)]]=k
   end
   local cells={};for s=1,9 do cells[s]=board[(t-1)*9+s] end
   if not Balance.Shape(cells) then
    for s=1,9 do if not cells[s] then local i,j=(t-1)*9+s,(t-1)*9+5;board[i],board[j]=board[j],board[i];break end end
   end
  end
  Remove(a,option.x.ids);Remove(b,option.y.ids);Add(a,option.y.ids);Add(b,option.x.ids)
  return old
 end
 local function Construct(total)
  if warmLimit and worktotal>=warmLimit then return end
  if total<bestn then return end
  for i,k in ipairs(crops) do if used[i]>0 and used[i]<(defs[k].family_min_count or 4) then return end end
  layouts=layouts+1;goal_layouts=goal_layouts+1
  -- 同数量的多个数量组合参与比较；限制几何尝试，避免大田卡住服务器。
  if (refined and goal_layouts or layouts)>96 then limited=true;return end
  local cells={}
  for t,p in ipairs(bins) do
   local a={};for i,k in ipairs(crops) do for _=1,p.counts[i] do a[#a+1]=k end end
   while #a<9 do a[#a+1]=false end
   local bank=Layout.Candidates(a,yieldfn);for _,v in ipairs(bank) do if Balance.Shape(v.cells) then cells[t]=v.cells;break end end
  end
  -- 数量组合与物理地皮分别排列，优先让共享同族的地皮靠近。
  local orders,identity={},{};for i=1,#bins do identity[i]=i end
  local function OrderCost(order)
   local cost=0
   for i=1,#order do for j=i+1,#order do
    local a,b=bins[order[i]],bins[order[j]];local shared=0
    for k=1,#crops do
     if used[k]==4 and a.counts[k]>0 and b.counts[k]>0 then
      local connected=false;local radius=(defs[crops[k]].family_check_dist or 4)^2
      for p=(i-1)*9+1,i*9 do for q=(j-1)*9+1,j*9 do if Layout.InRange(geometry,p,q,radius)then connected=true;break end end;if connected then break end end
      if not connected then return math.huge end
     end
     shared=shared+math.min(a.counts[k],b.counts[k])
    end
    cost=cost+shared*((tiles[i].x-tiles[j].x)^2+(tiles[i].z-tiles[j].z)^2)
   end end
   return cost
  end
  local function Order(order)
   local copy={};for i,v in ipairs(order) do copy[i]=v end
   local cost=OrderCost(copy);if cost<math.huge then orders[#orders+1]={order=copy,cost=cost} end
  end
  if #bins<=6 then
   local active,order={},{}
   local function Permute(at)
    if at>#bins then Order(order);return end
    for i=1,#bins do if not active[i] then active[i]=true;order[at]=i;Permute(at+1);active[i]=nil end end
   end
   Permute(1)
  else
   Order(identity)
   local cost=OrderCost(identity)
   for step=1,math.min(120,#bins*8) do
    local i,j=Rand(#bins),Rand(#bins);identity[i],identity[j]=identity[j],identity[i]
    local nextcost=OrderCost(identity)
    if nextcost<cost then cost=nextcost;Order(identity) else identity[i],identity[j]=identity[j],identity[i] end
   end
  end
  table.sort(orders,function(a,b)return a.cost<b.cost end)
  local allfour=true;for _,n in ipairs(used) do if n>0 and n~=4 then allfour=false;break end end
  local candidate,cm=nil,nil
  for variant=1,math.min(allfour and 48 or 4,#orders) do
   local order=orders[variant].order
   local exact=QuadCover(order)
   if exact then candidate,cm=exact,Layout.Metrics(exact,geometry);break end
   if not allfour then for rotation=0,7 do
    local board=Empty(#slots)
    for t,index in ipairs(order) do local c=Layout.Transform(cells[index],rotation);for s=1,9 do board[(t-1)*9+s]=c[s] end end
    local bad,violations=Bad(board)
    if bad~=0 and #bins>1 then
     local repairlimit=#tiles>16 and 180 or 4000
     for step=1,repairlimit do
      if not Budget(20) then break end
      local i=#violations>0 and violations[Rand(#violations)] or Rand(#bins*9)
      local t=math.floor((i-1)/9)+1;local changed
      if step%3==0 then
       local other=Rand(#tiles)
       if refined and step%5~=0 then
        local neighbors={};for index,tile in ipairs(tiles) do if index~=t and (tile.x-tiles[t].x)^2+(tile.z-tiles[t].z)^2<=32 then neighbors[#neighbors+1]=index end end
        if #neighbors>0 then other=neighbors[Rand(#neighbors)] end
       end
       changed=Exchange(board,t,other)
      else
       local j=(t-1)*9+Rand(9)
       if board[i]~=board[j] then
        changed={[i]=board[i],[j]=board[j]};board[i],board[j]=board[j],board[i]
        local shape={};for s=1,9 do shape[s]=board[(t-1)*9+s] end
        if not Balance.Shape(shape) then for p,k in pairs(changed) do board[p]=k end;changed=nil end
       end
      end
      if changed then
       local nextbad,nextviolations=Bad(board)
       if nextbad<=bad or step%97==0 or step%29==0 and nextbad<=bad+2 or refined and nextbad<=bad+2 and step%11==0 then bad,violations=nextbad,nextviolations else for p,k in pairs(changed) do board[p]=k end end
      end
      if step%16==0 and yieldfn then yieldfn() end
      if bad==0 then break end
     end
    end
    if bad==0 and Balance.Board(board,defs) then
     local metric=Layout.Metrics(board,geometry)
     if Layout.Better(metric,cm) then candidate,cm=board,metric end
    end
    if yieldfn then yieldfn() end
   end
   end
   if candidate then break end
  end
  if candidate then
   local board=candidate;local m=Layout.Metrics(board,geometry);local details={before=m,after=m,trials=0,moves=0,passes=0,limited=false}
   if total>bestn or total==bestn and Layout.Better(details.after,bestmetrics) then
    best,bestn,bestmetrics,arrangement=board,total,details.after,details
   end
  end
 end
 local function Remember(total)
  if total<bestn or total==0 then return end
  for i,k in ipairs(crops) do if used[i]>0 and used[i]<(defs[k].family_min_count or 4) then return end end
  largest=math.max(largest,total)
  proposals[total]=proposals[total] or {}
  if #proposals[total]<16 then
   local copy={};for i,p in ipairs(bins) do copy[i]=p end
   proposals[total][#proposals[total]+1]=copy
  end
 end
 if not refined then
 -- 先保留每格独立满足同族的安全后备方案，随后搜索跨格完整组合。
 do
  local localstock={};for i,n in ipairs(remaining) do localstock[i]=n end
  local total=0
  for t=1,#tiles do
   local chosen
   for _,p in ipairs(patterns) do
    local ok=true
    for i,n in ipairs(p.counts) do if n>localstock[i] or n>0 and n<(defs[crops[i]].family_min_count or 4) then ok=false;break end end
    if ok then chosen=p;break end
   end
   if not chosen then break end
   bins[#bins+1]=chosen;total=total+chosen.n
   for i,n in ipairs(chosen.counts) do localstock[i]=localstock[i]-n;used[i]=used[i]+n end
  end
  Construct(total);bins={};for i in ipairs(used) do used[i]=0 end
 end
 -- 将原始互补比例放大到完整同族，再拆成逐格互补片段；支持库存尾数。
 do
  local macros={}
  local function Gcd(a,b)while b~=0 do a,b=b,a%b end;return a end
  for _,base in ipairs(patterns) do
   local divisor,kinds,minimum,maximum=0,0,1,math.floor(9/base.n)*#tiles
   for i,n in ipairs(base.counts) do if n>0 then
    divisor=Gcd(divisor,n);kinds=kinds+1
    minimum=math.max(minimum,math.ceil((defs[crops[i]].family_min_count or 4)/n))
    maximum=math.min(maximum,math.floor(stock[crops[i]]/n))
   end end
   if divisor==1 and kinds<=3 and maximum>=minimum then
    local factors,seen={minimum,minimum+1,minimum+2,maximum},{}
    for _,factor in ipairs(factors) do if factor<=maximum and not seen[factor] then
     seen[factor]=true;local pieces={};local left=factor
     while left>0 do
      local quantity=math.min(left,math.floor(9/base.n));local p={n=base.n*quantity,counts={}}
      for i,n in ipairs(base.counts) do p.counts[i]=n*quantity end
      pieces[#pieces+1]=p;left=left-quantity
     end
     local consumption={};for i,n in ipairs(base.counts) do consumption[i]=n*factor end
     macros[#macros+1]={counts=consumption,pieces=pieces,n=base.n*factor}
    end end
   end
  end
  table.sort(macros,function(a,b)
   if a.n/#a.pieces~=b.n/#b.pieces then return a.n/#a.pieces>b.n/#b.pieces end
   return a.n>b.n
  end)
  local target,bestbins,macronodes=0,{},0
  local function Search(first,space,total)
   macronodes=macronodes+1;if macronodes>3000 or warmLimit and worktotal>=warmLimit then return end
   if macronodes%32==0 and yieldfn then yieldfn() end
   if total>0 then
    target=math.max(target,total);bestbins[total]=bestbins[total] or {}
    if #bestbins[total]<4 then local copy={};for i,p in ipairs(bins) do copy[i]=p end;bestbins[total][#bestbins[total]+1]=copy end
   end
   for index=first,#macros do if macronodes>3000 then break end;local m=macros[index]
    local repeats=math.floor(space/#m.pieces)
    for i,n in ipairs(m.counts) do if n>0 then repeats=math.min(repeats,math.floor(remaining[i]/n)) end end
    for count=repeats,1,-1 do
     for i,n in ipairs(m.counts) do remaining[i]=remaining[i]-n*count end
     for _=1,count do for _,p in ipairs(m.pieces) do bins[#bins+1]=p end end
     Search(index+1,space-count*#m.pieces,total+count*m.n)
     for _=1,count*#m.pieces do bins[#bins]=nil end
     for i,n in ipairs(m.counts) do remaining[i]=remaining[i]+n*count end
    end
   end
  end
  Search(1,#tiles,0)
  for total=target,bestn+1,-1 do
   effort=0;if refined then goal_layouts=0 end
   for _,proposal in ipairs(bestbins[total] or {}) do
    bins=proposal;for i in ipairs(used) do used[i]=0 end
    for _,p in ipairs(bins) do for i,n in ipairs(p.counts) do used[i]=used[i]+n end end
    Construct(total)
    if bestn==total or effort>800000 then break end
   end
   if bestn==total or worktotal>8000000 then break end
  end
  bins={};for i in ipairs(used) do used[i]=0 end
 end
 end
 if bestn==upper then return best,{upper=upper,total=bestn,nodes=nodes,layouts=layouts,inventory_total=upper,allocation_nodes=0,effort=worktotal,limited=limited,arrangement=arrangement,mode=refined and 'balanced-tile-packing-refined' or 'balanced-tile-packing'} end
 local allocations,globalupper,allocationlimited,allocationnodes=Balance.Allocations(crops,stock,vectors,#tiles*patterns[1].n,yieldfn)
 if not allocationlimited then upper=math.min(upper,globalupper) end
 limited=limited or allocationlimited
 local allpatterns=patterns
 local targetGoal=0
 local memo,searchnodes={},0
 local function Search(first,space,total)
  nodes=nodes+1;searchnodes=searchnodes+1
  if searchnodes>nodebudget then limited=true;return end
  if nodes%16==0 and yieldfn then yieldfn() end
  if total==targetGoal then if space==0 then Remember(total) end;return end
  if space==0 or total+space*patterns[1].n<targetGoal then return end
  if #(proposals[targetGoal] or {})>=4 then return end
  local tokens={};for i,n in ipairs(remaining) do tokens[i]=n end
  local key=first..';'..space..';'..table.concat(tokens,',')
  if memo[key] then return end;memo[key]=true
  for index=first,#patterns do local p=patterns[index]
   if total+space*p.n<targetGoal then break end
   local repeatmax=space
   for i,n in ipairs(p.counts) do if n>0 then repeatmax=math.min(repeatmax,math.floor(remaining[i]/n)) end end
   for repeatn=repeatmax,1,-1 do
    for i,n in ipairs(p.counts) do remaining[i]=remaining[i]-n*repeatn;used[i]=used[i]+n*repeatn end
    for _=1,repeatn do bins[#bins+1]=p end
    Search(index+1,space-repeatn,total+p.n*repeatn)
    for _=1,repeatn do bins[#bins]=nil end
    for i,n in ipairs(p.counts) do remaining[i]=remaining[i]+n*repeatn;used[i]=used[i]-n*repeatn end
    if #(proposals[targetGoal] or {})>=4 or searchnodes>nodebudget then return end
   end
  end
 end
 local attempts=0
 for goal=globalupper,math.max(1,bestn),-1 do
  if warmLimit and worktotal>=warmLimit then break end
  effort=0;if refined then goal_layouts=0;attempts=0 end
  local accepted=0
  for _,allocation in ipairs(allocations[goal] or {}) do
   attempts=attempts+1;if attempts>72 then limited=true;break end
   local catalog={};for _,p in ipairs(allpatterns) do local ok=true;for i,n in ipairs(p.counts) do if n>allocation[i] then ok=false;break end end;if ok then catalog[#catalog+1]=p end end
   local eligible=true
   if refined then
    eligible=false;patterns=catalog
    if #patterns>0 then
     for occupied=math.ceil(goal/patterns[1].n),math.min(#tiles,math.floor(goal/patterns[#patterns].n)) do
      remaining={};used={};for i,n in ipairs(allocation) do remaining[i]=n;used[i]=0 end
      targetGoal=goal;memo={};searchnodes=0;proposals[goal]={};bins={}
      Search(1,occupied,0)
      if #proposals[goal]>0 or searchnodes>nodebudget then eligible=true;break end
     end
    end
   end
   if eligible then
   local direct
   local fouronly=true;for _,n in ipairs(allocation) do if n>0 and n~=4 then fouronly=false;break end end
   if refined and not fouronly then
    for index,proposal in ipairs(proposals[goal] or {}) do
     if index>2 then break end
     bins=proposal;used={};for i=1,#crops do used[i]=0 end
     for _,p in ipairs(bins) do for i,n in ipairs(p.counts) do used[i]=used[i]+n end end
     Construct(goal)
     if bestn==goal then break end
    end
   end
   if bestn==goal then direct=best end
   if not direct and (refined or goal>#tiles*8) then
    for offset=0,#crops-1 do direct=FamilyField(allocation,goal,catalog,offset);if direct or effort>800000 then break end end
    if direct then
     local board=direct;local m=Layout.Metrics(board,geometry);local details={before=m,after=m,trials=0,moves=0,passes=0,limited=false}
     if goal>bestn or goal==bestn and Layout.Better(details.after,bestmetrics) then best,bestn,bestmetrics,arrangement=board,goal,details.after,details end
     accepted=accepted+1
    end
   end
   for _,ceiling in ipairs({9,8,7,6,5,4,3,2}) do if ceiling*#tiles>=goal and not direct then
    remaining={};used={};for i,n in ipairs(allocation) do remaining[i]=n;used[i]=0 end
    patterns={}
    for _,p in ipairs(allpatterns) do
     local ok=p.n<=ceiling;for i,n in ipairs(p.counts) do if n>remaining[i] then ok=false;break end end
     if ok then patterns[#patterns+1]=p end
    end
    if #patterns>0 then
     local low,high=math.ceil(goal/patterns[1].n),math.min(#tiles,math.floor(goal/patterns[#patterns].n))
     for step=0,high-low do
      local occupied=goal>=#tiles*6 and high-step or low+step
      targetGoal=goal;memo={};searchnodes=0;proposals[goal]={};bins={}
      Search(1,occupied,0)
      for _,proposal in ipairs(proposals[goal]) do
       bins=proposal;for i in ipairs(used) do used[i]=0 end
       for _,p in ipairs(bins) do for i,n in ipairs(p.counts) do used[i]=used[i]+n end end
       Construct(goal)
       if bestn==goal then accepted=accepted+1 end
       if accepted>=4 or LayoutLimit() or effort>800000 then break end
      end
      if bestn==goal or LayoutLimit() or effort>800000 then break end
     end
    end
    if accepted>=4 or LayoutLimit() or effort>800000 then break end
   end end
   if not refined and bestn<goal and goal<=#tiles*8 then
    for offset=0,#crops-1 do direct=FamilyField(allocation,goal,catalog,offset);if direct or effort>800000 then break end end
    if direct then
     local board=direct;local m=Layout.Metrics(board,geometry);local details={before=m,after=m,trials=0,moves=0,passes=0,limited=false}
     if goal>bestn or goal==bestn and Layout.Better(details.after,bestmetrics) then best,bestn,bestmetrics,arrangement=board,goal,details.after,details end
    end
   end
   if accepted>=4 or direct or LayoutLimit() or effort>800000 then break end
   end
  end
  if bestn==goal or attempts>72 or LayoutLimit() or worktotal>8000000 then break end
 end
 return best,{upper=upper,total=bestn,nodes=nodes,layouts=layouts,inventory_total=globalupper,allocation_nodes=allocationnodes,effort=worktotal,limited=limited,arrangement=arrangement,mode=refined and 'balanced-tile-packing-refined' or 'balanced-tile-packing'}
end
return M
