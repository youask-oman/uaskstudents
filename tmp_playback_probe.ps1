$before = Invoke-RestMethod -Method Get -Uri "http://localhost:9000/api/v1/chat_final/playback_state?message_id=108"
$node = @"
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto('http://localhost:3000/chat_final/63', { waitUntil: 'networkidle', timeout: 120000 });
  await page.waitForTimeout(6500);
  await browser.close();
})();
"@
$node | node
$after = Invoke-RestMethod -Method Get -Uri "http://localhost:9000/api/v1/chat_final/playback_state?message_id=108"
Write-Output ("before_visible=" + $before.visible_len + " before_complete=" + $before.is_complete)
Write-Output ("after_visible=" + $after.visible_len + " after_complete=" + $after.is_complete)
