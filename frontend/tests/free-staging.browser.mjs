// Opt-in smoke against isolated synthetic-only staging; never targets production.
import assert from 'node:assert/strict';
import {writeFile,mkdir} from 'node:fs/promises';
const base=process.env.FREE_STAGING_URL;
assert.ok(base,'Set FREE_STAGING_URL to the isolated demo frontend');
assert.ok(new URL(base).hostname==='127.0.0.1'||process.env.ALLOW_HOSTED_FREE_STAGING==='true','Explicitly select a hosted staging URL');
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const evidence=process.env.FREE_STAGING_EVIDENCE||'/tmp/voicescope-free-staging';
await mkdir(evidence,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,args:['--no-sandbox','--autoplay-policy=no-user-gesture-required']});
const results=[],errors=[],consoleErrors=[],failedRequests=[];let submissions=0;
try {
 const visitor=await browser.newContext();
 for(const path of ['/runs','/settings','/api/v1/runs','/api/v1/runs/demo-staging-stt/stt-review/audio','/favicon.ico']){
  const r=await visitor.request.get(base+path);assert.equal(r.status(),401,path);assert.equal(r.headers()['cache-control'],'no-store');
 }
 await visitor.close();results.push('anonymous pages, assets and API denied');
 const wrong=await browser.newContext({httpCredentials:{username:'wrong',password:'wrong'}});
 assert.equal((await wrong.request.get(base+'/api/v1/runs')).status(),401);await wrong.close();
 const context=await browser.newContext({httpCredentials:{username:process.env.OPERATOR_AUTH_USER,password:process.env.OPERATOR_AUTH_PASSWORD},viewport:{width:1440,height:1000}});
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')consoleErrors.push(m.text());});page.on('requestfailed',r=>failedRequests.push(r.failure()?.errorText));page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/stt-review/reference'))submissions++;});
 await page.goto(base+'/runs');await page.getByRole('heading',{name:'Calls',exact:true}).waitFor();
 const listing=await context.request.get(base+'/api/v1/runs');assert.equal(listing.status(),200);assert.equal((await listing.json()).total,6);results.push('six seeded synthetic calls listed');
 await page.goto(base+'/runs?call=demo-staging-hallucination');await page.getByText('Hand-labeled fixture',{exact:true}).waitFor();
 await page.getByRole('button',{name:/Turn 2 · Agent/}).click();await page.getByRole('tab',{name:'Transcript',exact:true}).waitFor();
 await page.screenshot({path:evidence+'/hallucination-evidence.png',fullPage:true});results.push('hand-labeled contradiction and evidence navigation');
 await page.goto(base+'/runs?call=demo-staging-policy');await page.getByText('Confirmed rule match',{exact:true}).waitFor();results.push('deterministic policy violation');
 await page.goto(base+'/runs?call=demo-staging-stt');await page.getByRole('tab',{name:'STT quality',exact:true}).click();
 await page.getByRole('heading',{name:'Synthetic STT demo',exact:true}).waitFor();await page.getByRole('heading',{name:'20.0%',exact:true}).waitFor();
 await page.getByText('Synthetic fixture disagreement · completed',{exact:true}).waitFor();await page.getByText(/This compares authored synthetic fixtures, not measured recognizer accuracy/).waitFor();
 assert.equal(await page.getByText('Needs human review',{exact:true}).count(),1);
 assert.equal(await page.getByText('Confirmed STT error',{exact:true}).count(),0);
 await page.getByText('Set up a scored comparison',{exact:true}).click();assert.equal(await page.getByLabel('I confirmed the recording coverage by listening.',{exact:true}).isChecked(),false);await page.getByText('Set up a scored comparison',{exact:true}).click();
 assert.ok(await page.locator('mark.stt-disagreement').count()>0);
 await page.getByRole('button',{name:/Listen at 0:00.6/}).click();
 await page.waitForFunction(()=>{const a=document.querySelector('.stt-audio audio');return a&&!a.paused&&a.currentTime>=.6;});
 await page.locator('.stt-audio audio').evaluate(a=>a.pause());
 await page.screenshot({path:evidence+'/stt-disagreement.png',fullPage:true});results.push('synthetic disagreement, highlights and generated audio seeking');
 await page.reload();await page.getByRole('tab',{name:'STT quality',exact:true}).click();await page.getByRole('heading',{name:'20.0%',exact:true}).waitFor();results.push('fixture survives page reload');
 await page.goto(base+'/runs?call=demo-staging-not-scored');await page.getByRole('tab',{name:'STT quality',exact:true}).click();await page.getByRole('heading',{name:'Not scored',exact:true}).waitFor();
 await page.getByText('Source fixture timestamps were intentionally omitted. No aligned rate or confirmed error is available.',{exact:true}).waitFor();results.push('missing timestamps stay Not scored');
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:evidence+'/mobile-not-scored.png',fullPage:true});results.push('mobile without horizontal overflow');
 const cross=await context.request.get(base+'/api/v1/runs',{headers:{Origin:'https://synthetic-attacker.example'}});assert.equal(cross.status(),403);results.push('cross-origin API denied');
 const blocked=await page.evaluate(async()=>{const r=await fetch('/api/v1/analyze/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({transcript:'Synthetic'})});return {status:r.status,body:await r.json()};});assert.equal(blocked.status,503);assert.match(blocked.body.detail,/Synthetic demo/);results.push('live processing rejected explicitly');
 assert.equal(submissions,0);assert.deepEqual(errors,[]);
 await writeFile(evidence+'/results.json',JSON.stringify({results,pageErrors:errors,providerSubmissions:submissions,actualServices:true,syntheticOnly:true,consoleErrors,failedRequests},null,2));console.log(JSON.stringify({passed:results.length,pageErrors:errors.length,providerSubmissions:submissions}));
 await context.close();
} finally {await browser.close();}
