import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:9000';
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin@uask.ai';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'admin1234';

const QUESTION_TEXT = `Question 1 (Multiple-choice)
A ball is thrown upward from a platform. Its height is h(t)=15+20t-5t^2 (meters). When does it hit the ground?

Choices
(A) 1.0 s
(B) 2.0 s
(C) 3.0 s
(D) 4.0 s
(E) 5.0 s


Question 2 (Final answer only)
Solve on 0 ≤ x < 2π:
cos(2x) = sin(x).
Final answer: {all x in [0,2π)}


Question 3 (Multiple-choice)
Compute the determinant of A = [[3,1,0],[2,4,1],[0,1,2]].

Choices
(A) 14
(B) 16
(C) 18
(D) 20
(E) 22


Question 4 (Final answer only)
Evaluate the limit:
lim_{x→0} (e^{2x} - 1 - 2x) / x^2.
Final answer: ____


Question 5 (Multiple-choice)
A company’s profit (in thousands) is P(x)= -0.5x^2 + 8x - 10, where x is thousands of units sold. How many units maximize profit?

Choices
(A) 4,000
(B) 6,000
(C) 8,000
(D) 10,000
(E) 12,000


Question 6 (Final answer only)
Compute the exact value:
∫_0^{π/2} sin^3(x) dx.
Final answer: ____


Question 7 (Multiple-choice)
Find the sum of the infinite series:
6 + 3 + 1.5 + 0.75 + ...

Choices
(A) 9
(B) 10
(C) 11
(D) 12
(E) 15


Question 8 (Final answer only)
A right circular cone has volume 36π and height 9. Find its radius.
Final answer: ____


Question 9 (Multiple-choice)
Solve for x:
log_3(x-1) + log_3(x-3) = 2.

Choices
(A) x = 4
(B) x = 5
(C) x = 6
(D) x = 7
(E) No real solution


Question 10 (Final answer only)
Let z = (3 - 4i)/(1 + 2i). Write z in the form a + bi.
Final answer: ____


Question 11 (Multiple-choice)
A fair die is rolled 3 times. What is P(exactly two sixes)?

Choices
(A) 25/216
(B) 5/72
(C) 1/18
(D) 1/12
(E) 5/216


Question 12 (Final answer only)
Find the exact solution y(x) to the differential equation:
dy/dx = 3y,  with  y(0)=2.
Final answer: y(x) = ____


Question 13 (Multiple-choice)
Find the area of the region bounded by y=x^2 and y=2x.

Choices
(A) 1/3
(B) 2/3
(C) 4/3
(D) 5/3
(E) 2


Question 14 (Final answer only)
Compute the exact value of the sum:
∑_{k=1}^{10} (2k - 1).
Final answer: ____


Question 15 (Multiple-choice)
Let f(x)=x^3-6x^2+9x. The local minimum value of f(x) is:

Choices
(A) -4
(B) -1
(C) 0
(D) 1
(E) 4`;

async function loginViaApi(page) {
  const resp = await fetch(`${API_BASE}/api/v1/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: ADMIN_EMAIL, password: ADMIN_PASSWORD })
  });
  if (!resp.ok) throw new Error(`Login failed: ${resp.status} ${await resp.text()}`);
  const data = await resp.json();
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.evaluate((p) => {
    localStorage.setItem('token', p.access_token);
    localStorage.setItem('user_id', String(p.user_id));
    localStorage.setItem('user_name', p.full_name || '');
    localStorage.setItem('user_role', p.role || '');
    localStorage.setItem('session_token', p.session_token || '');
    localStorage.setItem('user', JSON.stringify(p));
    localStorage.setItem('uask.solveTier', 'FINAL');
  }, data);
}

async function main() {
  const outDir = path.resolve('reports/evidence');
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  await loginViaApi(page);
  const token = await page.evaluate(() => localStorage.getItem('token'));
  await page.goto(`${BASE_URL}/solve`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);

  const acceptBtn = page.getByRole('button', { name: /^accept$/i });
  if (await acceptBtn.count()) await acceptBtn.first().click();

  const textarea = page.locator("[data-testid='solve-query-textarea']").first();
  if (await textarea.count()) {
    await textarea.fill(QUESTION_TEXT);
  } else {
    const editable = page.locator("[contenteditable='true']").first();
    await editable.click();
    await page.keyboard.press('Control+A');
    await page.keyboard.type(QUESTION_TEXT);
  }

  const solveBtn = page.locator("[data-testid='solve-submit-button']");
  await solveBtn.click();

  for (let i = 0; i < 8; i++) {
    const candidates = [
      page.getByRole('button', { name: /confirm/i }),
      page.getByRole('button', { name: /continue/i }),
      page.getByRole('button', { name: /solve/i }),
      page.getByRole('button', { name: /split/i }),
    ];
    let clicked = false;
    for (const c of candidates) {
      if (await c.count()) {
        const btn = c.first();
        const text = ((await btn.textContent()) || '').toLowerCase();
        if (!text.includes('cancel') && !text.includes('close')) {
          await btn.click();
          clicked = true;
          break;
        }
      }
    }
    if (!clicked) break;
    await page.waitForTimeout(1000);
  }

  await page.waitForURL(/\/chat_final\//, { timeout: 180000 });
  const finalUrl = page.url();
  const sessionId = finalUrl.split('/chat_final/')[1]?.split(/[?#]/)[0] || null;
  let sessionPayload = null;
  if (sessionId && token) {
    const resp = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (resp.ok) {
      sessionPayload = await resp.json();
    }
  }
  const assistantMsg = Array.isArray(sessionPayload?.messages)
    ? [...sessionPayload.messages].reverse().find((m) => m.role === 'assistant')
    : null;
  const telemetry = assistantMsg?.metadata?.telemetry || null;
  const finalItems = assistantMsg?.structured_data?.items;

  const report = {
    final_url: finalUrl,
    session_id: sessionId,
    batch_response_summary: {
      items_count: Array.isArray(finalItems) ? finalItems.length : null,
      openai_calls_count: telemetry?.openai_calls_count ?? null,
      provider: telemetry?.provider ?? null,
      model: telemetry?.model ?? null,
    },
  };

  fs.writeFileSync(path.join(outDir, 'solve_button_second_set_report.json'), JSON.stringify(report, null, 2), 'utf-8');
  fs.writeFileSync(path.join(outDir, 'solve_button_second_set_batch_response.json'), JSON.stringify(sessionPayload || {}, null, 2), 'utf-8');

  console.log(JSON.stringify(report));
  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
