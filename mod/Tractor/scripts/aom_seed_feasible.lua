-- 低开销可行性探测，只提供经过完整校验的上界见证；预算截断不构成不可行证明。
local M={}
function M.Find(crops,stock,tiles,slots,defs,target,yieldfn,budget)
 local Balance=require('aom_seed_balance')
 local Layout=require('aom_seed_layout')
 local patterns=Balance.Patterns(crops,stock,defs,yieldfn)
 local geometry=Layout.Geometry(tiles,slots,defs,yieldfn);geometry.balanced=true
 local K,N,T=#crops,#slots,#tiles
 local powers,single,all={}, {},0
 for c=0,K do powers[c]=2^c;single[2^c]=c;all=all+2^c end
 local function Has(mask,c)return mask%(powers[c]*2)>=powers[c] end
 local values={}
 local function Values(mask)
  if not values[mask] then local a={};for c=0,K do if Has(mask,c) then a[#a+1]=c end end;values[mask]=a end
  return values[mask]
 end
 local function Copy(a)local b={};for i,v in ipairs(a) do b[i]=v end;return b end
 local neighbors={}
 for c,k in ipairs(crops) do neighbors[c]={};for i=1,N do local a={};for _,q in ipairs(geometry.near[i]) do if q.d<=(defs[k].family_check_dist or 4)^2 then a[#a+1]=q.j end end;neighbors[c][i]=a end end
 local stopped=false;local nodes,work=0,0
 local function Step(n)
  work=work+(n or 1)
  if budget and work>budget then stopped=true;return false end
  return true
 end
 local function Propagate(domains,lists)
  local changed=true
  while changed do
   if stopped or not Step(N*K) then return false end
   if yieldfn then yieldfn() end
   changed=false
   local function Set(i,mask)
    if mask==0 then return false end
    if mask~=domains[i] then domains[i]=mask;changed=true end
    return true
   end
   local fixed,possible={},{};for c=0,K do fixed[c]=0;possible[c]=0 end
   for _,mask in ipairs(domains) do local c=single[mask];if c then fixed[c]=fixed[c]+1 end;for _,v in ipairs(Values(mask)) do possible[v]=possible[v]+1 end end
   for c=0,K do
    local cap=c==0 and N-target or stock[crops[c]]
    local minimum=c==0 and 0 or defs[crops[c]].family_min_count or 4
    if fixed[c]>cap or c==0 and possible[c]<cap or c>0 and fixed[c]>0 and possible[c]<minimum then return false end
    for i,mask in ipairs(domains) do if single[mask]==nil and Has(mask,c) then
     if fixed[c]==cap or c>0 and possible[c]<minimum then if not Set(i,mask-powers[c]) then return false end
     elseif c==0 and possible[c]==cap then if not Set(i,powers[c]) then return false end end
    end end
   end
   for c,k in ipairs(crops) do
    local minimum=defs[k].family_min_count or 4
    for i,mask in ipairs(domains) do if Has(mask,c) then
     local support={};if not Step(#neighbors[c][i]) then return false end
     for _,j in ipairs(neighbors[c][i]) do if Has(domains[j],c) then support[#support+1]=j end end
     if #support<minimum then if not Set(i,domains[i]-powers[c]) then return false end
     elseif single[domains[i]]==c and #support==minimum then for _,j in ipairs(support) do if not Set(j,powers[c]) then return false end end end
    end end
   end
   local mins,maxs={},{};local summin,summax=0,0
   for t=1,T do
    local counts,available={},{};for c=0,K do counts[c]=0;available[c]=0 end
    for i=(t-1)*9+1,t*9 do local mask=domains[i];local c=single[mask];if c then counts[c]=counts[c]+1 end;for _,v in ipairs(Values(mask)) do available[v]=available[v]+1 end end
    local allowed={};local lo,hi=9,0
    for _,p in ipairs(lists[t]) do
     if not Step(K) then return false end
     local ok=9-p.n>=counts[0] and 9-p.n<=available[0] and not (p.center_gap and not Has(domains[(t-1)*9+5],0))
     if ok then for c=1,K do if p.counts[c]<counts[c] or p.counts[c]>available[c] then ok=false;break end end end
     if ok then allowed[#allowed+1]=p;lo=math.min(lo,p.n);hi=math.max(hi,p.n) end
    end
    if #allowed==0 then return false end
    lists[t]=allowed;mins[t],maxs[t]=lo,hi;summin=summin+lo;summax=summax+hi
   end
   if target<summin or target>summax then return false end
   for t=1,T do
    local lo,hi=target-(summax-maxs[t]),target-(summin-mins[t]);local allowed={};local mincount,maxcount={},{};local gap=true
    for c=0,K do mincount[c]=9;maxcount[c]=0 end
    for _,p in ipairs(lists[t]) do if p.n>=lo and p.n<=hi then
     allowed[#allowed+1]=p;gap=gap and p.center_gap
     for c=0,K do local n=c==0 and 9-p.n or p.counts[c];mincount[c]=math.min(mincount[c],n);maxcount[c]=math.max(maxcount[c],n) end
    end end
    if #allowed==0 then return false end;lists[t]=allowed
    if gap and not Set((t-1)*9+5,Has(domains[(t-1)*9+5],0) and 1 or 0) then return false end
    for c=0,K do
     local assigned,candidates=0,0
     for i=(t-1)*9+1,t*9 do if single[domains[i]]==c then assigned=assigned+1 end;if Has(domains[i],c) then candidates=candidates+1 end end
     if assigned>maxcount[c] or candidates<mincount[c] then return false end
     for i=(t-1)*9+1,t*9 do local mask=domains[i];if Has(mask,c) then
      if assigned==maxcount[c] and single[mask]==nil then if not Set(i,mask-powers[c]) then return false end
      elseif candidates==mincount[c] then if not Set(i,powers[c]) then return false end end
     end end
    end
   end
  end
  return true
 end
 local initial,lists={},{}
 for i=1,N do initial[i]=target==N and all-1 or all end
 for t=1,T do local a=Copy(patterns);local zero={n=0,counts={}};for c=1,K do zero.counts[c]=0 end;a[#a+1]=zero;lists[t]=a end
 local function Search(domains,lists)
  nodes=nodes+1
  if not Propagate(domains,lists) then return nil end
  local chosen,rank=nil,math.huge
  for i,mask in ipairs(domains) do if not single[mask] then
   local score=#Values(mask)*10000+#lists[math.floor((i-1)/9)+1]*10+#geometry.near[i]
   if score<rank then chosen,rank=i,score end
  end end
  if not chosen then
   local board={};local n=0
   for i,mask in ipairs(domains) do local c=single[mask];board[i]=c>0 and crops[c] or false;if c>0 then n=n+1 end end
   if n==target and Layout.Valid(board,geometry) then return board end
   return nil
  end
  local used={};for c=1,K do used[c]=0 end;for _,mask in ipairs(domains) do local c=single[mask];if c and c>0 then used[c]=used[c]+1 end end
  local function Cost(c)
   if c==0 then return -1000 end
   local n=0;for _,j in ipairs(neighbors[c][chosen]) do if single[domains[j]]==c then n=n+1 end end
   return n*100+stock[crops[c]]-used[c]
  end
  local options=Copy(Values(domains[chosen]));table.sort(options,function(a,b)local x,y=Cost(a),Cost(b);return x~=y and x>y or x==y and a<b end)
  for _,c in ipairs(options) do
   if stopped then return nil end
   local child=Copy(domains);child[chosen]=powers[c]
   local board=Search(child,Copy(lists));if board then return board end
  end
  return nil
 end
 return Search(initial,lists)
end
return M
