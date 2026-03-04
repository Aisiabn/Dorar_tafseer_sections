"""
موسوعة التفسير — dorar.net
مخرجان في زحفة واحدة:
  ① dorar_tafseer_output/by_section/       — ملف لكل نوع قسم
  ② dorar_tafseer_output/tafseer_sections/ — ملف لكل عنوان title-1
"""

import requests
from bs4 import BeautifulSoup
import re, time, os, traceback
from collections import defaultdict
from difflib import SequenceMatcher

BASE    = "https://dorar.net"
INDEX   = "https://dorar.net/tafseer"
DELAY   = 1.2
OUT_DIR = "dorar_tafseer_output"
DIR_A   = os.path.join(OUT_DIR, "by_section")
DIR_B   = os.path.join(OUT_DIR, "tafseer_sections")

_val        = os.environ.get("TEST_SURAHS", "None")
TEST_SURAHS = None if _val == "None" else int(_val)

SURAH_RE   = re.compile(r"^/tafseer/(\d+)$")
SECTION_RE = re.compile(r"^/tafseer/(\d+)/(\d+)$")
TASHKEEL   = re.compile(
    r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC'
    r'\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]'
)
_TIP_RE = re.compile(r'\x01(\d+)\x01')
_T1_RE  = re.compile(r'\x02(.*?)\x03', re.DOTALL)


# ══════════════════════════════════════════════
# أدوات مشتركة
# ══════════════════════════════════════════════

_known_keys: list = []

def normalize(text):
    text = TASHKEEL.sub('', text)
    text = re.sub(r'[أإآٱ]', 'ا', text)
    text = re.sub(r'ى', 'ي', text)
    return re.sub(r'\s+', ' ', text).strip()

def fuzzy_key(heading, threshold=0.82):
    norm = normalize(heading)
    best_score, best_key = 0.0, None
    for k in _known_keys:
        s = SequenceMatcher(None, norm, k).ratio()
        if s > best_score:
            best_score, best_key = s, k
    if best_score >= threshold:
        return best_key
    _known_keys.append(norm)
    return norm

def safe_filename(text):
    text = TASHKEEL.sub('', text)
    text = re.sub(r'[\\/:*?"<>|]', '', text).strip().rstrip(':').strip()
    return text[:80] or "قسم"

def convert_inner_soup(soup_tag):
    """تحويل العناصر الداخلية في كائن BeautifulSoup"""
    for inner in soup_tag.find_all("span", class_="aaya"):
        inner.replace_with(f"﴿{inner.get_text(strip=True)}﴾")
    for inner in soup_tag.find_all("span", class_="hadith"):
        inner.replace_with(f"«{inner.get_text(strip=True)}»")
    for inner in soup_tag.find_all("span", class_="sora"):
        t = inner.get_text(strip=True)
        if t:
            inner.replace_with(f" {t} ")

def get_tip_text(tip):
    """
    استخراج نص الحاشية مع الحفاظ على أقواس الآيات.
    الـ attribute قد يحتوي على HTML — نُحلّله قبل استخراج النص.
    markers الحواشي المتداخلة \x01N\x01 تُحذف من النص النهائي.
    """
    _marker = re.compile(r'\x01\d+\x01')
    for attr in ("data-original-title", "title", "data-content", "data-tippy-content"):
        val = tip.get(attr, "").strip()
        if val:
            inner_soup = BeautifulSoup(val, "html.parser")
            convert_inner_soup(inner_soup)
            result = re.sub(r'\s+', ' ', inner_soup.get_text()).strip()
            return _marker.sub('', result).strip()
    # fallback: استخرج من DOM مباشرة
    convert_inner_soup(tip)
    result = re.sub(r'\s+', ' ', tip.get_text(strip=True)).strip()
    return _marker.sub('', result).strip()

def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent"               : "Mozilla/5.0 (Windows NT 6.1; WOW64) "
                                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                                     "Chrome/109.0.0.0 Safari/537.36",
        "Accept"                   : "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language"          : "ar,en-US;q=0.9,en;q=0.8",
        "Connection"               : "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    return s

def get_page(session, url, referer=INDEX):
    session.headers["Referer"] = referer
    try:
        r = session.get(url, timeout=20)
        print(f"  [{r.status_code}] {url}")
        return r.text if r.status_code == 200 else ""
    except Exception as e:
        print(f"  [ERR] {url} — {e}")
        return ""


# ══════════════════════════════════════════════
# روابط وتنقل
# ══════════════════════════════════════════════

def get_surah_links(html):
    soup = BeautifulSoup(html, "html.parser")
    links, seen = [], set()
    for card in soup.find_all("div", class_="card-personal"):
        a = card.find("a", href=SURAH_RE)
        if not a:
            continue
        href  = a["href"]
        title = a.get_text(strip=True)
        if href in seen or not title:
            continue
        seen.add(href)
        num = int(SURAH_RE.match(href).group(1))
        links.append({"url": BASE + href, "title": title, "num": num})
    links.sort(key=lambda x: x["num"])
    return links

def get_first_section_link(html, surah_num):
    soup  = BeautifulSoup(html, "html.parser")
    cands = []
    for a in soup.find_all("a", href=SECTION_RE):
        m = SECTION_RE.match(a["href"])
        if m and int(m.group(1)) == surah_num:
            cands.append((int(m.group(2)), BASE + a["href"]))
    if cands:
        cands.sort()
        return cands[0][1]
    return None

def get_next_link(html):
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=SECTION_RE):
        if "التالي" in a.get_text():
            return BASE + a["href"]
    return None

def get_page_title(html):
    soup = BeautifulSoup(html, "html.parser")
    og   = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].split(" - ", 1)[-1].strip()
    t = soup.find("title")
    if t:
        return t.get_text().split(" - ")[-1].strip()
    return ""


# ══════════════════════════════════════════════
# إعادة الترقيم (مشتركة)
# ══════════════════════════════════════════════

def renum(text, fns, global_fn_ref):
    if not fns:
        return text, []

    local_map = {}
    for fn in fns:
        m = re.match(r'\[\^(\d+)\]:', fn)
        if m and m.group(1) not in local_map:
            local_map[m.group(1)] = global_fn_ref[0]
            global_fn_ref[0] += 1

    for loc in local_map:
        text = re.sub(
            rf'(?<!\d)\[\^{re.escape(loc)}\](?!\d)',
            f'\x04{loc}\x04', text
        )
    for loc, gbl in local_map.items():
        text = text.replace(f'\x04{loc}\x04', f'[^{gbl}]')

    new_fns = []
    for fn in fns:
        m = re.match(r'\[\^(\d+)\]:(.*)', fn, re.DOTALL)
        if m:
            gbl = local_map.get(m.group(1))
            if gbl:
                new_fns.append(f"[^{gbl}]:{m.group(2)}")
    return text, new_fns


# ══════════════════════════════════════════════
# المُستخرِج الأول: مقالات (article + h5)
# ══════════════════════════════════════════════

def extract_articles(html):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(["nav", "header", "footer", "script", "style", "form"]):
        tag.decompose()
    for pat in [re.compile(p) for p in [
        r"\bmodal\b", r"\breadMore\b", r"\balert-dorar\b",
        r"\bcard-personal\b", r"\bdefault-gradient\b", r"\bfooter-copyright\b",
    ]]:
        for tag in soup.find_all(True, class_=pat):
            tag.decompose()

    results = []

    for block in soup.find_all("article"):
        h_tag   = block.find(["h5", "h4", "h3"])
        heading = h_tag.get_text(strip=True) if h_tag else ""
        if h_tag:
            h_tag.decompose()
        if not heading:
            continue

        # ── 1. استخرج الحواشي أولاً — معالجة عكسية لحل مشكلة التداخل ──
        tips_map    = {}
        tip_counter = [1]
        for tip in reversed(list(block.find_all("span", class_="tip"))):
            tip_text = get_tip_text(tip)
            if tip_text:
                tips_map[tip_counter[0]] = tip_text
                tip.replace_with(f"\x01{tip_counter[0]}\x01")
                tip_counter[0] += 1
            else:
                tip.decompose()

        # ── 2. بقية التحويلات ──
        for span in block.find_all("span", class_="aaya"):
            span.replace_with(f"﴿{span.get_text(strip=True)}﴾")
        for span in block.find_all("span", class_="sora"):
            span.replace_with(f" {span.get_text(strip=True)} ")
        for span in block.find_all("span", class_="hadith"):
            span.replace_with(f"«{span.get_text(strip=True)}»")
        for span in block.find_all("span", class_="title-2"):
            span.replace_with(f"\n#### {span.get_text(strip=True)}\n")
        for a in block.find_all("a"):
            if re.search(r"السابق|التالي|الصفحة|المراجع|اعتماد", a.get_text()):
                a.decompose()
        for i in range(1, 7):
            for h in block.find_all(f"h{i}"):
                h.replace_with(f"\n{'#'*(i+2)} {h.get_text(strip=True)}\n")
        for br in block.find_all("br"):
            br.replace_with("\n")
        for p in block.find_all("p"):
            p.insert_before("\n\n")
            p.insert_after("\n\n")

        # ── 3. استخرج النص واستبدل العلامات ──
        text      = block.get_text(separator="\n", strip=False)
        footnotes = []
        local_fn  = [1]

        def replace_marker(m, _tips=tips_map, _fns=footnotes, _ctr=local_fn):
            tid  = int(m.group(1))
            body = _tips.get(tid, '')
            _fns.append(f"[^{_ctr[0]}]: {body}")
            ref  = f" [^{_ctr[0]}]"
            _ctr[0] += 1
            return ref

        text = _TIP_RE.sub(replace_marker, text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'(?<!\n)\n(?![\n#>﴿«])', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()

        if text:
            results.append({"heading": heading, "text": text, "footnotes": footnotes})

    return results


# ══════════════════════════════════════════════
# المُستخرِج الثاني: title-1
# ══════════════════════════════════════════════

def extract_title1_blocks(html):
    soup   = BeautifulSoup(html, "html.parser")
    blocks = []

    for article in soup.find_all("article", class_="border-bottom"):
        h5 = article.find("h5", class_="default-text-color")
        if not h5 or "modal-title" in h5.get("class", []):
            continue
        l3_heading = h5.get_text(strip=True)

        paragraphs = article.find_all("p")
        if not paragraphs:
            continue

        # ── 1. استخرج كل الحواشي من كل الفقرات — معالجة عكسية لحل مشكلة التداخل ──
        tips_map    = {}
        tip_counter = [1]
        for p in paragraphs:
            for tip in reversed(list(p.find_all("span", class_="tip"))):
                tip_text = get_tip_text(tip)
                if tip_text:
                    tips_map[tip_counter[0]] = tip_text
                    tip.replace_with(f"\x01{tip_counter[0]}\x01")
                    tip_counter[0] += 1
                else:
                    tip.decompose()

        # ── 2. علّم title-1 وحوّل بقية العناصر ──
        for p in paragraphs:
            for span in p.find_all("span", class_="title-1"):
                span.replace_with(f"\x02{span.get_text(strip=True)}\x03")
            for span in p.find_all("span", class_="aaya"):
                span.replace_with(f"﴿{span.get_text(strip=True)}﴾")
            for span in p.find_all("span", class_="hadith"):
                span.replace_with(f"«{span.get_text(strip=True)}»")
            for span in p.find_all("span", class_="sora"):
                t = span.get_text(strip=True)
                if t:
                    span.replace_with(f" {t} ")
            for br in p.find_all("br"):
                br.replace_with("\n")

        # ── 3. اجمع نص كل الفقرات ──
        raw   = "\n\n".join(p.get_text(separator="") for p in article.find_all("p"))
        raw   = re.sub(r'[ \t]+', ' ', raw)
        parts = _T1_RE.split(raw)

        i = 1
        while i + 1 < len(parts):
            title_text = parts[i].strip()
            seg_raw    = parts[i + 1]
            i += 2

            if not title_text:
                continue

            local_fn  = [1]
            local_fns = []
            seen_tips = {}

            def replace_tip(m, _tips=tips_map, _seen=seen_tips,
                            _fns=local_fns, _ctr=local_fn):
                tid = int(m.group(1))
                if tid not in _seen:
                    _seen[tid] = _ctr[0]
                    _fns.append(f"[^{_ctr[0]}]: {_tips.get(tid, '')}")
                    _ctr[0] += 1
                return f" [^{_seen[tid]}]"

            seg_text = _TIP_RE.sub(replace_tip, seg_raw)
            seg_text = re.sub(r'\n{3,}', '\n\n', seg_text).strip()

            if not seg_text and not local_fns:
                continue

            blocks.append({
                "key"      : fuzzy_key(title_text),
                "display"  : title_text,
                "l3"       : l3_heading,
                "text"     : seg_text,
                "footnotes": local_fns,
            })

    return blocks


# ══════════════════════════════════════════════
# الزحف الموحّد
# ══════════════════════════════════════════════

def crawl_all(session, surah_links):
    db_a            = defaultdict(list)
    heading_display = {}
    db_b            = {}

    for surah in surah_links:
        snum, stitle, surl = surah["num"], surah["title"], surah["url"]
        print(f"\n{'='*55}\n[{snum:3d}] {stitle}")

        html_s = get_page(session, surl, referer=INDEX)
        time.sleep(DELAY)
        if not html_s:
            continue

        _feed_a(db_a, heading_display, extract_articles(html_s),
                stitle, snum, f"تعريف {stitle}", surl)
        _feed_b(db_b, extract_title1_blocks(html_s),
                stitle, f"تعريف {stitle}")

        first_url = get_first_section_link(html_s, snum)
        if not first_url:
            print("  ⚠ لا مقاطع")
            continue

        next_url, visited = first_url, set()
        sec_num = 1
        while next_url and next_url not in visited:
            visited.add(next_url)
            html_p = get_page(session, next_url, referer=surl)
            time.sleep(DELAY)
            if not html_p:
                break
            ptitle = get_page_title(html_p)
            print(f"    [{sec_num:3d}] {ptitle[:50]}")

            _feed_a(db_a, heading_display, extract_articles(html_p),
                    stitle, snum, ptitle, next_url)
            _feed_b(db_b, extract_title1_blocks(html_p),
                    stitle, ptitle)

            next_url = get_next_link(html_p)
            sec_num += 1

    return db_a, heading_display, db_b


def _feed_a(db, display_map, articles, stitle, snum, ptitle, url):
    for art in articles:
        key = fuzzy_key(art["heading"])
        if key not in display_map:
            display_map[key] = art["heading"]
        db[key].append({
            "surah"     : stitle,
            "surah_num" : snum,
            "page_title": ptitle,
            "url"       : url,
            "text"      : art["text"],
            "footnotes" : art["footnotes"],
        })

def _feed_b(db, blocks, stitle, ptitle):
    for blk in blocks:
        k = blk["key"]
        if k not in db:
            db[k] = {"display": blk["display"], "entries": []}
        db[k]["entries"].append({
            "surah"      : stitle,
            "page_title" : ptitle,
            "l3"         : blk["l3"],
            "text"       : blk["text"],
            "footnotes"  : blk["footnotes"],
        })


# ══════════════════════════════════════════════
# الحفظ — المخرج الأول (by_section)
# ══════════════════════════════════════════════

def save_by_section(db_a, heading_display):
    os.makedirs(DIR_A, exist_ok=True)
    index_lines = [f"# فهرس أقسام التفسير\n\n> {len(db_a)} قسم\n\n---\n\n"]

    for key, entries in sorted(db_a.items(), key=lambda x: -len(x[1])):
        heading  = heading_display.get(key, key)
        safe     = re.sub(r'[^\w\u0600-\u06FF]', '_', key)[:60]
        filepath = os.path.join(DIR_A, f"{safe}.md")
        n_surahs = len(set(e["surah_num"] for e in entries))

        global_fn_ref = [1]
        all_footnotes = []
        lines = [
            f"# {heading}\n\n",
            f"> {len(entries)} موضع — {n_surahs} سورة\n\n",
            "---\n\n",
        ]

        for e in sorted(entries, key=lambda x: x["surah_num"]):
            lines.append(f"## {e['surah']} — {e['page_title']}\n\n")
            lines.append(f"> {e['url']}\n\n")
            text, fns = renum(e["text"], e.get("footnotes", []), global_fn_ref)
            lines.append(f"{text}\n\n---\n\n")
            all_footnotes.extend(fns)

        if all_footnotes:
            lines.append("\n")
            for fn in all_footnotes:
                lines.append(f"{fn}\n")

        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)

        total_chars = sum(len(e["text"]) for e in entries)
        print(f"  ✔ [A] {heading[:35]:35s}  {len(entries):4d} موضع  "
              f"~{total_chars//1024} KB  {len(all_footnotes)} حاشية")
        index_lines.append(f"- [{heading}](./{safe}.md) — {len(entries)} موضع\n")

    with open(os.path.join(DIR_A, "فهرس.md"), "w", encoding="utf-8") as f:
        f.writelines(index_lines)
    print(f"\n✔ فهرس.md — {len(db_a)} قسم")


# ══════════════════════════════════════════════
# الحفظ — المخرج الثاني (tafseer_sections)
# ══════════════════════════════════════════════

def save_sections(db_b):
    os.makedirs(DIR_B, exist_ok=True)

    for key, info in db_b.items():
        display, entries = info["display"], info["entries"]
        fpath = os.path.join(DIR_B, safe_filename(display) + ".md")

        global_fn_ref = [1]
        all_footnotes = []
        lines = [
            f"# {display}\n\n",
            f"> المصدر: موسوعة التفسير — dorar.net  \n",
            f"> عدد المقاطع: {len(entries)}\n\n",
            "---\n\n",
        ]

        current_surah = None
        for entry in entries:
            if entry["surah"] != current_surah:
                current_surah = entry["surah"]
                lines.append(f"\n## سورة {current_surah}\n\n")

            lines.append(f"### {entry['page_title']}\n")
            lines.append(f"*ضمن: {entry['l3']}*\n\n")

            text, fns = renum(entry["text"], entry["footnotes"], global_fn_ref)
            if text:
                lines.append(f"{text}\n\n")
            all_footnotes.extend(fns)
            lines.append("---\n\n")

        if all_footnotes:
            lines.append("\n## الحواشي\n\n")
            for fn in all_footnotes:
                lines.append(f"{fn}\n")

        with open(fpath, "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"  ✔ [B] {safe_filename(display)}.md  "
              f"({len(entries)} مقطع، {len(all_footnotes)} حاشية)")

    print(f"\n✔ {len(db_b)} ملف في {DIR_B}/")


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

if __name__ == "__main__":
    try:
        session = make_session()

        print("① تهيئة الجلسة...")
        get_page(session, INDEX, referer=BASE)
        time.sleep(1.5)

        print("\n② جلب الصفحة الرئيسية...")
        html_main = get_page(session, INDEX, referer=BASE)
        time.sleep(2)
        if not html_main:
            raise SystemExit("فشل جلب الصفحة الرئيسية")

        surah_links = get_surah_links(html_main)
        print(f"\n③ {len(surah_links)} سورة مكتشفة")

        if TEST_SURAHS:
            surah_links = surah_links[:TEST_SURAHS]
            print(f"   وضع الاختبار: أول {TEST_SURAHS} سور فقط\n")

        print("\n④ الزحف (زحفة واحدة — مخرجان)...")
        db_a, heading_display, db_b = crawl_all(session, surah_links)

        print(f"\n⑤ حفظ {len(db_a)} قسم في {DIR_A}/...")
        save_by_section(db_a, heading_display)

        print(f"\n⑥ حفظ {len(db_b)} قسم في {DIR_B}/...")
        save_sections(db_b)

        print("\n✔ اكتمل.")

    except SystemExit as e:
        print(e)
    except Exception:
        traceback.print_exc()