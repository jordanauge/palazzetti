// Run with: node tests/test_memory_html.cjs /path/to/chrome
const {spawn, execFileSync} = require("node:child_process");
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
    assert.match(await evaluate('document.getElementById("details").textContent'),/Nothing selected/);
    assert.equal(await evaluate('document.querySelector("[data-address=\'249\']").textContent'),"F9");
    assert.equal(await evaluate('document.querySelector("[data-address=\'16\']").classList.contains("unmapped")'),true);
    assert.equal(await evaluate('document.querySelector("[data-address=\'249\']").classList.contains("unmapped")'),false);
    assert.equal(await evaluate('getComputedStyle(document.querySelector("[data-address=\'249\']")).backgroundColor===getComputedStyle(document.querySelector("[data-address=\'66\']")).backgroundColor'),false);
    assert.equal(await evaluate(`const labels=entries.map(e=>e.field.name||e.field.id);
      labels.every((label,i)=>i===0||labels[i-1].localeCompare(label)<=0)`),true);
    await evaluate('document.querySelector("[data-field=\'power_setting_ram_aux\']").dispatchEvent(new PointerEvent("pointerenter"))');
    assert.equal(await evaluate('document.querySelectorAll(".byte.hovered").length'),1);
    assert.equal(await evaluate('document.querySelector("[data-address=\'71\']").classList.contains("hovered")'),true);
    assert.match(await evaluate('document.getElementById("details").textContent'),/Nothing selected/);
    await evaluate('document.querySelector("[data-field=\'power_setting_ram_aux\']").click()');
    assert.match(await evaluate('document.getElementById("details").textContent'),/secondary RAM copy/);
    const pinnedDetails=await evaluate('document.getElementById("details").textContent');
    await evaluate('document.querySelector("[data-field=\'fumes_temperature\']").dispatchEvent(new PointerEvent("pointerenter"))');
    assert.equal(await evaluate('document.querySelector("[data-address=\'71\']").classList.contains("selected")'),true);
    assert.equal(await evaluate('document.querySelector("[data-address=\'66\']").classList.contains("hovered")'),true);
    assert.equal(await evaluate('document.getElementById("details").textContent'),pinnedDetails);
    await evaluate('document.getElementById("category-tab").click()');
    assert.equal(await evaluate('document.getElementById("category-tab").getAttribute("aria-selected")'),"true");
    assert.match(await evaluate('document.getElementById("field-list").textContent'),/User settings/);
    assert.equal(await evaluate('document.querySelector("[data-field=\'power_setting_ram_aux\']").getAttribute("aria-pressed")'),"true");
    await evaluate('document.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape"}))');
    assert.equal(await evaluate('document.querySelectorAll(".selected").length'),0);
    assert.equal(await evaluate('document.querySelectorAll(".hovered").length'),0);
    await evaluate('document.querySelector("[data-field=\'service_g_fumi_p1\']").click()');
    assert.equal(await evaluate('document.querySelectorAll(".byte.selected").length'),0);
    assert.equal(await evaluate('document.querySelectorAll(".field-entry.selected").length'),1);
    assert.match(await evaluate('document.getElementById("details").textContent'),/Unlocated parameter/);
    assert.match(await evaluate('document.getElementById("details").textContent'),/Our reverse engineering/);
    assert.match(await evaluate('document.getElementById("details").textContent'),/External reference/);
    assert.match(await evaluate('document.getElementById("details").textContent'),/supports: encoding/);
    assert.equal(await evaluate('document.querySelectorAll("#details a").length>=2'),true);
    await evaluate('document.querySelector("[data-field=\'fumes_temperature\']").click()');
    assert.match(await evaluate('document.getElementById("details").textContent'),/panel_match/);
    assert.equal(await evaluate('document.querySelector("#details a[href*=\'ridiculouslab.com\']")!==null'),true);
    assert.equal(await evaluate('document.getElementById("capture").options.length'),1);
    await evaluate(`const profileId=data.profiles[0].id;
      const observed={n:1,last:26,min:26,max:26,changes:0,distinct:1,rejected:0,
        first_t:1,last_t:1,points:[[1,26]],histogram:[[26,1]]};
      data.captures.push(
        {name:"test valid read",profile:profileId,first:1,last:1,bytes:{"ram:249":observed}},
        {name:"test rejected read",profile:profileId,first:1,last:1,bytes:{"ram:249":{n:0,rejected:25}}}
      );chooseProfile();`);
    assert.equal(await evaluate('document.getElementById("capture").options.length'),3);
    assert.equal(await evaluate('document.querySelector("[data-address=\'249\']").textContent'),"1A");
    await evaluate('document.querySelector("[data-field=\'power_state\']").click();document.getElementById("cell-mode").value="address";document.getElementById("cell-mode").dispatchEvent(new Event("change"))');
    assert.equal(await evaluate('document.querySelector("[data-address=\'249\']").textContent'),"F9");
    assert.equal(await evaluate('document.querySelector("[data-address=\'249\']").classList.contains("selected")'),true);
    assert.match(await evaluate('document.getElementById("details").textContent'),/Last 0x1A/);
    await evaluate('document.querySelector("[data-address=\'90\']").click()');
    assert.match(await evaluate('document.getElementById("details").textContent'),/refuted/);
    assert.match(await evaluate('document.getElementById("details").textContent'),/Running flags/);
    await evaluate('document.getElementById("capture").value="1";document.getElementById("capture").dispatchEvent(new Event("change"))');
    assert.equal(await evaluate('document.querySelector("[data-address=\'249\']").textContent'),"·");
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
    assert.equal(await evaluate('document.querySelectorAll(".byte.selected").length'),2);
    assert.match(await evaluate('document.getElementById("details").textContent'),/Raw -1; decoded 8/);
    await open("eeprom");
    assert.equal(await evaluate('document.getElementById("capture").options.length'),1);
    await evaluate('document.querySelector("[data-address=\'60\']").dispatchEvent(new PointerEvent("pointermove",{clientX:100,clientY:100}))');
    assert.equal(await evaluate('document.getElementById("tooltip").hidden'),false);
    assert.match(await evaluate('document.getElementById("tooltip").textContent'),/Stop time/);
    assert.equal(await evaluate('document.querySelectorAll(".byte.hovered").length'),18);
    assert.equal(await evaluate('document.querySelectorAll(".selected").length'),0);
    assert.match(await evaluate('document.getElementById("details").textContent'),/Nothing selected/);
    await evaluate('document.querySelector("[data-address=\'60\']").click()');
    assert.match(await evaluate('document.getElementById("details").textContent'),/chrono_programs.program_1.stop/);
    await evaluate('document.querySelector("[data-address=\'61\']").click()');
    assert.match(await evaluate('document.getElementById("details").textContent'),/mon-fri/);
    assert.match(await evaluate('document.getElementById("details").textContent'),/Parent Chrono programs/);
    await evaluate('document.getElementById("search").value="chrono";document.getElementById("search").dispatchEvent(new Event("input"))');
    assert.equal(await evaluate('document.querySelectorAll(".byte:not(.dim)").length'),18);
    assert.equal(await evaluate('document.querySelector("[data-field=\'power_setting\']").hidden'),true);
    assert.equal(await evaluate('document.querySelector("[data-field=\'chrono_programs.program_1.start\']").hidden'),false);
    await evaluate('document.querySelector("[data-address=\'61\']").focus();document.activeElement.dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowRight"}))');
    assert.equal(await evaluate('document.activeElement.dataset.address'),"62");
    await evaluate('document.getElementById("search").value="";document.getElementById("search").dispatchEvent(new Event("input"));document.querySelector("[data-field=\'chrono_programs.program_1\']").click()');
    assert.equal(await evaluate('document.querySelectorAll(".byte.selected").length'),3);
    assert.equal(await evaluate('document.querySelectorAll(".field-entry.selected").length'),1);
    const programDetails=await evaluate('document.getElementById("details").textContent');
    await evaluate('document.querySelector("[data-field=\'chrono_programs.program_1.start\']").dispatchEvent(new PointerEvent("pointerenter"))');
    assert.equal(await evaluate('document.querySelectorAll(".byte.hovered").length'),1);
    assert.equal(await evaluate('document.querySelector("[data-address=\'59\']").matches(".selected.hovered")'),true);
    assert.equal(await evaluate('document.getElementById("details").textContent'),programDetails);
    await evaluate('document.querySelector("[data-field=\'chrono_programs.program_1.start\']").dispatchEvent(new PointerEvent("pointerleave"))');
    assert.equal(await evaluate('document.querySelectorAll(".byte.hovered").length'),0);
    assert.equal(await evaluate('document.querySelectorAll(".byte.selected").length'),3);
    await evaluate('document.getElementById("search").value="0x3C";document.getElementById("search").dispatchEvent(new Event("input"))');
    assert.equal(await evaluate('document.querySelector("[data-field=\'chrono_programs\']").hidden'),false);
    assert.equal(await evaluate('document.querySelector("[data-field=\'chrono_programs.program_1.stop\']").hidden'),false);
    assert.equal(await evaluate('document.querySelector("[data-field=\'chrono_programs.program_2\']").hidden'),true);
    for(const width of [700,900,1200,1600]){
      await send("Emulation.setDeviceMetricsOverride",{width,height:900,deviceScaleFactor:1,mobile:false},sessionId);
      assert.equal(await evaluate('document.documentElement.scrollWidth<=window.innerWidth'),true,"No viewport overflow at "+width);
    }
    assert.deepEqual(errors,[]);
    console.log("Browser tests passed: linked catalogue, category tabs, independent hover/selection, click-only details, layout colors, members, captures, search, keyboard, responsive layout.");
    const mock=await send("Page.addScriptToEvaluateOnNewDocument",{source:`
      window.calls=[];
      const fixture={format:1,maps:[{id:"test",interval_ms:1000,fields:[
        {id:"state",name:"State",mem:"ram",addr:249,status:"observed",values:{"26":"off"}},
        {id:"word",mem:"ram",addr:10,width:2,encoding:"int16_le",scale:0.5},
        {id:"missing",mem:"eeprom",addr:78},
        {id:"bcd",mem:"ram",addr:20,encoding:"bcd"}
      ]}]};
      window.sample={boot:123,uptime_ms:4000,free_heap:20000,filesystem:true,paused:false,bytes:[
        {mem:"ram",addr:249,value:26,valid:true,stale:false,age_ms:20,interval_ms:1000},
        {mem:"ram",addr:10,value:254,valid:true,stale:false,age_ms:20},
        {mem:"ram",addr:11,value:255,valid:true,stale:false,age_ms:40},
        {mem:"ram",addr:20,value:90,valid:true,stale:false,age_ms:40}
      ]};
      window.fetch=async(url,options={})=>{
        window.calls.push({url,method:options.method||"GET",body:options.body?.toString()});
        if(url==="/memory/map")return new Response(JSON.stringify(fixture));
        if(url==="/memory/cache")return new Response(JSON.stringify(window.sample));
        if(url==="/memory/override")return new Response("updated");
        return new Response("not found",{status:404});
      };
    `},sessionId);
    const loaded=new Promise(done=>waiters.set(sessionId+":Page.loadEventFired",done));
    await send("Page.navigate",{url:pathToFileURL(resolve("components/palazzetti/map_web.html")).href},sessionId);
    await loaded;
    assert.equal(await evaluate('document.querySelectorAll("#fields tr").length'),4);
    assert.match(await evaluate('document.getElementById("fields").textContent'),/off/);
    assert.match(await evaluate('document.getElementById("fields").textContent'),/-1/);
    assert.match(await evaluate('document.getElementById("fields").textContent'),/Unavailable/);
    assert.match(await evaluate('document.getElementById("fields").textContent'),/Invalid BCD/);
    await evaluate('(async()=>{sample.bytes[0].valid=false;sample.bytes[0].value=null;sample.bytes[0].error="timeout";await refresh()})()');
    assert.match(await evaluate('document.querySelector("#fields tr").textContent'),/Unavailable.*timeout/);
    await evaluate('(async()=>{const input=document.querySelector("#fields input");input.focus();input.value=4500;await refresh()})()');
    assert.equal(await evaluate('document.querySelector("#fields input").value'),"4500");
    await evaluate('document.querySelector("#fields button").onclick()');
    // The asynchronous handler is observable via the fetch stub, not a live server.
    assert.match(await evaluate('calls.find(c=>c.url==="/memory/override").body'),/interval_ms=4500/);
    assert.equal(await evaluate('calls.filter(c=>c.method!=="GET").every(c=>c.url==="/memory/override")'),true);
    await evaluate('(async()=>{fetch=async()=>new Response("Unauthorized",{status:401});await run(refresh)})()');
    assert.match(await evaluate('document.getElementById("message").textContent'),/Unauthorized/);
    assert.deepEqual(errors,[]);
    console.log("Device dashboard tests passed: uploaded schema rendering, enum/signed/scaled values, invalid BCD, unavailable/failed reads, editing preservation, volatile override and HTTP errors.");
    if(process.env.PLZ_DEVICE_URL){
      await send("Page.removeScriptToEvaluateOnNewDocument",{identifier:mock.identifier},sessionId);
      const credentials=JSON.parse(execFileSync(resolve(".venv/bin/python"),["-c",
        "import json,yaml; from pathlib import Path; s=yaml.safe_load(Path('example/secrets.yaml').read_text()); print(json.dumps([s['web_username'],s['web_password']]))"
      ],{encoding:"utf8"}));
      const authorization="Basic "+Buffer.from(credentials.join(":")).toString("base64");
      await send("Network.enable",{},sessionId);
      await send("Network.setExtraHTTPHeaders",{headers:{Authorization:authorization}},sessionId);
      const loaded=new Promise(done=>waiters.set(sessionId+":Page.loadEventFired",done));
      await send("Page.navigate",{url:process.env.PLZ_DEVICE_URL+"/memory"},sessionId);
      await loaded;
      await evaluate(`new Promise((resolve,reject)=>{
        const check=()=>{
          if(document.querySelectorAll("#fields tr").length){observer.disconnect();resolve();}
          else if(document.getElementById("message").classList.contains("error")){
            observer.disconnect();reject(new Error(document.getElementById("message").textContent));
          }
        };
        const observer=new MutationObserver(check);
        observer.observe(document.body,{childList:true,subtree:true});check();
      })`);
      assert.equal(await evaluate('document.querySelectorAll("#fields tr").length'),
        await evaluate('documentMap.maps[Number(el("map").value)||0].fields.length'));
      assert.match(await evaluate('document.getElementById("status").textContent'),/storage mounted/);
      const body=await evaluate('(async()=>await (await request("/memory/map")).text())()');
      await evaluate(`(async()=>{
        const file=new File([${JSON.stringify(body)}],"lara.json",{type:"application/json"});
        const transfer=new DataTransfer();transfer.items.add(file);el("file").files=transfer.files;
        await el("upload").onclick();
      })()`);
      assert.match(await evaluate('el("message").textContent'),/Map stored in flash and activated/);
      await evaluate('document.querySelector("#fields input").value=0;document.querySelector("#fields button").onclick()');
      assert.match(await evaluate('el("message").textContent'),/Volatile cadence updated/);
      assert.deepEqual(errors,[]);
      console.log("Live ESP browser workflow passed: authenticated page, streamed cache, upload through file picker and volatile override.");
    }
  }finally{
    clearTimeout(timeout);
    if(browser.exitCode===null){browser.kill();await stopped;}
    rmSync(directory,{recursive:true});
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
