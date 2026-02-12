import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:9000';
const EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin@uask.ai';
const PASS = process.env.E2E_ADMIN_PASSWORD || 'admin1234';
const EVIDENCE = path.resolve('reports/evidence');

const sessionsData = JSON.parse(fs.readFileSync(path.join(EVIDENCE,'chat_6cases_sessions.json'),'utf-8'));
const sessionIds = sessionsData.cases.map(c => c?.done?.session_id).filter(Boolean);

async function login(page){
  const resp = await fetch(`${API_BASE}/api/v1/login`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({email:EMAIL,password:PASS})});
  if(!resp.ok) throw new Error(`login failed ${resp.status}`);
  const data = await resp.json();
  await page.goto(`${BASE_URL}/login`, {waitUntil:'domcontentloaded'});
  await page.evaluate((payload)=>{
    localStorage.setItem('token', payload.access_token);
    localStorage.setItem('user_id', String(payload.user_id));
    localStorage.setItem('user_name', payload.full_name || '');
    localStorage.setItem('user_role', payload.role || '');
    localStorage.setItem('session_token', payload.session_token || '');
    localStorage.setItem('user', JSON.stringify(payload));
  }, data);
}

const browser = await chromium.launch({headless:true});
const context = await browser.newContext();
const page = await context.newPage();
const consoleErrors=[];
page.on('console',msg=>{ if(msg.type()==='error') consoleErrors.push(msg.text()); });
page.on('pageerror',err=>consoleErrors.push(String(err)));

await login(page);

const results=[];
for (const sid of sessionIds){
  const apiStatuses=[];
  const onResp = (res)=>{ const url=res.url(); if(url.includes('/api/')) apiStatuses.push({url,status:res.status()}); };
  page.on('response', onResp);
  let ok=true; let mainStatus=null;
  try{
    const resp = await page.goto(`${BASE_URL}/chat/${sid}`, {waitUntil:'networkidle', timeout:45000});
    mainStatus = resp?.status() ?? null;
    if(mainStatus!==200) ok=false;
  }catch{ ok=false; mainStatus=-1; }
  page.off('response', onResp);
  const bad = apiStatuses.filter(a=>a.status>=400);
  if(bad.length) ok=false;
  results.push({session_id:sid, main_status:mainStatus, ok, bad_api_calls:bad, api_calls:apiStatuses.slice(0,40)});
}

fs.writeFileSync(path.join(EVIDENCE,'chat_6cases_smoke.json'), JSON.stringify(results,null,2));
fs.writeFileSync(path.join(EVIDENCE,'chat_6cases_console_log.txt'), consoleErrors.join('\n'));

await context.close();
await browser.close();
console.log(JSON.stringify({ok: results.every(r=>r.ok), checked: results.length}, null, 2));
