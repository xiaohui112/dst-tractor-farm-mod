'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const canvasViewport=require('../static/canvas-viewport.js');
const tall={contentWidth:646,contentHeight:854,stageWidth:1000,stageHeight:550};
test('完整农田在两个方向均不超出可用区域，并保持比例',()=>{
 for(const [w,h] of [[646,854],[854,646],[126,126],[3350,126]]){
  const v=canvasViewport({...tall,contentWidth:w,contentHeight:h,view:'overview'});
  assert.ok(v.width<=988+1e-8);assert.ok(v.height<=538+1e-8);
  assert.ok(Math.abs(v.width/v.height-w/h)<1e-8);
  assert.ok(Math.abs(v.width-988)<1e-8||Math.abs(v.height-538)<1e-8);
 }
});
test('清晰查看使大田作物至少28像素，允许画布内平移',()=>{
 const v=canvasViewport(tall);
 assert.ok(v.scale*31>=28);assert.ok(v.height>550);
 assert.ok(v.scale>canvasViewport({...tall,view:'overview'}).scale);
});
test('小田不受固定放大上限影响',()=>{
 const v=canvasViewport({...tall,contentWidth:126,contentHeight:126,view:'overview'});
 assert.ok(v.scale>1.4);assert.equal(v.height,538);
});
test('编辑模式展示完整可编辑范围，避免清晰视图最小倍率影响',()=>{
 const v=canvasViewport({...tall,editing:true});
 assert.ok(v.height<=538);assert.equal(v.scale,v.fit);
});
test('手动缩放相对于当前视图生效',()=>{
 const initial=canvasViewport(tall),zoomed=canvasViewport({...tall,zoom:1.3});
 assert.equal(zoomed.scale,initial.scale*1.3);
 assert.equal(zoomed.width,initial.width*1.3);
});
