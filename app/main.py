from __future__ import annotations
import os, socket, ipaddress, hashlib, sqlite3, html, re
from urllib.parse import urlparse, urljoin, urlencode
import httpx
from bs4 import BeautifulSoup, NavigableString
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

APP_NAME = "WebTranslate AI"
CACHE_DB = os.getenv("CACHE_DB", "/tmp/cache.sqlite")
LT_URL = os.getenv("LIBRETRANSLATE_URL", "").rstrip("/")
LT_KEY = os.getenv("LIBRETRANSLATE_KEY", "")
MYMEMORY_EMAIL = os.getenv("MYMEMORY_EMAIL", "")
MAX_HTML_BYTES = 2_000_000
TIMEOUT = 15
app = FastAPI(title=APP_NAME)
LANGS = {"auto":"Auto","en":"English","vi":"Tiếng Việt","zh":"中文","ja":"日本語","ko":"한국어","fr":"Français","de":"Deutsch","es":"Español","th":"ไทย","ru":"Русский","pt":"Português","it":"Italiano","ar":"العربية"}
SKIP_TAGS = {"script","style","noscript","code","pre","svg","math","textarea"}
ATTRS = {"alt","title","placeholder","aria-label"}

def validate_url(raw: str) -> str:
    p = urlparse(raw)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise HTTPException(400, "Chỉ chấp nhận URL http/https hợp lệ, không chứa thông tin đăng nhập.")
    if p.port and p.port not in (80, 443):
        raise HTTPException(400, "MVP chỉ hỗ trợ cổng 80/443.")
    host = p.hostname.lower().rstrip(".")
    if host in ("localhost", "localhost.localdomain") or host.endswith(".localhost"):
        raise HTTPException(403, "Chặn hostname nội bộ.")
    try:
        ips = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            ips = {ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80))}
        except socket.gaierror:
            raise HTTPException(400, "Không phân giải được hostname.")
    if not ips or any(not ip.is_global for ip in ips):
        raise HTTPException(403, "Chặn IP nội bộ/không công khai.")
    return raw

def db():
    os.makedirs(os.path.dirname(CACHE_DB) or ".", exist_ok=True)
    c = sqlite3.connect(CACHE_DB)
    c.execute("CREATE TABLE IF NOT EXISTS translations (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    return c

def cache_key(text, src, tgt):
    return hashlib.sha256(f"{src}|{tgt}|{text}".encode()).hexdigest()

def cached(text, src, tgt):
    with db() as c:
        row = c.execute("SELECT value FROM translations WHERE key=?", (cache_key(text, src, tgt),)).fetchone()
    return row[0] if row else None

def cache_put(text, src, tgt, val):
    with db() as c:
        c.execute("INSERT OR REPLACE INTO translations(key,value) VALUES(?,?)", (cache_key(text, src, tgt), val))

def split_bytes(text, limit=450):
    chunks, cur = [], ""
    for part in re.split(r"(?<=[.!?。！？])\s+|\n", text):
        if not part:
            continue
        if len((cur + " " + part).encode("utf-8")) <= limit:
            cur = (cur + " " + part).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = ""
            if len(part.encode("utf-8")) <= limit:
                cur = part
            else:
                for ch in part:
                    if len((cur + ch).encode("utf-8")) > limit:
                        chunks.append(cur)
                        cur = ch
                    else:
                        cur += ch
    if cur:
        chunks.append(cur)
    return chunks or [text]

async def translate_text(text, source, target):
    original, text = text, text.strip()
    if not text or source == target:
        return original
    old = cached(text, source, target)
    if old is not None:
        return old
    if LT_URL:
        payload = {"q": text, "source": source, "target": target, "format": "text"}
        if LT_KEY:
            payload["api_key"] = LT_KEY
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.post(f"{LT_URL}/translate", json=payload)
            r.raise_for_status()
            result = r.json().get("translatedText", text)
    else:
        if source == "auto":
            source = "en"  # MyMemory API requires an explicit source language.
        result_parts = []
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            for part in split_bytes(text):
                params = {"q": part, "langpair": f"{source}|{target}", "mt": "1"}
                if MYMEMORY_EMAIL:
                    params["de"] = MYMEMORY_EMAIL
                r = await c.get("https://api.mymemory.translated.net/get", params=params)
                r.raise_for_status()
                data = r.json()
                if data.get("responseStatus") != 200 or data.get("quotaFinished"):
                    raise RuntimeError(data.get("responseDetails", "MyMemory quota exceeded"))
                result_parts.append(data.get("responseData", {}).get("translatedText", part))
        result = " ".join(result_parts)
    cache_put(text, source, target, result)
    return result

async def fetch_html(url):
    current = validate_url(url)
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False, headers={"User-Agent": "WebTranslateAI/0.2"}) as c:
        for _ in range(5):
            validate_url(current)
            resp = await c.get(current)
            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("location")
                if not loc:
                    break
                current = validate_url(urljoin(current, loc))
                continue
            resp.raise_for_status()
            if "text/html" not in resp.headers.get("content-type", ""):
                raise HTTPException(415, "URL không trả về HTML.")
            if len(resp.content) > MAX_HTML_BYTES:
                raise HTTPException(413, "HTML vượt giới hạn 2 MB.")
            return resp.text, current
    raise HTTPException(400, "Redirect quá nhiều hoặc URL không hợp lệ.")

async def translate_document(source_html, source_url, source_lang, target_lang):
    soup = BeautifulSoup(source_html, "html.parser")
    if soup.head and not soup.find("base"):
        soup.head.insert(0, soup.new_tag("base", href=source_url))
    for node in list(soup.find_all(string=True)):
        if not isinstance(node, NavigableString) or not node.parent:
            continue
        if any(getattr(p, "name", None) in SKIP_TAGS for p in [node.parent, *node.parent.parents]):
            continue
        text = str(node)
        if text.strip():
            try:
                node.replace_with(await translate_text(text, source_lang, target_lang))
            except Exception:
                pass
    for tag in soup.find_all(True):
        if tag.name in SKIP_TAGS:
            continue
        for attr in ATTRS:
            val = tag.get(attr)
            if isinstance(val, str) and val.strip():
                try:
                    tag[attr] = await translate_text(val, source_lang, target_lang)
                except Exception:
                    pass
        for attr in ("src", "poster"):
            val = tag.get(attr)
            if val and not val.startswith(("data:", "blob:", "#")):
                tag[attr] = urljoin(source_url, val)
        if tag.name == "a" and tag.get("href"):
            href = tag["href"]
            if not href.startswith(("#", "mailto:", "tel:", "javascript:")):
                dest = urljoin(source_url, href)
                tag["href"] = "/translate?" + urlencode({"url": dest, "target": target_lang, "source": source_lang})
    for tag in soup.find_all(["script", "iframe", "object", "embed"]):
        tag.decompose()
    return str(soup)

@app.get("/", response_class=HTMLResponse)
def index():
    source_options = "".join(f'<option value="{k}" {"selected" if k == "en" else ""}>{v}</option>' for k, v in LANGS.items())
    target_options = "".join(f'<option value="{k}" {"selected" if k == "vi" else ""}>{v}</option>' for k, v in LANGS.items() if k != "auto")
    return HTMLResponse(f"""<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WebTranslate AI</title>
<style>*{{box-sizing:border-box}}body{{font:16px system-ui;background:radial-gradient(ellipse at top,#e2edff,#f5f7fb 55%);color:#14243a;margin:0;min-height:100vh;display:grid;place-items:center;padding:20px}}main{{background:#fff;padding:clamp(22px,5vw,42px);border-radius:24px;box-shadow:0 18px 60px #10203018;width:min(700px,100%)}}h1{{margin:0;font-size:clamp(28px,5vw,38px)}}.tag{{color:#1b65d5;font-weight:700}}input,select,button{{width:100%;padding:14px;border:1px solid #cbd5e1;border-radius:12px;margin:8px 0;font:inherit}}button{{background:#1c63d5;color:white;border:0;font-weight:700;cursor:pointer}}label{{font-weight:600}}.row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.hint{{font-size:13px;color:#64748b;line-height:1.55}}@media(max-width:520px){{.row{{grid-template-columns:1fr}}}}</style>
<main><div class="tag">🌐 WebTranslate AI · Free MVP</div><h1>Dịch website, giữ bố cục</h1><p>Nhập link để tạo bản dịch. Ảnh và kiểu trang được giữ ở mức khả thi.</p><form action="/translate"><label>Đường link website</label><input name="url" required type="url" placeholder="https://example.com"><div class="row"><div><label>Ngôn ngữ gốc</label><select name="source">{source_options}</select></div><div><label>Dịch sang</label><select name="target">{target_options}</select></div></div><button type="submit">Dịch trang →</button></form><p class="hint">Dịch miễn phí qua MyMemory có hạn mức khoảng 5.000 ký tự/ngày (tùy nhà cung cấp). Chọn ngôn ngữ nguồn cụ thể để dịch chính xác hơn. Nếu tự host LibreTranslate, cấu hình LIBRETRANSLATE_URL để sử dụng máy dịch riêng. MVP tắt JavaScript/iframe nhằm tăng an toàn, vì vậy trang động phức tạp có thể không hoạt động.</p></main></html>""")

@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME}

@app.get("/translate", response_class=HTMLResponse)
async def translate(url: str = Query(...), target: str = "vi", source: str = "en"):
    validate_url(url)
    if target not in LANGS or target == "auto":
        raise HTTPException(400, "Ngôn ngữ đích không hợp lệ.")
    if source not in LANGS:
        raise HTTPException(400, "Ngôn ngữ nguồn không hợp lệ.")
    try:
        raw, final_url = await fetch_html(url)
        return HTMLResponse(await translate_document(raw, final_url, source, target))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Tải hoặc dịch không thành công: {html.escape(str(exc)[:140]})")
