'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const cropDisplay=require('../static/crop-display.js');
function fixture(count=9){
 const point={crop:'potato',cx:0,cz:0,family:4,family_min:4};
 return {point,result:{slots:Array.from({length:count},()=>({...point})),checks:{nutrient_tiles:[{x:0,z:0,balanced:true}]}},scene:{season:'autumn'},meta:{crops:[{id:'potato',seasons:['autumn','winter','spring']}],constants:{FARM_PANT_OVERCROWDING_MAX_PLANTS:10}}};
}
const display=f=>cropDisplay(f.point,f.result,f.scene,f.meta);
test('同族恰好4株且每地皮10株可显示巨大化原版图标',()=>{
 const f=fixture(10),d=display(f);
 assert.equal(d.giant,true);assert.equal(d.icon,'/assets/crops/potato_oversized.png');assert.deepEqual(d.reasons,[]);
});
test('同族仅3株使用成熟图标',()=>{
 const f=fixture();f.point.family=3;
 assert.equal(display(f).icon,'/assets/crops/potato.png');assert.deepEqual(display(f).reasons,['同族不足']);
});
test('同一地皮11株触发原版拥挤规则',()=>{
 const d=display(fixture(11));assert.equal(d.giant,false);assert.deepEqual(d.reasons,['密度检查未通过']);
});
test('相邻地皮的作物不计入本地皮拥挤数量，空坑也不计入',()=>{
 const f=fixture(10);f.result.slots.push({crop:null,cx:0,cz:0},...Array.from({length:10},()=>({crop:'tomato',cx:4,cz:0})));
 assert.equal(display(f).giant,true);
});
test('不应季作物显示成熟',()=>{
 const f=fixture();f.scene.season='summer';assert.equal(display(f).giant,false);assert.deepEqual(display(f).reasons,['非应季']);
});
test('养分不互补或未知时不标巨大化',()=>{
 for(const tiles of [[{x:0,z:0,balanced:false}],[{x:4,z:0,balanced:true}],[]]){
  const f=fixture();f.result.checks.nutrient_tiles=tiles;assert.equal(display(f).giant,false);
 }
});
test('缺失原版阈值、作物定义或检查数据时使用成熟图标',()=>{
 for(const change of [f=>delete f.meta.constants,f=>f.meta.crops=[],f=>delete f.result.checks,f=>delete f.point.family]){
  const f=fixture();change(f);assert.equal(display(f).icon,'/assets/crops/potato.png');
 }
});
test('多个条件不满足时保留全部原因',()=>{
 const f=fixture(11);f.point.family=1;f.scene.season='summer';f.result.checks.nutrient_tiles[0].balanced=false;
 assert.equal(display(f).reasons.length,4);
});
test('十四种作物均有成熟及巨大化PNG资源',()=>{
 const names=['carrot','corn','potato','tomato','asparagus','eggplant','pumpkin','watermelon','dragonfruit','durian','garlic','onion','pepper','pomegranate'];
 for(const name of names)for(const suffix of ['','_oversized']){
  const bytes=fs.readFileSync(path.join(__dirname,'../static/assets/crops',name+suffix+'.png'));
  assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
 }
});
