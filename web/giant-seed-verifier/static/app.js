'use strict';
// 输入、绘图和导出；播种规划仅由 /api/jobs 调用 Mod 原始 Lua 执行。
const $=id=>document.getElementById(id), NS='http://www.w3.org/2000/svg';
const seasons={autumn:'秋天',winter:'冬天',spring:'春天',summer:'夏天'};
const terrainStyles={
 autumn:{soil:'#8d7350',empty:'#433b2d',border:'#d3b582',pit:'#655035',pitStroke:'#c2a474',label:'#f0d7aa',filter:'sepia(.65) saturate(.9) brightness(.9)',shade:'#30251966'},
 winter:{soil:'#c6d1cd',empty:'#6b7777',border:'#eef4e8',pit:'#73817b',pitStroke:'#e0e9da',label:'#f2f6eb',filter:'grayscale(1) brightness(1.9)',shade:'#52687855'},
 spring:{soil:'#718352',empty:'#354531',border:'#c4d39a',pit:'#405431',pitStroke:'#a9bb7a',label:'#e4edc6',filter:'sepia(.25) hue-rotate(25deg) saturate(1.15) brightness(1.05)',shade:'#20351e66'},
 summer:{soil:'#ad9254',empty:'#605237',border:'#e9ce8b',pit:'#796236',pitStroke:'#d7b979',label:'#fff0bf',filter:'sepia(.9) saturate(1.05) brightness(1.25)',shade:'#4e35195c'}
};
const colors=['#db9e65','#e1c967','#b9a07c','#d78974','#9db279','#bb9caf','#dda46d','#9bb38d','#d4a1ad','#a8b97d','#d8ceb0','#c6b1c5','#d99b7c','#c7a0a3'];
let meta,presets=[],scene={strategy:'GIANT_TEMPLATE',season:'autumn',width:2,height:2,tiles:[[0,0],[1,0],[0,1],[1,1]],start:[0,0],seeds:{tomato:40,potato:40}},result=null,mode='',focusCrop=null,selected=null,zoom=1,job=null,generation=0,drag=null;
const crop=k=>meta?.crops.find(c=>c.id===k),key=(x,z)=>`${x},${z}`,has=(x,z)=>scene.tiles.some(t=>t[0]===x&&t[1]===z),totalSeeds=()=>Object.values(scene.seeds).reduce((a,b)=>a+b,0);
const el=(tag,attrs={},text)=>{const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e;};
function message(text=''){ $('message').hidden=!text;$('message').textContent=text; }
async function api(path,options={}){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);try{const r=await fetch(path,{...options,signal:controller.signal}),v=await r.json();if(!r.ok)throw Error(v.error||'请求失败');return v;}catch(e){if(e.name==='AbortError')throw Error('请求超时，请重试连接');throw e;}finally{clearTimeout(timer);}}
function status(text,detail='',kind='neutral'){$('plan-status').textContent=text;$('plan-status').className='status '+kind;$('status-detail').textContent=detail;}
function persist(){try{localStorage.setItem('tractor-native-scene-v1',JSON.stringify(scene));}catch{}}
function setMode(next){mode=mode===next?'':next;$('edit-button').classList.toggle('active',mode==='edit');$('start-button').classList.toggle('active',mode==='start');$('map-stage').classList.toggle('editing',!!mode);$('edit-tip').textContent=mode==='edit'?'点击或拖动地皮，添加或移除农田。':mode==='start'?'点击已有农田设置起点；Mod只扫描与起点连通的区域。':'每块地皮为3×3坑。可点击编辑不规则范围。';draw();}
function invalidate(){generation++;if(job){fetch('/api/jobs/'+job,{method:'DELETE'}).catch(()=>{});job=null;}busy(false);result=null;selected=null;focusCrop=null;message();status('参数已修改','点击生成以运行当前 Mod');$('export').disabled=true;['stat-planted','stat-seeds','stat-holes','stat-family'].forEach(id=>$(id).textContent='—');$('stat-family').classList.remove('pass');$('stat-bound').textContent='等待生成方案';$('stat-tiles').textContent='所选农田范围内';$('checks-badge').textContent='';$('validation-line').hidden=true;$('template-modules').hidden=true;usage();inspect();refreshCounts();persist();draw();}
function refreshCounts(){$('seed-count').textContent=totalSeeds()+' 颗库存';$('farm-count').textContent=scene.tiles.length+' 块 · '+scene.tiles.length*9+' 坑';}
function refreshStrategyLimit(){$('strategy-limit').textContent=scene.strategy==='GIANT_TEMPLATE'?'模版：不设固定地皮上限':'最优：最多64块连通地皮';}
function renderControls(){
 refreshStrategyLimit();
 $('strategy').value=scene.strategy;
 const auto=document.createElement('option');auto.value='';auto.textContent='自动整块选配';
 $('template-id').replaceChildren(auto,...(meta.templates||[]).map(t=>{const o=document.createElement('option');o.value=t.id;o.textContent=`${t.id} · ${t.total}株`;return o;}));
 $('template-id').value=scene.template_id||'';$('template-id').disabled=scene.strategy!=='GIANT_TEMPLATE';
 $('width').value=scene.width;$('height').value=scene.height;
 $('seasons').replaceChildren(...Object.entries(seasons).map(([id,name])=>{const b=document.createElement('button');b.className=id===scene.season?'active':'';b.innerHTML=`<img src="/assets/seasons/${id}_symbol.png" alt="">${name}`;b.onclick=()=>{scene.season=id;invalidate();renderControls();};return b;}));
 $('seeds').replaceChildren(...meta.crops.map(c=>{const row=document.createElement('label'),good=c.seasons.includes(scene.season);row.className='seed-row'+(good?'':' out-season');row.title=c.seasons.map(s=>seasons[s]).join('、')+'适宜生长';row.innerHTML=`<img src="/assets/crops/${c.id}.png" alt=""><span class="seed-name">${c.name}${good?'':'<span class="off">非当季</span>'}</span><input type="number" min="0" max="9999" value="${scene.seeds[c.id]||0}" aria-label="${c.name}种子数量">`;const input=row.querySelector('input');input.addEventListener('focus',()=>input.select());input.addEventListener('click',()=>input.select());input.addEventListener('blur',()=>{if(input.value===''){input.value='0';scene.seeds[c.id]=0;invalidate();}});input.addEventListener('input',e=>{if(e.target.value===''){e.target.setCustomValidity('');scene.seeds[c.id]=0;invalidate();return;}const n=Number(e.target.value);if(!Number.isInteger(n)||n<0||n>9999){e.target.setCustomValidity('请输入0至9999的整数');return;}e.target.setCustomValidity('');scene.seeds[c.id]=n;invalidate();});return row;}));refreshCounts();
}
function loadScene(data){
 if(!data||!seasons[data.season]||!Number.isSafeInteger(data.width)||!Number.isSafeInteger(data.height)||data.width<1||data.height<1||!Array.isArray(data.tiles)||!data.tiles.length||typeof data.seeds!=='object'||!data.seeds)throw Error('请导入本页保存的场景或完整结果 JSON。');
 const seen=new Set();for(const p of data.tiles){if(!Array.isArray(p)||p.length!==2||p.some(n=>!Number.isInteger(n))||p[0]<0||p[0]>=data.width||p[1]<0||p[1]>=data.height||seen.has(key(...p)))throw Error('场景地皮坐标无效。');seen.add(key(...p));}
 if(!Array.isArray(data.start)||!seen.has(key(...data.start)))throw Error('场景起点无效。');
 for(const [k,n] of Object.entries(data.seeds))if((!crop(k)&&k!=='randomseed')||!Number.isInteger(n)||n<0||n>9999)throw Error('场景种子库存无效。');
 if(data.strategy!==undefined&&!['GIANT_TEMPLATE','GIANT'].includes(data.strategy))throw Error('播种策略无效。');
 scene={...structuredClone(data),strategy:data.strategy||'GIANT'};zoom=1;mode='';invalidate();renderControls();setMode('');
}
function shape(type){const w=scene.width,h=scene.height;scene.tiles=[];for(let z=0;z<h;z++)for(let x=0;x<w;x++){let yes=type==='rectangle'||type==='L'&&(x===0||z===h-1)||type==='T'&&(z===0||x===Math.floor(w/2))||type==='ring'&&(x===0||z===0||x===w-1||z===h-1)||type==='U'&&(x===0||x===w-1||z===h-1);if(yes)scene.tiles.push([x,z]);}scene.start=scene.tiles[0]||[0,0];invalidate();}
function tileEdit(x,z,value){const exists=has(x,z);if(exists===value)return;if(value)scene.tiles.push([x,z]);else scene.tiles=scene.tiles.filter(t=>t[0]!==x||t[1]!==z);if(!has(...scene.start))scene.start=scene.tiles[0]||[0,0];invalidate();}
function draw(){
 const svg=$('map'),stage=$('map-stage'),pad=18,T=104,terrain=terrainStyles[scene.season];
 // 浏览时只适应实际农田的外接矩形；编辑时展示完整可编辑网格。
 const tiles=mode==='edit'||!scene.tiles.length?[[0,0],[scene.width-1,scene.height-1]]:scene.tiles;
 const minX=Math.min(...tiles.map(t=>t[0])),maxX=Math.max(...tiles.map(t=>t[0]));
 const minZ=Math.min(...tiles.map(t=>t[1])),maxZ=Math.max(...tiles.map(t=>t[1]));
 const W=(maxX-minX+1)*T+pad+4,H=(maxZ-minZ+1)*T+pad+4;
 const fit=Math.min(Math.max(1,stage.clientWidth-12)/W,Math.max(1,stage.clientHeight-12)/H);
 svg.setAttribute('viewBox',`${minX*T} ${minZ*T} ${W} ${H}`);svg.style.width=W*fit*zoom+'px';svg.style.height=H*fit*zoom+'px';svg.replaceChildren();
 stage.dataset.season=scene.season;stage.style.setProperty('--turf-filter',terrain.filter);stage.style.setProperty('--ground-shade',terrain.shade);stage.style.setProperty('--ground-color',terrain.soil);
 const defs=el('defs'),pattern=el('pattern',{id:'turf',patternUnits:'userSpaceOnUse',width:T,height:T});
 pattern.append(el('image',{href:'/assets/turf.png',width:T,height:T,opacity:scene.season==='winter'?.38:.7,style:`filter:${terrain.filter}`}));
 if(scene.season==='winter'){
  pattern.append(el('path',{d:'M0 0H104V14Q80 9 64 17T25 13T0 19Z M0 88Q18 82 39 90T79 87T104 90V104H0Z',fill:'#edf3ee',opacity:.8}));
  for(const [cx,cy,r] of [[15,31,4],[81,68,6],[35,76,3],[72,35,3]])pattern.append(el('ellipse',{cx,cy,rx:r*1.6,ry:r,fill:'#e9f0ec',opacity:.65}));
 }else if(scene.season==='summer')pattern.append(el('path',{d:'M8 43l9 5 4-7m-4 7-2 10 M68 83l6-8 10 3m-10-3-3-9',fill:'none',stroke:'#695133','stroke-width':.8,opacity:.45}));
 defs.append(pattern);svg.append(defs);
 const scanned=new Set((result?.tiles||[]).map(t=>key(t.x/4,t.z/4)));
 for(let x=minX;x<=maxX;x++)svg.append(el('text',{x:pad+(x+.5)*T,y:minZ*T+12,'text-anchor':'middle',class:'tile-label',fill:terrain.label},column(x)));
 for(let z=minZ;z<=maxZ;z++)svg.append(el('text',{x:minX*T+9,y:pad+(z+.5)*T+3,'text-anchor':'middle',class:'tile-label',fill:terrain.label},z+1));
 for(let z=minZ;z<=maxZ;z++)for(let x=minX;x<=maxX;x++){
  const yes=has(x,z),unused=result&&yes&&!scanned.has(key(x,z));const g=el('g',{'data-tile':key(x,z),class:'field-tile',role:mode?'button':'presentation',tabindex:mode?0:-1,'aria-label':`地皮 ${column(x)}${z+1}，${yes?'农田':'空白'}`});
  g.append(el('rect',{x:pad+x*T+1,y:pad+z*T+1,width:T-2,height:T-2,rx:5,fill:yes?(unused?terrain.empty:terrain.soil):terrain.empty,stroke:terrain.border,'stroke-dasharray':yes?'':'4 4'}));
  if(yes){g.append(el('rect',{x:pad+x*T+1,y:pad+z*T+1,width:T-2,height:T-2,rx:5,fill:'url(#turf)','pointer-events':'none'}));for(let row=0;row<3;row++)for(let col=0;col<3;col++)g.append(el('circle',{cx:pad+(x+(col+.5)/3)*T,cy:pad+(z+(row+.5)/3)*T,r:3.3,fill:unused?terrain.empty:terrain.pit,stroke:terrain.pitStroke,'stroke-width':.6,'stroke-dasharray':'2 1','pointer-events':'none'}));}
  if(yes&&scene.start[0]===x&&scene.start[1]===z){g.append(el('path',{d:`M${pad+x*T+6},${pad+z*T+16}v-11l9,2l-9,4`,fill:'#ead39b',stroke:'#ead39b','stroke-width':1.2,'pointer-events':'none'}));}
  if(unused)g.append(el('text',{x:pad+(x+.5)*T,y:pad+(z+.5)*T+3,'text-anchor':'middle',fill:'#959b84','font-size':10,'pointer-events':'none'},'未连通'));
  svg.append(g);
 }
 const pointXY=p=>[pad+(p.x/4+.5)*T,pad+(p.z/4+.5)*T];
 if(result?.slots){
  const selectedPoint=selected!==null?result.slots[selected]:null;
  if(selectedPoint?.crop){const [x,y]=pointXY(selectedPoint);svg.append(el('circle',{cx:x,cy:y,r:selectedPoint.family_radius/4*T,fill:'#f4dc9e18',stroke:'#e8d291','stroke-width':1.2,'stroke-dasharray':'5 4','pointer-events':'none'}));}
  result.slots.forEach((p,i)=>{if(!p.crop)return;const c=crop(p.crop),[x,y]=pointXY(p),color=colors[meta.crops.findIndex(c=>c.id===p.crop)],dim=focusCrop&&p.crop!==focusCrop;
   const display=cropDisplay(p,result,scene,meta);
   const near=selectedPoint?.crop===p.crop&&Math.hypot(p.x-selectedPoint.x,p.z-selectedPoint.z)<=selectedPoint.family_radius+1e-8;
   const g=el('g',{class:'crop-point '+(display.giant?'giant-crop':'mature-crop'),'data-harvest':display.giant?'giant':'mature',transform:`translate(${x},${y})`,opacity:dim?.23:1,tabindex:mode?-1:0,role:'button','aria-label':`${c.name}，${display.label}，${p.family}株同族，地皮${column(p.cx/4)}${p.cz/4+1}`,'data-point':i,'pointer-events':mode?'none':'auto'});
   g.append(el('circle',{r:16,fill:color,opacity:.5,class:'plant-disc',stroke:selected===i?'#fff1b7':near?'#e8d291':display.giant?'#d7bb79':'#b9b2a0','stroke-width':selected===i?2.4:near?1.5:1}));
   g.append(el('image',{href:display.icon,x:-15.5,y:-15.5,width:31,height:31,'pointer-events':'none'}));g.append(el('title',{},`${c.name} · ${display.label}${display.giant?'（全程养护达标时）':'：'+display.reasons.join('、')} · 同族 ${p.family}/${p.family_min}（含自身）`));svg.append(g);
  });
 }
 $('map-hint').textContent=mode==='edit'?'点击或拖动：添加 / 移除地皮':mode==='start'?'点击农田：设置 Mod 扫描起点':'点击作物，查看同族距离与数量';
}
function column(x){let s='';for(x++;x>0;x=Math.floor((x-1)/26))s=String.fromCharCode(65+(x-1)%26)+s;return s;}
function inspect(){
 if(selected===null||!result?.slots[selected]?.crop){$('inspect').innerHTML='<div class="inspect-icon">⌁</div><p>选择一株作物<br><span>查看巨大化条件、同族范围和所在坑位</span></p>';return;}
 const p=result.slots[selected],display=cropDisplay(p,result,scene,meta),row=Math.round((p.z-p.cz)/meta.grid_spacing)+2,col=Math.round((p.x-p.cx)/meta.grid_spacing)+2;
 $('inspect').innerHTML=`<img src="${display.icon}" alt="${display.label}"><div><strong>${crop(p.crop).name}</strong><span class="harvest-state">${display.label}</span><small>地皮 ${column(p.cx/4)}${p.cz/4+1} · 第${row}行第${col}列 · 同族 ${p.family}/${p.family_min} 株</small><div class="family-note">${display.giant?'应季 ✓ 同族 ✓ 养分互补 ✓ 密度 ✓':display.reasons.join(' · ')}</div><small>半径 ${p.family_radius} · 含自身 · 坐标 ${p.x.toFixed(3)}, ${p.z.toFixed(3)}</small></div>`;
}
function usage(){
 if(!meta?.crops)return;
 $('usage').replaceChildren(...meta.crops.filter(c=>(scene.seeds[c.id]||0)>0).map(c=>{
  const b=document.createElement('button'),stock=scene.seeds[c.id]||0,used=result?(result.used[c.id]||0):null,left=used===null?null:stock-used;
  b.className='usage-chip'+(focusCrop===c.id?' active':'')+(used===0?' unused':'');
  b.title=`${c.name}：${used===null?'等待生成布局':`使用 ${used} / 库存 ${stock}，剩余 ${left}`}`;
  b.setAttribute('aria-label',b.title);b.setAttribute('aria-pressed',focusCrop===c.id);
  b.innerHTML=`<img src="/assets/crops/${c.id}.png" alt=""><span><strong>${c.name}</strong><small><span>用 <b>${used??'—'}</b></span><span>余 <b>${left??'—'}</b></span></small></span>`;
  b.onclick=()=>{focusCrop=focusCrop===c.id?null:c.id;selected=null;inspect();usage();draw();};return b;
 }));
 if(scene.seeds.randomseed){const s=document.createElement('span');s.className='muted';s.textContent=`普通种子 ${scene.seeds.randomseed} 颗，Mod不参与配种`;$('usage').append(s);}
}

function showResult(r){const modulePanel=$('template-modules');modulePanel.hidden=r.strategy!=='GIANT_TEMPLATE'||!r.count;modulePanel.open=false;const summary=document.createElement('summary'),body=document.createElement('div');summary.textContent=`已放置 ${(r.template_modules||[]).length} 个完整模版 · 展开查看编号和位置`;body.className='module-list';modulePanel.replaceChildren(summary,body);modulePanel.ontoggle=()=>{if(modulePanel.open&&!body.textContent)body.textContent=(r.template_modules||[]).map(m=>`${m.id} · 地皮(${m.origin.x/4},${m.origin.z/4}) · ${m.symmetry>=4?'镜像＋':''}旋转${m.symmetry%4*90}°`).join('；');};result=r;meta={...meta,...r.source};$('source-button').textContent='v'+meta.version;selected=null;focusCrop=null;$('export').disabled=false;$('stat-planted').textContent=r.count;$('stat-bound').textContent=r.strategy==='GIANT_TEMPLATE'?(r.count?'固定模版布局':'未生成方案'):(r.optimal?'已证明最大合法播种量':r.count?'合法配比安全上界 '+r.upper:'未生成方案');$('stat-seeds').textContent=Object.values(r.remaining).reduce((a,b)=>a+b,0);$('stat-holes').textContent=scene.tiles.length*9-r.count;$('stat-tiles').textContent=`扫描 ${r.tiles.length} / 所选 ${scene.tiles.length} 块地皮`;$('stat-family').textContent=r.count?`${r.checks.family_passed}/${r.checks.family_total}`:'—';$('stat-family').classList.add('pass');$('checks-badge').textContent=r.valid?'Mod校验通过':'';$('validation-line').hidden=!r.count;$('validation-line').textContent=r.count?`✓ Mod自检  ✓ 逐格养分互补  ✓ 同族距离  ✓ 坑距  ✓ 应季  ✓ 库存   ·   同族分散 ${r.layout.fragmentation} · 同族距离 ${Number(r.layout.family_distance).toFixed(1)} · 整齐评分 ${Number(r.layout.tidy).toFixed(1)}`:'';status(r.count?'布局已生成':'未生成方案',`${r.count?Object.keys(r.used).length+'种作物 · ':''}${(r.elapsed_ms/1000).toFixed(2)} 秒 · ${r.strategy==='GIANT_TEMPLATE'?`模版准备 ${(Number(r.timings?.template_prepare_ms||0)/1000).toFixed(3)} 秒 · 选配回填 ${(Number(r.timings?.template_select_ms||0)/1000).toFixed(3)} 秒 · 校验评分 ${(Number(r.timings?.arrangement_ms||0)/1000).toFixed(3)} 秒`:`最大数量 ${(Number(r.timings?.quantity_ms||0)/1000).toFixed(3)} 秒 · 紧凑整齐 ${(Number(r.timings?.arrangement_ms||0)/1000).toFixed(3)} 秒`}（CPU）`,r.count?'':'warn');let note=r.message||'';if(r.count&&r.strategy==='GIANT_TEMPLATE')note='按固定模版生成，未运行全田逐坑搜索。';else if(r.count&&!r.optimal)note=`已通过配比校验；安全数量上界为 ${r.upper}，本次尚未证明数量最优。`;if(r.tiles.length&&r.tiles.length<scene.tiles.length)note+=(note?' ':'')+'仅扫描与起点连通的农田，断开的区域不会播种。';message(note);usage();inspect();draw();persist();}
function clearInspection(){selected=null;focusCrop=null;usage();inspect();draw();}
function selectPoint(index){if(selected===index){clearInspection();return;}selected=index;focusCrop=result.slots[index].crop;usage();inspect();draw();}
function busy(yes){$('run').disabled=yes;$('run').firstElementChild.textContent=yes?'正在运行 Mod 算法…':'生成播种布局';$('cancel').hidden=!yes;}
async function generate(){if(mode)setMode(mode);if(!scene.tiles.length){message('请先添加至少一块农田。');return;}if($('seeds').querySelector('input:invalid')){$('seeds').querySelector('input:invalid').reportValidity();return;}const token=++generation;busy(true);message();status('正在计算','读取 Mod 原始 Lua','working');try{const created=await api('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(scene)});if(token!==generation){fetch('/api/jobs/'+created.id,{method:'DELETE'});return;}job=created.id;while(token===generation){const state=await api('/api/jobs/'+job);if(token!==generation)return;if(state.status==='complete'){showResult(state.result);break;}if(state.status==='error')throw Error(state.error);if(state.status==='cancelled'){status('已取消','调整后可重新生成');break;}status('正在计算',`${state.phase} · ${(state.elapsed_ms/1000).toFixed(1)} 秒`,'working');await new Promise(resolve=>setTimeout(resolve,150));}}catch(e){if(token===generation){message(e.message);status('生成失败','检查输入或查看错误详情','warn');}}finally{if(token===generation){job=null;busy(false);}}}
function sourceDialog(){const s=result?.source||meta;$('source-summary').textContent=`Mod ${s.version} · ${s.runtime} · 本机游戏模块${s.installed_match?'与当前源码一致':'与当前源码不一致或未安装'} · 指纹 ${s.fingerprint}`;$('source-files').replaceChildren(...s.files.map(f=>{const row=document.createElement('div');row.className='source-file';const name=document.createElement('span');name.textContent=f.path;const size=document.createElement('span');size.textContent=(f.bytes/1024).toFixed(1)+' KB';const hash=document.createElement('code');hash.textContent=f.sha256;hash.style.gridColumn='1/-1';row.append(name,size,hash);return row;}));$('source-dialog').showModal();}
function download(data,suffix){const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`tractor-${scene.season}-${suffix}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('export-dialog').close();}
function planner(){const tiles={};for(const [x,z] of scene.tiles)tiles[key(x,z)]={};for(const p of result.slots){if(!p.crop)continue;const col=Math.round((p.x-p.cx)/meta.grid_spacing)+1,row=Math.round((p.z-p.cz)/meta.grid_spacing)+1;tiles[key(p.cx/4,p.cz/4)][key(col,row)]=({tomato:'tomaRoot',dragonfruit:'dragonFruit'})[p.crop]||p.crop;}return{width:scene.width,height:scene.height,season:scene.season,tiles};}
$('map').addEventListener('pointerdown',e=>{const tile=e.target.closest('[data-tile]'),point=e.target.closest('[data-point]');if(mode&&tile){const [x,z]=tile.dataset.tile.split(',').map(Number);e.preventDefault();if(mode==='start'){if(has(x,z)){scene.start=[x,z];invalidate();}return;}drag={add:!has(x,z)};tileEdit(x,z,drag.add);}else if(point){selectPoint(Number(point.dataset.point));}else if(!mode){clearInspection();}});
$('map').addEventListener('pointermove',e=>{if(!drag)return;const target=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-tile]');if(target){const [x,z]=target.dataset.tile.split(',').map(Number);tileEdit(x,z,drag.add);}});window.addEventListener('pointerup',()=>drag=null);window.addEventListener('pointercancel',()=>drag=null);
$('map').addEventListener('keydown',e=>{const tile=e.target.closest('[data-tile]');if(mode&&tile&&['Enter',' '].includes(e.key)){e.preventDefault();const [x,z]=tile.dataset.tile.split(',').map(Number);if(mode==='edit')tileEdit(x,z,!has(x,z));else if(has(x,z)){scene.start=[x,z];invalidate();}return;}const p=e.target.closest('[data-point]');if(p&&['Enter',' '].includes(e.key)){e.preventDefault();selectPoint(Number(p.dataset.point));}});
window.addEventListener('keydown',e=>{if(e.key==='Escape'&&!mode)clearInspection();});
$('map-stage').addEventListener('pointerdown',e=>{if(e.target===$('map-stage')&&!mode)clearInspection();});
$('strategy').onchange=e=>{scene.strategy=e.target.value;scene.template_id=null;invalidate();renderControls();};
$('template-id').onchange=e=>{scene.template_id=e.target.value||null;invalidate();};
$('run').onclick=generate;$('cancel').onclick=()=>{generation++;if(job)fetch('/api/jobs/'+job,{method:'DELETE'}).catch(()=>{});job=null;busy(false);status('已取消','可以调整输入后重新生成');};
$('edit-button').onclick=()=>setMode('edit');$('start-button').onclick=()=>setMode('start');$('shapes').onclick=e=>{if(e.target.dataset.shape)shape(e.target.dataset.shape);};
for(const id of ['width','height']){const input=$(id);input.oninput=()=>{const n=Number(input.value);if(!Number.isSafeInteger(n)||n<1)return;scene[id]=n;shape('rectangle');zoom=1;draw();};input.onblur=()=>{input.value=scene[id];};}
$('clear-seeds').onclick=()=>{scene.seeds={};invalidate();renderControls();};$('season-seeds').onclick=()=>{scene.seeds=Object.fromEntries(meta.crops.filter(c=>c.seasons.includes(scene.season)).map(c=>[c.id,40]));invalidate();renderControls();};
$('zoom-in').onclick=()=>{zoom=Math.min(zoom*1.3,8);draw();};$('zoom-out').onclick=()=>{zoom=Math.max(zoom/1.3,.4);draw();};$('fit').onclick=()=>{zoom=1;draw();$('map-stage').scrollTo(0,0);};new ResizeObserver(()=>draw()).observe($('map-stage'));
$('source-button').onclick=sourceDialog;$('source-link').onclick=sourceDialog;$('close-dialog').onclick=()=>$('source-dialog').close();$('export').onclick=()=>$('export-dialog').showModal();$('close-export').onclick=()=>$('export-dialog').close();$('download-full').onclick=()=>download({format:'tractor-native-verifier/v1',...result},'result');$('download-scene').onclick=()=>download({format:'tractor-native-scene/v1',...scene},'scene');$('download-planner').onclick=()=>download(planner(),'planner');
$('import').onclick=()=>$('file').click();$('file').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{if(f.size>1000000)throw Error('文件过大。');const v=JSON.parse(await f.text());loadScene(v.input||v);status('场景已导入','点击生成，使用当前 Mod 重新计算');}catch(err){message('导入失败：'+err.message);}e.target.value='';};
$('example').onchange=e=>{if(e.target.value==='')return;loadScene(presets[Number(e.target.value)].scenario);e.target.value='';generate();};
let connected=false,connecting=false;
function connectionNote(text=''){$('connection-note').hidden=!text;$('connection-text').textContent=text;}
async function loadPresets(){
 try{
  presets=await api('/api/presets');
  const placeholder=document.createElement('option');placeholder.value='';placeholder.textContent='选择场景…';
  $('example').replaceChildren(placeholder,...presets.map((p,i)=>{const o=document.createElement('option');o.value=i;o.textContent=p.name;return o;}));
  $('example').disabled=false;
 }catch(e){$('example').disabled=true;connectionNote('预设场景加载失败，仍可手动配置和生成布局。');}
}
async function connect(){
 if(connecting)return;connecting=true;$('retry-connection').disabled=true;connectionNote();
 try{
  let embedded=null;try{embedded=JSON.parse($('bootstrap-meta')?.textContent||'null');}catch{}
  const source=connected?await api('/api/meta'):(embedded||await api('/api/meta'));
  if(source.verifier_schema!==4||!Array.isArray(source.crops)||!source.crops.length)throw Error('服务版本过旧，请重新双击启动器打开新服务。');
  meta=source;$('source-button').textContent='v'+meta.version;
  if(!connected){try{const saved=localStorage.getItem('tractor-native-scene-v1');if(saved)loadScene(JSON.parse(saved));}catch{}}
  renderControls();usage();draw();$('run').disabled=!$('cancel').hidden;
  const first=!connected;connected=true;
  // Optional examples must never block crop controls or layout generation.
  loadPresets();if(first)status('准备就绪','选择策略后点击生成播种布局');
 }catch(e){$('run').disabled=!connected||!$('cancel').hidden;connectionNote('连接失败：'+e.message);if(!connected)status('连接失败','请点击左侧重新连接','warn');}
 finally{connecting=false;$('retry-connection').disabled=false;}
}
$('retry-connection').onclick=connect;
connect();
