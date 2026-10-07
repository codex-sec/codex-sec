"""Draws stats.svg, streak.svg, langs.svg, year.svg and the hd-*.svg section headings.

Usage:
  GITHUB_TOKEN=... GH_LOGIN=yourname python3 scripts/generate_stats.py
  python3 scripts/generate_stats.py --demo     # fake data, no network
Only the standard library is used, so the workflow needs no pip install.
"""
import json, os, sys, urllib.request
from datetime import date, timedelta
from xml.sax.saxutils import escape

BG, INK, MUTE, RED, LINE = "#1c2430", "#f4f4f4", "#9aa4b2", "#ff4d5e", "#2b3646"
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"


def api(url, token, body=None):
    req = urllib.request.Request(url, data=body)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("User-Agent", "profile-stats")
    if body:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def get_days(login, token):
    q = """query($l:String!){user(login:$l){contributionsCollection{contributionCalendar{
      totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
    d = api("https://api.github.com/graphql", token,
            json.dumps({"query": q, "variables": {"l": login}}).encode())
    cal = d["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [(x["date"], x["contributionCount"])
            for w in cal["weeks"] for x in w["contributionDays"]]
    return cal["totalContributions"], days


def get_langs(login, token):
    by_bytes, by_repos = {}, {}
    repos = api(f"https://api.github.com/users/{login}/repos?per_page=100&type=owner", token)
    for r in repos:
        if r.get("fork"):
            continue
        if r.get("language"):
            by_repos[r["language"]] = by_repos.get(r["language"], 0) + 1
        for lang, n in api(r["languages_url"], token).items():
            by_bytes[lang] = by_bytes.get(lang, 0) + n
    top = lambda d: sorted(d.items(), key=lambda x: -x[1])[:5]
    return top(by_bytes), top(by_repos)


def span(a, b):
    da, db = date.fromisoformat(a), date.fromisoformat(b)
    f = lambda d, y: d.strftime("%b ").lower() + str(d.day) + (d.strftime(" '%y") if y else "")
    return f"{f(da, da.year != db.year)} - {f(db, False)}"


def streaks(days):
    today = date.today().isoformat()
    days = [d for d in days if d[0] <= today]
    best, best_rng, run, start = 0, "-", 0, None
    for dt, c in days:
        if c > 0:
            if run == 0:
                start = dt
            run += 1
            if run > best:
                best, best_rng = run, span(start, dt)
        else:
            run = 0
    cur, i = 0, len(days) - 1
    if i >= 0 and days[i][1] == 0:      # today may still be empty
        i -= 1
    end = days[i][0] if i >= 0 else None
    while i >= 0 and days[i][1] > 0:
        cur += 1
        first = days[i][0]
        i -= 1
    cur_rng = span(first, end) if cur else "-"
    return cur, cur_rng, best, best_rng


def card(w, h, inner):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="{FONT}"><rect width="{w}" height="{h}" rx="14" fill="{BG}" stroke="{LINE}"/>'
            f'{inner}</svg>')


def stats_svg(total, cur, longest):
    cols = [("contributions (1y)", total), ("current streak", f"{cur}d"), ("longest streak", f"{longest}d")]
    out = ""
    for i, (label, val) in enumerate(cols):
        x = 24 + i * 156
        out += (f'<text x="{x}" y="70" font-size="30" font-weight="700" fill="{RED}">{escape(str(val))}</text>'
                f'<text x="{x}" y="96" font-size="12" fill="{MUTE}">{escape(label)}</text>')
    out += f'<text x="24" y="34" font-size="13" fill="{INK}">activity</text>'
    return card(495, 120, out)


def langs_svg(by_bytes, by_repos):
    out = ""
    cols = [("by bytes", by_bytes, 24, True), ("by repos", by_repos, 330, False)]
    for title, data, x0, as_pct in cols:
        out += f'<text x="{x0}" y="34" font-size="12" fill="{MUTE}">{title}</text>'
        total = sum(n for _, n in data) or 1
        top = max([n for _, n in data] + [1])
        for i, (name, n) in enumerate(data):
            y = 54 + i * 26
            frac = n / total if as_pct else n / top
            label = f"{n * 100 / total:.0f}%" if as_pct else str(n)
            out += (f'<text x="{x0}" y="{y + 11}" font-size="12" fill="{INK}">{escape(name.lower())}</text>'
                    f'<rect x="{x0 + 90}" y="{y}" width="120" height="12" rx="6" fill="{LINE}"/>'
                    f'<rect x="{x0 + 90}" y="{y}" width="{max(6, 120 * frac):.0f}" height="12" rx="6" fill="{RED}"/>'
                    f'<text x="{x0 + 222}" y="{y + 11}" font-size="12" fill="{MUTE}">{label}</text>')
        if not data:
            out += f'<text x="{x0}" y="70" font-size="12" fill="{MUTE}">no public repos yet</text>'
    return card(620, 54 + 5 * 26 + 14, out)


RAMP = [(".", LINE), (":", "#7a2c3a"), ("+", "#b8344a"), ("#", "#e0405a"), ("@", RED)]


def heading_svg(title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="620" height="44" viewBox="0 0 620 44" '
            f'font-family="{FONT}"><text x="0" y="28" font-size="20" font-weight="700" fill="{RED}">'
            f'{escape(title)}</text><rect x="0" y="38" width="620" height="2" fill="{LINE}"/></svg>')


def streak_svg(cur, cur_rng, longest, longest_rng):
    out = ""
    for i, (label, val, rng) in enumerate([("current streak", cur, cur_rng), ("longest streak", longest, longest_rng)]):
        x = 40 + i * 300
        out += (f'<text x="{x}" y="62" font-size="44" font-weight="700" fill="{RED}">{val}</text>'
                f'<text x="{x + 12 + 26 * len(str(val))}" y="62" font-size="16" fill="{MUTE}">days</text>'
                f'<text x="{x}" y="90" font-size="13" fill="{INK}">{label}</text>'
                f'<text x="{x}" y="110" font-size="11" fill="{MUTE}">{escape(rng)}</text>')
    out += f'<rect x="310" y="28" width="1" height="84" fill="{LINE}"/>'
    return card(620, 134, out)


def year_svg(days):
    mx = max([c for _, c in days] + [1])
    out = ""
    for i, (_, c) in enumerate(days):
        level = 0 if c == 0 else min(4, 1 + (c * 4 - 1) // mx)
        ch, col = RAMP[level]
        out += (f'<text x="{20 + (i // 7) * 11}" y="{34 + (i % 7) * 16}" font-size="13" '
                f'fill="{col}">{escape(ch)}</text>')
    legend = "".join(f'<text x="{20 + k * 22}" y="164" font-size="13" fill="{col}">{escape(ch)}</text>'
                     for k, (ch, col) in enumerate(RAMP))
    out += legend + f'<text x="140" y="164" font-size="11" fill="{MUTE}">quiet to loud</text>'
    return card(620, 182, out)


def main():
    if "--demo" in sys.argv:
        t = date.today()
        days = [((t - timedelta(d)).isoformat(), 0 if d in (9, 20) else 2) for d in range(364, -1, -1)]
        total = sum(c for _, c in days)
        langs = ([("JavaScript", 5200), ("HTML", 3100), ("CSS", 1500), ("Python", 900)],
                 [("JavaScript", 4), ("HTML", 3), ("Python", 2), ("CSS", 1)])
    else:
        login, token = os.environ["GH_LOGIN"], os.environ["GITHUB_TOKEN"]
        total, days = get_days(login, token)
        langs = get_langs(login, token)
    cur, cur_rng, longest, longest_rng = streaks(days)
    open("stats.svg", "w").write(stats_svg(total, cur, longest))
    open("langs.svg", "w").write(langs_svg(*langs))
    open("streak.svg", "w").write(streak_svg(cur, cur_rng, longest, longest_rng))
    open("year.svg", "w").write(year_svg(days[-365:]))
    for name in ["about", "stack", "projects", "stats", "about-this-page"]:
        open(f"hd-{name}.svg", "w").write(heading_svg(name.replace("-", " ")))
    print("wrote stats, langs, streak, year and hd-*.svg")


if __name__ == "__main__":
    main()
