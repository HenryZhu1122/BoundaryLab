import fs from 'node:fs/promises';
const ROOT='C:/Users/33943/Documents/ChatGPT/智绘芯生，AI赋能/boundarylab/artifacts/publicity';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
export class Recorder {
 constructor(tab,cdp){this.tab=tab;this.cdp=cdp;this.pointer={x:900,y:450};}
 async move(x,y){
  const old={...this.pointer};
  for(let i=1;i<=12;i++){
   await this.cdp.send('Input.dispatchMouseEvent',{type:'mouseMoved',x:old.x+(x-old.x)*i/12,y:old.y+(y-old.y)*i/12});
   await sleep(35);
  }
  this.pointer={x,y};
 }
 async scroll(y){
  await this.cdp.send('Runtime.evaluate',{expression:'window.scrollTo({top:'+Math.round(y)+',behavior:"smooth"})'});
  await sleep(750);
 }
 async clip(name,action,duration=0){
  const folder=ROOT+'/'+name;await fs.mkdir(folder,{recursive:true});
  const state={name,frames:[],started:Date.now(),source:'native-browser-screencast'};let active=true;let pumpError;
  let cursor=(await this.cdp.readEvents({methods:['Page.screencastFrame']})).cursor;
  await this.cdp.send('Page.startScreencast',{format:'jpeg',quality:90,maxWidth:3840,maxHeight:2160,everyNthFrame:1});
  const pump=(async()=>{
   try{
    while(active){
     const rr=await this.cdp.readEvents({afterSequence:cursor,methods:['Page.screencastFrame'],limit:100,timeoutMs:200});
     cursor=rr.cursor;
     await Promise.all(rr.events.map(e=>this.cdp.send('Page.screencastFrameAck',{sessionId:e.params.sessionId})));
     for(const e of rr.events){
      const file=String(state.frames.length).padStart(6,'0')+'.jpg';
      await fs.writeFile(folder+'/'+file,Buffer.from(e.params.data,'base64'));
      state.frames.push({file,received:(Date.now()-state.started)/1000,timestamp:e.params.metadata.timestamp});
     }
     await sleep(15);
    }
   }catch(e){pumpError=e;}
  })();
  try{await sleep(250);await action();await sleep(Math.max(100,duration*1000-(Date.now()-state.started)));}
  finally{active=false;await pump;await this.cdp.send('Page.stopScreencast');}
  if(pumpError)throw pumpError;
  state.duration=(Date.now()-state.started)/1000;
  await fs.writeFile(folder+'/frames.json',JSON.stringify(state));
  return {name,frames:state.frames.length,duration:state.duration};
 }
}
