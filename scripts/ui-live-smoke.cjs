const {chromium}=require('playwright');
(async()=>{
  const b=await chromium.launch({channel:'msedge',headless:true});
  const p=await b.newPage({viewport:{width:1440,height:1000}});
  const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.goto('http://127.0.0.1:8765/',{waitUntil:'networkidle'});
  await p.locator('#preset').selectOption('lowpass');
  await p.locator('#mode').selectOption('local');
  await p.locator('#budget').fill('4');
  await p.locator('.toggle-row').filter({has:p.locator('#build-map')}).click();
  await p.locator('.toggle-row').filter({has:p.locator('#auto-repair')}).click();
  await p.locator('#start').click();
  await p.waitForFunction(()=>document.querySelector('#status-title').textContent==='研究完成' &&
    document.querySelector('#metric-runs').textContent.startsWith('4') &&
    document.querySelector('#metric-runs-note').textContent.includes('非大模型'),null,{timeout:30000});
  const failures=await p.locator('.event.error').count();
  if(failures)throw Error('Study failed');
  const metric=await p.locator('#metric-runs').innerText();
  if(!metric.includes('4'))throw Error('Budget not respected');
  if(!(await p.locator('#metric-runs-note').textContent()).includes('非大模型'))throw Error('Mode incorrectly labeled');
  await b.close();if(errors.length)throw Error(errors.join('\n'));
  console.log('Live UI smoke passed: edit contract, select lowpass, create and complete a real local investigation.');
})().catch(e=>{console.error(e.message);process.exit(1)});
