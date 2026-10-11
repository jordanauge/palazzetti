// Run with: node tests/test_memory_html.cjs /path/to/chrome
const {spawn} = require("node:child_process");
const {mkdtempSync, rmSync} = require("node:fs");
const {tmpdir} = require("node:os");
const {join, resolve} = require("node:path");
const {pathToFileURL} = require("node:url");
const assert = require("node:assert/strict");

async function main() {
  if (!process.argv[2]) throw new Error("Pass the Chrome/Chromium executable path");
  const directory = mkdtempSync(join(tmpdir(), "plz-html-test-"));
  const browser = spawn(process.argv[2], [
    "--headless=new", "--remote-debugging-pipe", "--no-first-run",
    "--no-default-browser-check", "--disable-background-networking",
    "--user-data-dir="+directory, "about:blank",
  ], {stdio:["ignore","ignore","ignore","pipe","pipe"]});
  let id=0, buffer="";
  const pending=new Map();
  const waiters=new Map();
  const errors=[];
  const stopped=new Promise(done=>browser.once("exit",done));
  browser.on("error",error=>{for(const p of pending.values())p.reject(error);});
  browser.on("exit",()=>{for(const p of pending.values())p.reject(new Error("Browser exited"));});
  browser.stdio[4].on("data",chunk=>{
    buffer+=chunk.toString();
    let end;
    while((end=buffer.indexOf("\0"))>=0){
      const message=JSON.parse(buffer.slice(0,end));buffer=buffer.slice(end+1);
      if(message.id){
        const p=pending.get(message.id);
        if(p){pending.delete(message.id);message.error?p.reject(new Error(JSON.stringify(message.error))):p.resolve(message.result);}
      }else{
        if(message.method==="Runtime.exceptionThrown")errors.push(message.params);
        const key=message.sessionId+":"+message.method;
        const done=waiters.get(key);
        if(done){waiters.delete(key);done(message.params);}
      }
    }
  });
  function send(method,params={},sessionId){
    return new Promise((resolve,reject)=>{
      const request={id:++id,method,params};
      if(sessionId)request.sessionId=sessionId;
      pending.set(request.id,{resolve,reject});
      browser.stdio[3].write(JSON.stringify(request)+"\0");
    });
  }
  const timeout=setTimeout(()=>browser.kill(),45000);
  try{
    const {targetId}=await send("Target.createTarget",{url:"about:blank"});
    const {sessionId}=await send("Target.attachToTarget",{targetId,flatten:true});
    await send("Page.enable",{},sessionId);
    await send("Runtime.enable",{},sessionId);
    async function evaluate(expression){
      const result=await send("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true},sessionId);
      if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));
      return result.result.value;
    }
    async function open(memory){
      const loaded=new Promise(done=>waiters.set(sessionId+":Page.loadEventFired",done));
      await send("Page.navigate",{url:pathToFileURL(resolve("docs/memory-"+memory+".html")).href},sessionId);
      await loaded;
      assert.equal(await evaluate('document.querySelectorAll(".byte").length'),256);
      assert.equal(await evaluate('document.getElementById("error").hidden'),true);
    }
    await open("ram");
    assert.equal(await evaluate('document.getElementById("capture").options.length'),1);
    await evaluate(`const profileId=data.profiles[0].id;
      const observed={n:1,last:26,min:26,max:26,changes:0,distinct:1,rejected:0,
        first_t:1,last_t:1,points:[[1,26]],histogram:[[26,1]]};
      data.captures.push(
        {name:"test valid read",profile:profileId,first:1,last:1,bytes:{"ram:249":observed}},
        {name:"test rejected read",profile:profileId,first:1,last:1,bytes:{"ram:249":{n:0,rejected:25}}}
      );chooseProfile();`);
    assert.equal(await evaluate('document.getElementById("capture").options.length'),3);
    await evaluate('document.querySelector("[data-address=\'90\']").click()');
    assert.match(await evaluate('document.getElementById("details").textContent'),/refuted/);
    assert.match(await evaluate('document.getElementById("details").textContent'),/Running flags/);
    await evaluate('document.getElementById("capture").value="1";document.getElementById("capture").dispatchEvent(new Event("change"))');
    assert.equal(await evaluate('document.querySelector("[data-address=\'249\']").textContent'),"??");
    await evaluate('document.querySelector("[data-address=\'249\']").click()');
    assert.match(await evaluate('document.getElementById("details").textContent'),/failed reads/);
    await evaluate('document.getElementById("profile").value="1";document.getElementById("profile").dispatchEvent(new Event("change"))');
    assert.equal(await evaluate('document.getElementById("capture").options.length'),1);
    await evaluate(`data.profiles[1].fields.push({
      id:"test_word",name:"Test signed word",addr:256,width:2,members:[],
      encoding:"int16_le",scale:2,offset:10,status:"observed",mem:"ram"
    });
    data.captures.push({name:"test",profile:data.profiles[1].id,first:1,last:2,bytes:{
      "ram:256":{n:1,last:255,min:255,max:255,changes:0,distinct:1,rejected:0,first_t:1,last_t:1,points:[[1,255]],histogram:[[255,1]]},
      "ram:257":{n:1,last:255,min:255,max:255,changes:0,distinct:1,rejected:0,first_t:2,last_t:2,points:[[2,255]],histogram:[[255,1]]}
    }});chooseProfile();document.querySelector("[data-address='257']").click();`);
    assert.equal(await evaluate('document.querySelectorAll(".byte").length'),272);
    assert.equal(await evaluate('document.querySelectorAll(".selected").length'),2);
    assert.match(await evaluate('document.getElementById("details").textContent'),/Raw -1; decoded 8/);
    await open("eeprom");
    assert.equal(await evaluate('document.getElementById("capture").options.length'),1);
    await evaluate('document.querySelector("[data-address=\'60\']").dispatchEvent(new PointerEvent("pointermove",{clientX:100,clientY:100}))');
    assert.equal(await evaluate('document.getElementById("tooltip").hidden'),false);
    assert.match(await evaluate('document.getElementById("tooltip").textContent'),/Stop time/);
    assert.equal(await evaluate('document.querySelectorAll(".selected").length'),18);
    assert.match(await evaluate('document.getElementById("details").textContent'),/chrono_programs.program_1.stop/);
    await evaluate('document.querySelector("[data-address=\'61\']").click()');
    assert.match(await evaluate('document.getElementById("details").textContent'),/mon-fri/);
    await evaluate('document.getElementById("search").value="chrono";document.getElementById("search").dispatchEvent(new Event("input"))');
    assert.equal(await evaluate('document.querySelectorAll(".byte:not(.dim)").length'),18);
    await evaluate('document.querySelector("[data-address=\'61\']").focus();document.activeElement.dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowRight"}))');
    assert.equal(await evaluate('document.activeElement.dataset.address'),"62");
    assert.deepEqual(errors,[]);
    console.log("Browser tests passed: hover, members, region highlighting, overlap, capture validity, profile isolation, search, keyboard.");
  }finally{
    clearTimeout(timeout);
    if(browser.exitCode===null){browser.kill();await stopped;}
    rmSync(directory,{recursive:true});
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
