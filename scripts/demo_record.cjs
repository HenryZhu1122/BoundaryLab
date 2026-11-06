const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');

(async()=>{
  const id=JSON.parse(fs.readFileSync('artifacts/featured.json','utf8')).id;
  const study=JSON.parse(fs.readFileSync(`artifacts/studies/${id}/study.json`,'utf8'));
  const timeline=JSON.parse(fs.readFileSync('artifacts/demo/timeline.json','utf8'));
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const context=await browser.newContext({viewport:{width:1600,height:1000},deviceScaleFactor:1,
    recordVideo:{dir:'artifacts/demo/recording',size:{width:1600,height:1000}}});
  const page=await context.newPage();
  await page.goto('http://127.0.0.1:8765/?study='+id,{waitUntil:'networkidle'});
  await page.locator('#domain-map .map-dot').first().waitFor();
  await page.addStyleTag({content:'.view{padding-top:22px}.intro{margin-bottom:18px}.intro h1{font-size:28px}.metric{padding-top:10px;padding-bottom:8px}.domain-map{height:300px}.waveform{height:220px}.demo-watermark{position:fixed;bottom:10px;right:28px;font:11px Consolas,monospace;color:#b5c9c4;background:#0b171ee8;padding:5px 12px;border:1px solid #37554d;border-radius:4px;z-index:30;pointer-events:none}'});
  await page.evaluate(()=>{const d=document.createElement('div');d.className='demo-watermark';d.textContent='真实研究记录回放 · ngspice 47 · AI 配音';document.body.append(d)});
  const started=Date.now();
  const hold=async ms=>new Promise(r=>setTimeout(r,Math.max(0,ms)));
  for(const scene of timeline){
    const t=Date.now();
    if(scene.action==='overview'||scene.action==='setup')await page.evaluate(()=>window.scrollTo({top:0,behavior:'smooth'}));
    if(scene.action==='bandwidth'){
      const row=study.measurements.find(r=>r.distortion<.01&&!r.passed);
      await page.locator(`#domain-map [data-id="${row.id}"]`).click();
      await page.locator('.wave-panel').scrollIntoViewIfNeeded();
    }
    if(scene.action==='slew'){
      const row=study.measurements.find(r=>r.distortion>.03&&r.rail_occupancy<.01);
      await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
      await page.locator(`#domain-map [data-id="${row.id}"]`).click();
      await page.locator('.wave-panel').scrollIntoViewIfNeeded();
    }
    if(scene.action==='refuted'){
      const planIndex=study.events.findIndex(e=>e.prediction_match===false)-1;
      const seq=study.events[planIndex].seq;
      const detail=page.locator(`.event-plan[data-seq="${seq}"]`);
      await detail.locator('summary').click();
      await detail.scrollIntoViewIfNeeded();
    }
    if(scene.action==='revision'){
      await page.locator('[data-view="report"]').click();
      await page.locator('.report-block').filter({hasText:'修改方案与独立复测'}).scrollIntoViewIfNeeded();
    }
    if(scene.action==='comparison'){
      await page.locator('[data-view="workbench"]').click();
      await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
      await page.locator('[data-map="after"]').click();
    }
    if(scene.action==='report'){
      await page.locator('[data-view="report"]').click();
      await page.locator('.report-toolbar').scrollIntoViewIfNeeded();
    }
    if(scene.action==='closing'){
      await page.locator('[data-view="workbench"]').click();
      await page.evaluate(()=>window.scrollTo({top:0,behavior:'smooth'}));
    }
    console.log(scene.action,scene.duration.toFixed(1)+'s');
    await hold(scene.duration*1000-(Date.now()-t));
  }
  const video=page.video();
  await context.close();
  const videoPath=await video.path();
  fs.writeFileSync('artifacts/demo/video.json',JSON.stringify({path:videoPath,duration_s:(Date.now()-started)/1000},null,2));
  await browser.close();
  console.log('Recorded:',videoPath);
})().catch(e=>{console.error(e.message);process.exit(1)});
