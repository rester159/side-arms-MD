// Exercise the generated page's controls without claiming browser audio playback.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const root=process.argv[2]||'.local/hucard-audio-review';
const html=fs.readFileSync(root+'/index.html','utf8');
class Element {
  constructor(){this.events={};this.dataset={}}
  addEventListener(name,fn,options={}){(this.events[name]??=[]).push({fn,once:options.once})}
  dispatch(name,event={}){const handlers=this.events[name]||[];this.events[name]=handlers.filter(h=>!h.once);handlers.forEach(h=>h.fn(event))}
  closest(){return this.section}
}
class Audio extends Element {
  constructor(){super();this.currentTime=0;this.duration=10;this.readyState=0;this.paused=true}
  play(){this.paused=false;this.dispatch('play');return Promise.resolve()}
  pause(){this.paused=true}
  load(){this.readyState=1;this.dispatch('loadedmetadata')}
}
const clips=[],buttons=[];
for(const sectionHtml of html.matchAll(/<section>([\s\S]*?)<\/section>/g)){
  const section={dataset:{},clips:[],querySelectorAll(){return this.clips}};
  for(const match of sectionHtml[1].matchAll(/<audio ([^>]+)>/g)){
    const clip=new Audio();clip.section=section;
    for(const attr of match[1].matchAll(/(data-[\w-]+|src)="([^"]+)"/g)){
      if(attr[1]==='src')clip.src=attr[2];else clip.dataset[attr[1].slice(5)]=attr[2];
    }
    for(const kind of ['original','matched'])assert(fs.existsSync(root+'/'+clip.dataset[kind]));
    section.clips.push(clip);clips.push(clip);
    const button=new Element();button.section=section;button.dataset.side=clip.dataset.side;buttons.push(button);
  }
}
assert.equal(clips.length,42);
const checkbox=new Element();checkbox.checked=true;
const document={querySelectorAll:s=>s==='audio'?clips:buttons,querySelector:()=>checkbox};
vm.runInNewContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],{document});
clips[0].play();clips[0].currentTime=3.25;buttons[1].dispatch('click');
assert(clips[0].paused&&!clips[1].paused);assert.equal(clips[1].currentTime,3.25);
clips[1].currentTime=4;buttons[1].dispatch('click');assert.equal(clips[1].currentTime,4);
checkbox.checked=false;checkbox.dispatch('change',{target:checkbox});
assert(clips.every(c=>c.src===c.dataset.original));assert.equal(clips[1].currentTime,4);
assert.equal(clips.filter(c=>!c.paused).length,1);
clips[2].play();assert(clips[1].paused&&!clips[2].paused);
checkbox.checked=true;checkbox.dispatch('change',{target:checkbox});
assert(clips.every(c=>c.src===c.dataset.matched));
console.log('PASS: 21 pairs, audio links, A/B position preservation, gain-mode switch, exclusive playback controls');
