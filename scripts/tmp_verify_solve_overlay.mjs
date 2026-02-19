import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';
const EMAIL = process.env.E2E_STUDENT_EMAIL || 'admin@uask.ai';
const PASS = process.env.E2E_STUDENT_PASSWORD || 'DevOnlyChangeMe123!';

const outDir = path.join(process.cwd(), 'reports', 'evidence', 'solve_overlay_check');
fs.mkdirSync(outDir, { recursive: true });
const log = [];

const parseTimer = (txt) => {
  const m = txt.match(/(\d{2}):(\d{2})\.(\d)s/);
  if (!m) return null;
  return Number(m[1]) * 60 + Number(m[2]) + Number(m[3]) / 10;
};

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  try {
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
    await page.locator('input[type="email"]').fill(EMAIL);
    await page.locator('input[type="password"]').fill(PASS);
    await page.getByRole('button', { name: /log in/i }).click();
    await page.waitForURL(/\/solve/);

    await page.evaluate(() => {
      localStorage.removeItem('uask.activeAttemptId');
      localStorage.removeItem('uask.activeQuery');
      localStorage.removeItem('uask.solveOverlayState.v1');
    });

    await page.getByRole('button', { name: /^Free$|^Short$|^Standard$|^Research$/ }).first().click();
    await page.locator('textarea[placeholder="Type your question..."]').fill('Solve x^2 - 5x + 6 = 0 and plot roots.');
    await page.getByTestId('solve-submit-button').click();

    const overlay = page.getByRole('dialog', { name: 'Solving Problem Progress' });
    await overlay.waitFor({ state: 'visible', timeout: 30000 });
    log.push('overlay_visible_initial=true');

    const stageLabels = ['Preparing Engine', 'Executing Solver', 'Calling AI Core', 'Plotting Coordinates'];
    for (const label of stageLabels) {
      const visible = await overlay.getByText(label, { exact: true }).isVisible();
      log.push(`stage_label_${label.replace(/\s+/g, '_').toLowerCase()}=${visible}`);
    }

    await page.screenshot({ path: path.join(outDir, 'overlay_initial.png'), fullPage: true });

    const timerTextBefore = await overlay.locator('p.text-4xl').first().innerText().catch(() => '');
    const timerSecBefore = parseTimer(timerTextBefore ?? '');
    log.push(`timer_before=${timerTextBefore}`);

    let progressed = false;
    for (let i = 0; i < 8; i++) {
      const completedCount = await overlay.locator('span.material-symbols-outlined:has-text("check_circle")').count();
      if (completedCount > 0) {
        progressed = true;
        break;
      }
      await wait(600);
    }
    log.push(`stage_progression_detected=${progressed}`);

    await wait(3500);
    const stillSolving = await overlay.isVisible().catch(() => false);
    log.push(`still_solving_before_refresh=${stillSolving}`);

    if (stillSolving) {
      const timerTextPreRefresh = await overlay.locator('p.text-4xl').first().innerText().catch(() => '');
      const timerSecPreRefresh = parseTimer(timerTextPreRefresh ?? '');
      await page.reload({ waitUntil: 'domcontentloaded' });
      const overlayAfterRefresh = page.getByRole('dialog', { name: 'Solving Problem Progress' });
      await overlayAfterRefresh.waitFor({ state: 'visible', timeout: 20000 });
      const timerTextPostRefresh = await overlayAfterRefresh.locator('p.text-4xl').first().innerText().catch(() => '');
      const timerSecPostRefresh = parseTimer(timerTextPostRefresh ?? '');
      log.push(`timer_pre_refresh=${timerTextPreRefresh}`);
      log.push(`timer_post_refresh=${timerTextPostRefresh}`);
      if (timerSecPreRefresh != null && timerSecPostRefresh != null) {
        log.push(`timer_resumed_nonreset=${timerSecPostRefresh >= (timerSecPreRefresh - 0.2)}`);
      } else {
        log.push('timer_resumed_nonreset=unknown');
      }
      await page.screenshot({ path: path.join(outDir, 'overlay_after_refresh.png'), fullPage: true });
    } else {
      log.push('refresh_while_solving=skipped_fast_completion');
    }

    await page.waitForTimeout(2500);
    await page.reload({ waitUntil: 'domcontentloaded' });
    const overlayPostCompletion = page.getByRole('dialog', { name: 'Solving Problem Progress' });
    const stuckAfterCompletion = await overlayPostCompletion.isVisible().catch(() => false);
    log.push(`stuck_after_completion_refresh=${stuckAfterCompletion}`);

    fs.writeFileSync(path.join(outDir, 'verification.log'), log.join('\n'));
    console.log(log.join('\n'));
  } catch (err) {
    log.push(`error=${err instanceof Error ? err.message : String(err)}`);
    fs.writeFileSync(path.join(outDir, 'verification.log'), log.join('\n'));
    console.error(err);
    process.exitCode = 1;
  } finally {
    await page.close();
    await browser.close();
  }
})();
