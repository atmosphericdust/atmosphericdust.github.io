#!/usr/bin/env python3
"""Build atmosphericdust.com — one page, generated from data/*.yml.

Usage:  python3 build.py
Needs:  Python 3.9+ and PyYAML  (pip install pyyaml)

Writes index.html, publications.bib, sitemap.xml and robots.txt.
"""

import html
import re
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is missing. Run:  pip install pyyaml")

ROOT = Path(__file__).parent
DATA = ROOT / "data"

# Change this line and --font in assets/style.css to swap the typeface.
FONT_LINK = ("https://fonts.googleapis.com/css2?"
             "family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400"
             "&amp;display=swap")

ME = ["Luka Ilić", "Ilić, Luka", "Ilić, L.", "Ilic, L."]

# source, kind, heading, anchor, on the home page?
GROUPS = [
    ("articles", "article", "Papers", "papers", True),
    ("chapters", "chapter", "Book chapters", "book-chapters", False),
    ("reports", "report", "CAMS reports", "reports", False),
    ("proceedings", "paper", "Conference papers", "conference-papers", False),
    ("abstracts", "abstract", "Conference abstracts", "conference-abstracts", False),
    ("theses", "thesis", "Thesis", "thesis", False),
    ("technical", "technical", "Technical solutions", "technical-solutions", False),
]

BIB_TYPE = {
    "article": "article", "report": "techreport", "paper": "inproceedings",
    "abstract": "inproceedings", "chapter": "incollection",
    "thesis": "phdthesis", "technical": "misc",
}


def load(name):
    with open(DATA / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def esc(text):
    return html.escape(str(text), quote=True)


def bold_me(authors):
    out = esc(authors)
    for variant in ME:
        pattern = re.escape(esc(variant)) + r"(?![\w])"
        new = re.sub(pattern, "<strong>" + esc(variant) + "</strong>", out, count=1)
        if new != out:
            return new
    return out


# --------------------------------------------------------------------------

def gallery(cfg, name):
    """A row of three images, used above Papers and above Field campaigns."""
    items = (cfg.get("galleries") or {}).get(name) or []
    if not items:
        return ""
    return '<div class="gallery" style="grid-template-columns:repeat(%d,1fr)">%s</div>' % (
        min(len(items), 3), "".join(
        '<img src="%s" alt="%s"%s loading="lazy">'
        % (esc(i["src"]), esc(i.get("alt", "")),
           (' style="object-position:%s"' % esc(i["position"])) if i.get("position") else "")
        for i in items))


def count_label(label, n):
    """'18 CAMS reports', '1 book chapter'."""
    text = label if label.startswith("CAMS") else label[0].lower() + label[1:]
    if n == 1 and text.endswith("s") and not text.endswith("sis"):
        text = text[:-1]
    return "%d %s" % (n, text)


def pub_li(entry):
    doi = entry.get("doi")
    url = entry.get("url")
    link = "https://doi.org/" + doi if doi else url

    title = esc(entry["title"])
    title = '<a href="%s">%s</a>' % (esc(link), title) if link else title

    bits = ['<span class="authors">%s</span> (%s). %s.' % (
        bold_me(entry.get("authors", "")), esc(entry["year"]), title)]

    tail = []
    if entry.get("venue"):
        tail.append("<em>%s</em>" % esc(entry["venue"]))
    if entry.get("details"):
        tail.append(esc(entry["details"]))
    if tail:
        bits.append('<span class="extra"> %s.</span>' % ", ".join(tail))

    return "<li>%s</li>" % "".join(bits)


def bib_authors(authors):
    parts = [p.strip() for p in authors.split(",") if p.strip()]
    names, i = [], 0
    initials = re.compile(r"^(?:[A-ZÀ-Þ]\.(?:\s*[-–]?\s*[A-ZÀ-Þ]\.)*|[A-ZÀ-Þ])$")
    while i < len(parts):
        part = parts[i]
        if part in {"…", "...", "et al.", "et al"}:
            names.append("others")
            i += 1
            continue
        if part.startswith(("…", "...")):
            names.append("others")
            part = part.lstrip("….").strip()
            parts[i] = part
        if i + 1 < len(parts) and initials.match(parts[i + 1].rstrip(".") + "."):
            names.append("%s, %s" % (part, parts[i + 1]))
            i += 2
        else:
            names.append(part)
            i += 1
    return " and ".join(names)


def bib_entry(entry, kind):
    fields = [("author", bib_authors(entry.get("authors", ""))),
              ("title", "{" + str(entry["title"]) + "}"),
              ("year", entry["year"])]
    venue = entry.get("venue", "")
    field = {"article": "journal", "paper": "booktitle", "abstract": "booktitle",
             "report": "institution", "chapter": "booktitle", "thesis": "school"}
    fields.append((field.get(kind, "howpublished"), venue))
    if entry.get("details"):
        fields.append(("note", entry["details"]))
    if entry.get("doi"):
        fields.append(("doi", entry["doi"]))
        fields.append(("url", "https://doi.org/" + entry["doi"]))
    elif entry.get("url"):
        fields.append(("url", entry["url"]))

    lines = ["@%s{%s," % (BIB_TYPE[kind], entry.get("key", "ref%s" % entry["year"]))]
    lines += ["  %-13s= {%s}," % (k, v) for k, v in fields if v]
    lines.append("}")
    return "\n".join(lines)


# --------------------------------------------------------------------------

def main():
    # python3 build.py --staging  ->  ask search engines to stay away
    staging = "--staging" in sys.argv
    noindex = '<meta name="robots" content="noindex, nofollow">\n' if staging else ""

    cfg = load("site.yml")
    cfg.update(load("articles.yml"))
    cfg.update(load("reports.yml"))
    cfg.update(load("conferences.yml"))
    site = cfg["site"]

    sections, full_sections, jump, bib, total, counts = [], [], [], [], 0, {}
    for source, kind, label, anchor, on_home in GROUPS:
        entries = sorted(cfg.get(source) or [], key=lambda e: (-int(e["year"]), e["title"]))
        if not entries:
            continue
        total += len(entries)
        counts[label] = len(entries)
        bib += [bib_entry(e, kind) for e in entries]
        block = ('<h2 id="%s">%s</h2>\n<ol class="pubs" reversed>%s</ol>'
                 % (anchor, esc(label), "".join(pub_li(e) for e in entries)))
        full_sections.append(block)
        if on_home:
            if source == "articles":
                sections.append(gallery(cfg, "papers"))
            jump.append('<a href="#%s">%s</a>' % (anchor, esc(label)))
            sections.append(block)

    rest = sum(n for label, n in counts.items()
               if label != "Papers")
    sections.append(
        '<p class="note">The remaining %d items — %s — are on the '
        '<a href="publications.html">complete publication list</a>.</p>'
        % (rest, ", ".join(count_label(label, n) for label, n in counts.items()
                           if label != "Papers")))

    photos = "".join(
        '<img src="%s" alt="%s"%s loading="lazy">'
        % (esc(p["src"]), esc(p["alt"]),
           (' style="object-position:%s"' % esc(p["position"])) if p.get("position") else "")
        for p in cfg.get("photos", []))

    toplinks = " | ".join(
        (['<a href="mailto:%s">Email</a>' % esc(site["email"])] if site.get("email") else [])
        + ['<a href="%s">%s</a>' % (esc(p["url"]), esc(p["name"])) for p in cfg["profiles"]])

    intro = "<p>%s</p>" % esc(cfg["intro"]) + "".join("<p>%s</p>" % esc(p) for p in cfg["bio"])

    projects = "".join(
        '<li><b>%s</b> <span class="when">%s</span><br>%s</li>' % (
            ('<a href="%s">%s</a>' % (esc(p["url"]), esc(p["name"]))) if p.get("url")
            else esc(p["name"]),
            esc(p["period"]), esc(p["body"]))
        for p in cfg["projects"])

    campaigns = "".join(
        '<li><b>%s</b> <span class="when">%s</span><br>%s</li>' % (
            ('<a href="%s">%s</a>' % (esc(c["url"]), esc(c["name"]))) if c.get("url")
            else esc(c["name"]),
            esc(c["where"]), esc(c["body"]))
        for c in cfg["campaigns"])

    def simple(items):
        return "".join(
            '<li>%s <span class="when">%s%s</span></li>' % (
                ('<a href="%s">%s</a>' % (esc(i["url"]), esc(i["title"]))) if i.get("url")
                else esc(i["title"]),
                esc(i.get("outlet", "")),
                (", " + esc(i["date"])) if i.get("date") else "")
            for i in items)

    vids = cfg.get("videos") or []
    videos_html = ""
    if vids:
        def player(v):
            if v.get("mp4"):
                return ('<video src="%s" controls preload="none" playsinline></video>'
                        % esc(v["mp4"]))
            return ('<iframe src="https://www.youtube-nocookie.com/embed/%s" title="%s"'
                    ' loading="lazy" allowfullscreen'
                    ' allow="accelerometer; clipboard-write; encrypted-media;'
                    ' picture-in-picture"></iframe>'
                    % (esc(v["id"]), esc(v["title"])))

        cards = "".join(
            '<figure><div class="embed">%s</div>'
            '<figcaption>%s<span class="when">%s</span></figcaption></figure>'
            % (player(v), esc(v["title"]), esc(v.get("outlet", "")))
            for v in vids)
        videos_html = ('<h2 id="videos">Videos</h2>\n<div class="videos">%s</div>\n\n' % cards)

    dp = cfg["dust_protocol"]
    dp_links = " · ".join('<a href="%s">%s</a>' % (esc(l["url"]), esc(l["name"]))
                          for l in dp["links"])

    jump_all = jump + ['<a href="#field-campaigns">Field campaigns</a>',
                       '<a href="#projects">Projects</a>',
                       '<a href="#talks">Talks</a>',
                       '<a href="#outreach">Outreach</a>',
                       '<a href="#videos">Videos</a>',
                       '<a href="#dust-protocol">The Dust Protocol</a>',
                       '<a href="publications.html">All publications</a>']

    page = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
%(noindex)s<title>%(name)s</title>
<meta name="description" content="%(desc)s">
<meta property="og:title" content="%(name)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:type" content="website">
<meta property="og:url" content="%(base)s">
<link rel="canonical" href="%(base)s">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="%(font)s" rel="stylesheet">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>

%(logo)s
<h1>%(name)s</h1>
%(subtitle)s
<p class="toplinks">%(toplinks)s</p>
<div class="photos">%(photos)s</div>
<p class="jump">Jump to: %(jump)s</p>

%(intro)s

%(sections)s

%(campaign_gallery)s
<h2 id="field-campaigns">Field campaigns</h2>
<ul class="plain">%(campaigns)s</ul>

<h2 id="projects">Projects</h2>
<ul class="plain">%(projects)s</ul>

<h2 id="talks">Talks</h2>
<p class="note">Invited and contributed talks, seminars and public lectures.</p>
<ul class="plain">%(talks)s</ul>

<h2 id="outreach">Outreach</h2>
<h3>Interviews</h3>
<ul class="plain">%(interviews)s</ul>
<h3>Press</h3>
<ul class="plain">%(press)s</ul>

%(videos)s<h2 id="dust-protocol">The Dust Protocol</h2>
<p>%(dp_desc)s</p>
<p>%(dp_links)s</p>

</body>
</html>
""" % {
        "noindex": noindex,
        "logo": ('<img class="logo" src="%s" alt="Atmospheric Dust">' % esc(cfg["logo"]))
                if cfg.get("logo") else "",
        "subtitle": ('<p class="subtitle">%s</p>' % esc(cfg["subtitle"]))
                    if cfg.get("subtitle") else "",
        "name": esc(site["name"]), "desc": esc(site["description"]),
        "base": esc(site["base_url"]), "font": FONT_LINK,
        "toplinks": toplinks, "photos": photos,
        "jump": " | ".join(jump_all), "intro": intro,
        "sections": "\n\n".join(sections),
        "projects": projects, "campaigns": campaigns,
        "campaign_gallery": gallery(cfg, "campaigns"),
        "interviews": simple(cfg["interviews"]), "press": simple(cfg["press"]),
        "talks": simple(cfg["talks"]),
        "videos": videos_html,
        "dp_desc": esc(dp["description"]), "dp_links": dp_links,
        "orcid": esc(site["orcid"]), "total": total,
        "today": date.today().isoformat(),
    }

    (ROOT / "index.html").write_text(page, encoding="utf-8")

    full = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
%(noindex)s<title>Publications — %(name)s</title>
<meta name="description" content="Complete list of %(total)d publications by %(name)s.">
<link rel="canonical" href="%(base)s/publications.html">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="%(font)s" rel="stylesheet">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>

%(logo)s
<h1>Publications</h1>
<p class="toplinks"><a href="index.html">&#8592; %(name)s</a> ·
<a href="publications.bib">BibTeX</a> ·
<a href="https://orcid.org/%(orcid)s">ORCID</a></p>
<p class="jump">%(total)d items: %(breakdown)s.</p>
<p class="jump">Jump to: %(jump)s</p>

%(sections)s

<footer>
<p><a href="index.html">Back to %(name)s</a></p>
</footer>

</body>
</html>
""" % {
        "noindex": noindex,
        "logo": ('<a href="index.html"><img class="logo" src="%s" alt="Atmospheric Dust"></a>'
                 % esc(cfg["logo"])) if cfg.get("logo") else "",
        "name": esc(site["name"]), "base": esc(site["base_url"]), "font": FONT_LINK,
        "total": total,
        "breakdown": ", ".join(count_label(label, n) for label, n in counts.items()),
        "jump": " | ".join(
            '<a href="#%s">%s</a>' % (anchor, esc(label))
            for _, _, label, anchor, _ in GROUPS if counts.get(label)),
        "sections": "\n\n".join(full_sections),
        "orcid": esc(site["orcid"]), "today": date.today().isoformat(),
    }
    (ROOT / "publications.html").write_text(full, encoding="utf-8")
    (ROOT / "publications.bib").write_text(
        "%% Publications of %s — generated %s\n\n" % (site["name"], date.today().isoformat())
        + "\n\n".join(bib) + "\n", encoding="utf-8")
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>%s</loc><lastmod>%s</lastmod></url></urlset>\n"
        % (site["base_url"], date.today().isoformat()), encoding="utf-8")
    (ROOT / "robots.txt").write_text(
        "User-agent: *\nDisallow: /\n" if staging else
        "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % site["base_url"],
        encoding="utf-8")

    print("Built index.html and publications.html — %d publications.%s"
          % (total, "  [staging: noindex]" if staging else ""))


if __name__ == "__main__":
    main()
