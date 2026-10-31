// Records the whole demo as one screen capture and writes the time each narration part starts.
// Usage: NODE_PATH=$(npm root -g) node record.js <base-url> <out-dir>
// Needs the backend (reset first) and the website running at <base-url>.
const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const BASE = process.argv[2] || 'http://127.0.0.1:8001'
const OUT = process.argv[3] || path.join(__dirname, 'out')
const OVERLOAD = fs.readFileSync(path.join(__dirname, 'OVERLOAD.txt'), 'utf8').trim()
const VTT = path.join(__dirname, 'assets', 'meeting1.vtt')
const W = 1440, H = 810

const CURSOR = () => {
  const make = () => {
    if (document.getElementById('fake-cursor')) return
    const c = document.createElement('div')
    c.id = 'fake-cursor'
    c.style.cssText = 'position:fixed;left:-50px;top:-50px;width:24px;height:24px;border-radius:50%;background:rgba(107,31,52,.88);border:2.5px solid #fff;box-shadow:0 3px 12px rgba(0,0,0,.35);z-index:2147483647;pointer-events:none;transform:translate(-50%,-50%);transition:transform .12s'
    document.documentElement.appendChild(c)
    addEventListener('mousemove', (e) => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px' }, true)
    addEventListener('mousedown', () => { c.style.transform = 'translate(-50%,-50%) scale(.65)' }, true)
    addEventListener('mouseup', () => { c.style.transform = 'translate(-50%,-50%) scale(1)' }, true)
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', make); else make()
}

const CARD = (big, small) => `<!doctype html><meta charset=utf-8><body style="margin:0;height:100vh;display:grid;place-items:center;background:#eeede9;font-family:'Inter Tight','Inter',system-ui,sans-serif;color:#22231f">
<div style="text-align:center"><div style="display:inline-flex;align-items:center;gap:16px;font-size:64px;font-weight:600;letter-spacing:-.04em"><span style="display:grid;place-items:center;width:78px;height:78px;border-radius:22px;background:#6b1f34;color:#fff;font-size:52px">q</span>quorum<span style="color:#6b1f34">.</span></div>
<div style="margin-top:28px;font-size:44px;font-weight:500;letter-spacing:-.03em;color:#6f706a">${big}</div><div style="margin-top:14px;font-size:22px;color:#6f706a">${small}</div></div>`

;(async () => {
  fs.mkdirSync(OUT, { recursive: true })
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, recordVideo: { dir: OUT, size: { width: W, height: H } } })
  await ctx.addInitScript(CURSOR)
  const t0 = Date.now()
  const page = await ctx.newPage()
  const marks = []
  const mark = (n) => { marks.push({ scene: n, t: (Date.now() - t0) / 1000 }); console.log('scene', n, ((Date.now() - t0) / 1000).toFixed(1) + 's') }
  const wait = (ms) => page.waitForTimeout(ms)
  const tryStep = async (name, fn) => { try { await fn() } catch (e) { console.log('  !', name, '-', e.message.split('\n')[0]) } }

  let mx = W / 2, my = H / 2
  async function moveTo(loc, opts = {}) {
    await loc.first().scrollIntoViewIfNeeded().catch(() => {})
    const box = await loc.first().boundingBox()
    if (!box) return
    const x = box.x + box.width * (opts.fx ?? 0.5), y = box.y + box.height * (opts.fy ?? 0.5)
    await page.mouse.move(x, y, { steps: 28 }); mx = x; my = y
    await wait(250)
  }
  async function click(loc, opts) { await moveTo(loc, opts); await page.mouse.down(); await wait(90); await page.mouse.up(); await wait(200) }
  async function smoothTo(loc, block = 0.22, ms = 1100) {
    const y = await loc.first().evaluate((el, b) => Math.max(0, el.getBoundingClientRect().top + scrollY - innerHeight * b), block)
    await page.evaluate(([to, dur]) => new Promise((done) => {
      const from = scrollY, t = performance.now()
      const ease = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2)
      const tick = (now) => { const p = Math.min(1, (now - t) / dur); scrollTo(0, from + (to - from) * ease(p)); p < 1 ? requestAnimationFrame(tick) : done() }
      requestAnimationFrame(tick)
    }), [y, ms])
    await wait(300)
  }

  // 1 · Title card
  mark(1)
  await page.setContent(CARD('Meetings that remember.', 'Built for the Product Space × Wispr Flow hackathon'))
  await wait(3500)

  // 2 · Speak it (the sample types itself, like dictation landing in the box)
  mark(2)
  await page.goto(BASE + '/', { waitUntil: 'networkidle' })
  await wait(3200)
  await tryStep('sample', async () => {
    await click(page.getByText('Play the sample debrief'))
    await page.waitForFunction(() => document.querySelector('#debrief').value.length >= 200, null, { timeout: 15000 })
    await wait(2200)
  })

  // 3 · Agents run
  mark(3)
  await tryStep('run', async () => {
    await click(page.getByRole('button', { name: /Run Quorum/ }))
    await page.getByRole('button', { name: /Accept all new/ }).waitFor({ timeout: 90000 })
    await wait(2500)
  })

  // 4 · The conflict
  mark(4)
  await tryStep('conflict', async () => {
    await smoothTo(page.getByText('This contradicts what your team agreed.'), 0.12)
    await wait(2500)
    await moveTo(page.getByRole('button', { name: 'Keep previous' })); await wait(900)
    await click(page.getByRole('button', { name: 'Accept new' })); await wait(1500)
  })

  // 5 · Ripple
  mark(5)
  await tryStep('ripple', async () => {
    await smoothTo(page.getByText(/what that changes/i), 0.12)
    await wait(2200)
    const row = page.locator('.ripple-row').first()
    await click(row, { fx: 0.04 }); await wait(1100)
    await click(row, { fx: 0.04 }); await wait(1800)
  })

  // 6 · Tasks and cleaned-up words
  mark(6)
  await tryStep('cleanup', async () => {
    await smoothTo(page.getByText('Your words, cleaned up'), 0.25)
    await wait(3800)
  })

  // 7 · Spoken edit
  mark(7)
  await tryStep('edit', async () => {
    const box = page.getByLabel(/Tell Quo/i)
    await smoothTo(box, 0.4)
    await click(box)
    await page.keyboard.type('Move the beta testers message to Tuesday', { delay: 55 })
    await wait(600)
    await click(page.getByRole('button', { name: /Apply/ }))
    await page.locator('.edit-changes').waitFor({ timeout: 60000 })
    await wait(2800)
  })

  // 8 · Approve
  mark(8)
  await tryStep('approve', async () => {
    await click(page.getByRole('button', { name: /^Approve/ }))
    await page.getByText(/Open the team board/).waitFor({ timeout: 60000 })
    await wait(4500)
  })

  // 9 · Board
  mark(9)
  await tryStep('board', async () => {
    await click(page.getByText('Open the team board'))
    await page.getByText('open commitments').first().waitFor({ timeout: 15000 })
    await wait(2500)
    await smoothTo(page.locator('.owner-column').first(), 0.25, 900)
    await moveTo(page.locator('.board-task').nth(1)); await wait(2500)
  })

  // 10 · Reminders (demo clock)
  mark(10)
  await tryStep('reminders', async () => {
    await click(page.locator('.clock-pill'))
    await wait(700)
    await page.locator('#demo-clock').fill('2026-11-03T08:00')
    await wait(500)
    await click(page.getByRole('button', { name: /Update clock/ })); await wait(1800)
    await click(page.getByRole('button', { name: 'Run reminders' })); await wait(4200)
  })

  // 11 · Digest
  mark(11)
  await tryStep('digest', async () => {
    await click(page.getByRole('link', { name: 'Digest' })); await wait(2000)
    await click(page.getByRole('button', { name: 'Rahul' })); await wait(2800)
    await smoothTo(page.locator('.digest-columns'), 0.3, 900); await wait(2500)
  })

  // 12 · Memory: timeline and decision map
  mark(12)
  await tryStep('memory', async () => {
    await click(page.getByRole('link', { name: 'Memory' })); await wait(3200)
    await click(page.getByText('Decision map', { exact: true })); await wait(4200)
  })

  // 13 · Time machine
  mark(13)
  await tryStep('time machine', async () => {
    await click(page.getByText('Time machine', { exact: true })); await wait(1500)
    await page.locator('input[aria-label="Decision snapshot date"]').fill('2026-10-25'); await wait(3500)
  })

  // 14 · Brief and radar
  mark(14)
  await tryStep('brief radar', async () => {
    await click(page.getByText('Walk-in brief', { exact: true })); await wait(3600)
    await click(page.getByText('Change radar', { exact: true })); await wait(3600)
  })

  // 15 · Ask
  mark(15)
  await tryStep('ask', async () => {
    await click(page.getByRole('link', { name: 'Ask' })); await wait(2200)
    await click(page.getByText('When are we launching?').first()); await wait(1200)
    const send = page.getByRole('button', { name: /Ask your meetings/ })
    if (await send.isEnabled()) await click(send)
    await page.locator('.answer-history > *').first().waitFor({ timeout: 20000 }); await wait(3200)
    await smoothTo(page.locator('.answer-history'), 0.2, 900); await wait(2500)
  })

  // 16 · Reset, then the warnings
  mark(16)
  await tryStep('warnings', async () => {
    await click(page.getByRole('button', { name: 'Reset the demo' })); await wait(3600)
    await click(page.locator('#debrief'))
    await page.keyboard.type(OVERLOAD, { delay: 12 })
    await wait(700)
    await click(page.getByRole('button', { name: /Run Quorum/ }))
    await page.getByRole('button', { name: /Accept all new/ }).waitFor({ timeout: 90000 })
    await wait(1500)
    await smoothTo(page.locator('.segmented-choice').first(), 0.35, 1000); await wait(3200)
    await smoothTo(page.getByText(/Priya has 3 tasks/), 0.4, 900); await wait(3500)
  })

  // 17 · Upload
  mark(17)
  await tryStep('upload', async () => {
    await click(page.getByRole('link', { name: /Quorum home/ })); await wait(2500)
    await moveTo(page.locator('.upload-link')); await wait(900)
    const [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.locator('.upload-link').click()])
    await chooser.setFiles(VTT)
    await wait(9000)
  })

  // 18 · Outro
  mark(18)
  await page.setContent(CARD('Meetings that remember.', 'Built entirely by voice with Wispr Flow'))
  await wait(4200)
  const total = (Date.now() - t0) / 1000
  marks.push({ scene: 19, t: total })

  const video = page.video()
  await ctx.close()
  const file = await video.path()
  fs.writeFileSync(path.join(OUT, 'marks.json'), JSON.stringify({ marks, total, video: path.basename(file) }, null, 2))
  console.log('video', file, 'total', total.toFixed(1) + 's')
  await browser.close()
})()
