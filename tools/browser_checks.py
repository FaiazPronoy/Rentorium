#!/usr/bin/env python3
"""
Browser checks for Rentorium, in a real browser through Playwright.

  1. pages     every page a visitor, a renter, an owner and the agent can
               reach answers 200 with no console error
  2. contrast  every piece of text against WCAG AA, light and dark
  3. phone     nothing scrolls sideways at 390 px
  4. flows     each key on the rack signs in as its person, the password
               eye works, the header search and the rail both filter

Start the site first on a database filled by seed_demo:

  cd Rentorium
  python manage.py seed_demo
  python manage.py runserver 127.0.0.1:8020
  python ../tools/browser_checks.py

Uses the Edge that ships with Windows; set RT_BROWSER=chrome for Chrome.
Screenshots go to tools/shots (ignored by git).
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("RT_BASE", "http://127.0.0.1:8020")
CHANNEL = os.environ.get("RT_BROWSER", "msedge")
SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")

VISITOR = ["/", "/property/browse", "/property/categories", "/about", "/faqs", "/contact/",
           "/testimonial", "/account/signin", "/account/signup", "/property/compare/"]
RENTER = ["/account/dashboard/", "/property/saved/", "/property/visits/", "/property/messages/",
          "/account/notifications/", "/account/profile", "/property/saved-searches/"]
OWNER = ["/property/my-listings/", "/property/list-a-property"]
AGENT = ["/agents/dashboard/", "/agents/reports/", "/agents/stats/", "/agents/users/",
         "/agents/log/", "/agents/enquiries/"]
PASS, FAIL = [], []


def check(name, ok, extra=""):
    (PASS if ok else FAIL).append(name)
    print(("  ok   " if ok else "  FAIL ") + name + ("  -> " + str(extra) if extra and not ok else ""))


CONTRAST_JS = r"""
() => {
  const parse = c => {
    const m = c && c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number);
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  const lin = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const lum = c => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
  const over = (top, under) => ({r: top.r * top.a + under.r * (1 - top.a),
                                 g: top.g * top.a + under.g * (1 - top.a),
                                 b: top.b * top.a + under.b * (1 - top.a), a: 1});
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
  const root = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
  const hex = h => ({r: parseInt(h.slice(1, 3), 16), g: parseInt(h.slice(3, 5), 16), b: parseInt(h.slice(5, 7), 16), a: 1});
  const page = /^#[0-9a-f]{6}$/i.test(root) ? hex(root) : {r: 255, g: 255, b: 255, a: 1};
  // a gradient band counts as its darkest and lightest stops, and both must pass
  const stops = img => [...img.matchAll(/rgba?\([^)]+\)/g)].map(m => parse(m[0])).filter(c => c && c.a >= .9);
  const background = el => {
    const stack = [];
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage.includes('url(') && e.tagName !== 'BODY') return null;  // text on a photograph
      if (cs.backgroundImage.includes('gradient') && e.tagName !== 'BODY') {
        const solid = stops(cs.backgroundImage);
        if (solid.length) return solid.reduce((a, c) => lum(c) > lum(a) ? c : a);
      }
      const c = parse(cs.backgroundColor);
      if (c && c.a > 0) { stack.push(c); if (c.a >= 1) break; }
    }
    if (!stack.length || stack[stack.length - 1].a < 1) stack.push(page);
    return stack.reduceRight((acc, layer) => acc ? over(layer, acc) : layer, null);
  };
  const bad = [];
  let checked = 0;
  for (const el of document.querySelectorAll('body *')) {
    const text = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
    if (!text) continue;
    const cs = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    if (cs.visibility === 'hidden' || cs.display === 'none' || box.width === 0 || box.height === 0) continue;
    if (el.closest('[aria-hidden="true"], .sr-only, [hidden], option, script, style, .menu-panel, .stage, .pcard-media, .hero-photo, .cat, .cat-tile')) continue;
    if (parseFloat(cs.opacity) === 0) continue;
    const fg = parse(cs.color);
    const bg = background(el);
    if (!fg || !bg) continue;
    const size = parseFloat(cs.fontSize), weight = parseInt(cs.fontWeight, 10);
    const need = (size >= 24 || (size >= 18.66 && weight >= 700)) ? 3 : 4.5;
    const r = ratio(fg.a < 1 ? over(fg, bg) : fg, bg);
    checked++;
    if (r < need) bad.push({text: text.slice(0, 40), ratio: Math.round(r * 100) / 100, need, cls: el.className || el.tagName});
  }
  return {checked, bad};
}
"""


def take_key(page, role):
    page.goto(BASE + "/account/signin")
    page.locator(".keytag", has_text=role).click()
    page.wait_for_load_state("networkidle")


def visit(page, urls, theme, who, statuses, fails, errors_seen):
    total = 0
    for url in urls:
        response = page.goto(BASE + url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(250)
        statuses.append((who + url, response.status))
        # anything that reveals on scroll is shown straight away for the check
        page.evaluate("document.documentElement.classList.remove('armed');"
                      "document.querySelectorAll('.reveal').forEach(e => e.classList.add('in'))")
        page.wait_for_timeout(700)
        res = page.evaluate(CONTRAST_JS)
        total += res["checked"]
        fails += [(who, url, b) for b in res["bad"]]
        name = "%s-%s-%s" % (theme, who, url.strip("/").replace("/", "-") or "home")
        page.screenshot(path=os.path.join(SHOTS, name + ".png"), full_page=True)
    return total


def main():
    os.makedirs(SHOTS, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=CHANNEL)

        for theme in ("light", "dark"):
            print("\n=== %s ===" % theme)
            statuses, fails, errors, total = [], [], [], 0
            for who, urls, key in (("visitor", VISITOR, None), ("renter", RENTER, "Renter"),
                                   ("owner", OWNER, "Owner"), ("agent", AGENT, "Agent")):
                ctx = browser.new_context(viewport={"width": 1366, "height": 900}, color_scheme=theme)
                page = ctx.new_page()
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                if key:
                    take_key(page, key)
                total += visit(page, urls, theme, who, statuses, fails, errors)
                if who == "visitor":
                    page.goto(BASE + "/property/browse")
                    href = page.locator("a[href*='/property/listing/']").first.get_attribute("href")
                    total += visit(page, [href], theme, who, statuses, fails, errors)
                ctx.close()
            check("%s: %d pages answer 200" % (theme, len(statuses)), all(s == 200 for _, s in statuses),
                  [u for u, s in statuses if s != 200])
            check("%s: no console errors" % theme, not errors, errors[:3])
            check("%s: %d text checks pass AA" % (theme, total), not fails, fails[:6])

        print("\n=== phone ===")
        wide = {}
        for who, urls, key in (("visitor", VISITOR, None), ("renter", RENTER, "Renter"), ("agent", AGENT, "Agent")):
            ctx = browser.new_context(viewport={"width": 390, "height": 844})
            page = ctx.new_page()
            if key:
                take_key(page, key)
            for url in urls:
                page.goto(BASE + url)
                page.wait_for_load_state("networkidle")
                w = page.evaluate("document.documentElement.scrollWidth")
                if w > 390:
                    wide[who + url] = w
            ctx.close()
        check("nothing scrolls sideways at 390 px", not wide, wide)

        print("\n=== flows ===")
        for role in ("Renter", "Owner", "Agent"):
            ctx = browser.new_context(viewport={"width": 1366, "height": 900})
            page = ctx.new_page()
            take_key(page, role)
            signed_in = page.locator(".menu > button").count() == 1
            check("the %s key signs in" % role.lower(), signed_in)
            ctx.close()

        ctx = browser.new_context(viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        page.goto(BASE + "/account/signin")
        page.locator("button[aria-label='Show password']").first.click()
        check("the eye shows the password", page.locator("#id_password").get_attribute("type") == "text")

        page.goto(BASE + "/")
        page.fill("#navSearch", "Gulshan")
        page.press("#navSearch", "Enter")
        page.wait_for_load_state("networkidle")
        check("the header search goes to the listings with the words in it",
              "/property/browse" in page.url and "q=Gulshan" in page.url)

        page.goto(BASE + "/")
        page.locator(".rail a", has_text="To rent").click()
        page.wait_for_load_state("networkidle")
        tags = page.locator(".pcard .badge-rent, .pcard .badge-sale").all_inner_texts()
        check("To rent on the rail shows only places to rent",
              tags and all(t.strip() == "To rent" for t in tags), tags[:4])
        check("and marks itself as the one in use", "on" in (page.locator(".rail a", has_text="To rent").get_attribute("class") or ""))
        ctx.close()

        browser.close()
    print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
