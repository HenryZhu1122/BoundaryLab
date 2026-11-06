const {chromium}=require('playwright');
const path=require('node:path');
const fs=require('node:fs');

(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const page=await browser.newPage({viewport:{width:1512,height:1120},deviceScaleFactor:1});
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  const studies=await (await fetch('http://127.0.0.1:8765/api/studies')).json();
  let selected;
  for(const row of studies){
    const s=await (await fetch('http://127.0.0.1:8765/api/studies/'+row.id)).json();
    if(s.status==='completed' && s.map && s.repair?.after_map){selected=s.id;break}
  }
  if(!selected)throw Error('No completed study with validation map');
  await page.goto('http://127.0.0.1:8765/?study='+selected,{waitUntil:'networkidle'});
  await page.locator('#domain-map .map-dot').first().waitFor();
  fs.mkdirSync('artifacts/qa',{recursive:true});
  await page.screenshot({path:'artifacts/qa/workbench-desktop.png',fullPage:true});
  await page.locator('#domain-map .map-dot').nth(4).click();
  await page.locator('#waveform svg').waitFor();
  await page.locator('#show-netlist').click();
  await page.locator('#netlist-dialog[open]').waitFor();
  if(!((await page.locator('#netlist-text').textContent()).includes('Bgm')))throw Error('Netlist not visible');
  await page.locator('#close-dialog').click();
  await page.locator('[data-map="after"]').click();
  await page.locator('[data-view="report"]').click();
  await page.locator('#report-content .report-table').first().waitFor();
  await page.screenshot({path:'artifacts/qa/report-desktop.png',fullPage:true});
  await page.locator('[data-view="about"]').click();
  await page.screenshot({path:'artifacts/qa/method-desktop.png',fullPage:true});
  await page.locator('[data-view="workbench"]').click();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'artifacts/qa/workbench-mobile.png',fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+2);
  if(overflow)throw Error('Mobile horizontal overflow');
  await browser.close();
  if(errors.length)throw Error(errors.join('\n'));
  console.log('UI QA passed: map selection, waveform, netlist, repair toggle, report, method, mobile layout.');
})().catch(e=>{console.error(e);process.exit(1)});
