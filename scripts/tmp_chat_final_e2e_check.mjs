import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const outDir = path.resolve('reports/evidence/chat_final_63');
fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const result = {
  url: 'http://localhost:3000/chat_final/63',
  question_count: null,
  giant_rect_count: null,
  playback_len_t0: null,
  playback_len_t1: null,
  playback_grew: null,
  playback_source_console: [],
};
page.on('console', (msg) => {
  const text = msg.text();
  if (text.includes('[chat_final] playback_source')) {
    result.playback_source_console.push(text);
  }
});
await page.goto(result.url, { waitUntil: 'networkidle', timeout: 120000 });
await page.waitForTimeout(1500);
await page.screenshot({ path: path.join(outDir, 'after_load.png'), fullPage: true });

const questionText = 'If the patient tests positive on the first test, find the probability they actually have the disease.';
result.question_count = await page.getByText(questionText, { exact: false }).count();
result.giant_rect_count = await page.locator('svg rect[width="13800"][height="950"][y="-200"]').count();

const playback = page.locator('#steps-block-playback-solution');
if (await playback.count()) {
  result.playback_len_t0 = (await playback.innerText()).length;
  await page.screenshot({ path: path.join(outDir, 'playback_t0.png'), fullPage: true });
  await page.waitForTimeout(1300);
  result.playback_len_t1 = (await playback.innerText()).length;
  await page.screenshot({ path: path.join(outDir, 'playback_t1.png'), fullPage: true });
  result.playback_grew = (result.playback_len_t1 || 0) > (result.playback_len_t0 || 0);
}

fs.writeFileSync(path.join(outDir, 'e2e_check.json'), JSON.stringify(result, null, 2), 'utf-8');
await browser.close();
console.log(path.join(outDir, 'e2e_check.json'));
