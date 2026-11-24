#!/usr/bin/env python3
"""
Extractor automático v2 — Liga de Softbol VENEZUELA-UNIMET (beisbolysoftbol.com)
================================================================================
Mejoras v2:
  - Parser HTML con pila de tablas (soporta tablas anidadas sin perder Pitcheo ni Defensiva).
  - Detecta todos los alias de columnas en español de Pitcheo y Defensiva (IL/EL/IP, JG/JP/JS,
    PO/AS/E/DP/EJ/PDF/AL CAMPO) y lee `roster.php` para capturar rosters completos (incluso en T90).
  - Extrae también estadísticas de pitcheo y defensa desde `jugador.php` como respaldo automático.
  - Imprime diagnóstico claro en GitHub Actions si alguna tabla viene vacía.
"""

import html
import json
import re
import sys
import time
import unicodedata
import http.cookiejar
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_SITE = "https://beisbolysoftbol.com/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-VE,es;q=0.9,en;q=0.8",
}


def norm_text(s: str) -> str:
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(s))
    asc = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", asc).strip().lower()


def clean_cell(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(s or ""))).strip()


_COOKIE_JAR = http.cookiejar.CookieJar()
_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_COOKIE_JAR))


def fetch_html(url: str, retries: int = 3, referer: str = "") -> str:
    full_url = url if url.startswith("http") else urllib.parse.urljoin(BASE_SITE, url.lstrip("/"))
    parsed = urllib.parse.urlsplit(full_url)
    safe_url = urllib.parse.urlunsplit((
        parsed.scheme, parsed.netloc,
        urllib.parse.quote(parsed.path, safe="/"),
        urllib.parse.quote(parsed.query, safe="=&%+-_."),
        parsed.fragment,
    ))
    hdrs = dict(HEADERS)
    hdrs["Referer"] = referer or BASE_SITE
    req = urllib.request.Request(safe_url, headers=hdrs)
    for attempt in range(retries + 1):
        try:
            with _OPENER.open(req, timeout=30) as resp:
                raw = resp.read()
                try:
                    txt = raw.decode("utf-8")
                except UnicodeDecodeError:
                    txt = raw.decode("latin-1", errors="replace")
                if len(txt.strip()) < 80 and attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return txt
        except urllib.error.HTTPError as e:
            wait_s = 2.5 * (attempt + 1) if e.code in (403, 429, 500, 502, 503, 504) else 1.2
            if attempt < retries:
                time.sleep(wait_s)
            else:
                print(f"[WARN] HTTP {e.code} leyendo {safe_url}: {e.reason}")
                return ""
        except Exception as e:
            if attempt < retries:
                time.sleep(1.8 * (attempt + 1))
            else:
                print(f"[WARN] No se pudo leer {safe_url}: {e}")
                return ""
    return ""


class NestedTableAndLinkParser(HTMLParser):
    """Extrae TODAS las tablas (incluso si están anidadas dentro de tablas de maquetación)."""
    def __init__(self) -> None:
        super().__init__()
        self.all_links: List[Tuple[str, str]] = []
        self.tables: List[Dict[str, Any]] = []
        self._table_stack: List[Dict[str, Any]] = []
        self._in_a = False
        self._cur_href = ""
        self._cur_a_text: List[str] = []
        self._in_heading = False
        self._cur_heading: List[str] = []
        self._last_heading = ""

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        attr_d = dict(attrs)
        if t in ("h1", "h2", "h3", "h4", "h5", "caption"):
            self._in_heading = True
            self._cur_heading = []
        elif t == "a":
            self._in_a = True
            self._cur_href = str(attr_d.get("href") or "").strip()
            self._cur_a_text = []
        elif t == "table":
            self._table_stack.append({
                "heading": self._last_heading,
                "rows": [],
                "cur_row": None,
                "cur_cell": None,
            })
        elif t == "tr" and self._table_stack:
            top = self._table_stack[-1]
            if top["cur_cell"] is not None and top["cur_row"] is not None:
                top["cur_row"].append({
                    "text": clean_cell("".join(top["cur_cell"]["text_parts"])),
                    "links": list(top["cur_cell"]["links"]),
                })
                top["cur_cell"] = None
            if top["cur_row"]:
                top["rows"].append(top["cur_row"])
            top["cur_row"] = []
        elif t in ("td", "th") and self._table_stack:
            top = self._table_stack[-1]
            if top["cur_row"] is None:
                top["cur_row"] = []
            if top["cur_cell"] is not None:
                top["cur_row"].append({
                    "text": clean_cell("".join(top["cur_cell"]["text_parts"])),
                    "links": list(top["cur_cell"]["links"]),
                })
            top["cur_cell"] = {"text_parts": [], "links": []}

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("h1", "h2", "h3", "h4", "h5", "caption") and self._in_heading:
            self._in_heading = False
            txt = clean_cell("".join(self._cur_heading))
            if txt:
                self._last_heading = txt
        elif t == "a" and self._in_a:
            self._in_a = False
            txt = clean_cell("".join(self._cur_a_text))
            if self._cur_href:
                self.all_links.append((self._cur_href, txt))
                if self._table_stack and self._table_stack[-1]["cur_cell"] is not None:
                    self._table_stack[-1]["cur_cell"]["links"].append((self._cur_href, txt))
            self._cur_href = ""
        elif t in ("td", "th") and self._table_stack:
            top = self._table_stack[-1]
            if top["cur_cell"] is not None and top["cur_row"] is not None:
                top["cur_row"].append({
                    "text": clean_cell("".join(top["cur_cell"]["text_parts"])),
                    "links": list(top["cur_cell"]["links"]),
                })
                top["cur_cell"] = None
        elif t == "tr" and self._table_stack:
            top = self._table_stack[-1]
            if top["cur_cell"] is not None and top["cur_row"] is not None:
                top["cur_row"].append({
                    "text": clean_cell("".join(top["cur_cell"]["text_parts"])),
                    "links": list(top["cur_cell"]["links"]),
                })
                top["cur_cell"] = None
            if top["cur_row"]:
                top["rows"].append(top["cur_row"])
            top["cur_row"] = None
        elif t == "table" and self._table_stack:
            finished = self._table_stack.pop()
            if finished["cur_cell"] is not None and finished["cur_row"] is not None:
                finished["cur_row"].append({
                    "text": clean_cell("".join(finished["cur_cell"]["text_parts"])),
                    "links": list(finished["cur_cell"]["links"]),
                })
                finished["cur_cell"] = None
            if finished["cur_row"]:
                finished["rows"].append(finished["cur_row"])
                finished["cur_row"] = None
            if finished["rows"]:
                self.tables.append({"heading": finished["heading"], "rows": finished["rows"]})

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self._cur_heading.append(data)
        if self._in_a:
            self._cur_a_text.append(data)
        if self._table_stack and self._table_stack[-1]["cur_cell"] is not None:
            self._table_stack[-1]["cur_cell"]["text_parts"].append(data)



def inspect_empty_html(html_str: str) -> str:
    """Extrae texto visible del <body> y posibles endpoints AJAX/iframe para diagnóstico."""
    if not html_str:
        return "HTML vacío (0 bytes)"
    body_m = re.search(r"<body[^>]*>(.*?)</body>", html_str, re.IGNORECASE | re.DOTALL)
    chunk = body_m.group(1) if body_m else html_str
    # Buscar posibles llamadas AJAX / .load / iframe / window.location dentro de scripts
    ajax_hits = re.findall(r"""(?:url\s*:\s*|load\s*\(\s*|src\s*=\s*|href\s*=\s*|location(?:\.href)?\s*=\s*)['"]([^'"]+\.php[^'"]*)['"]""", chunk, re.IGNORECASE)
    ajax_hits = [u for u in dict.fromkeys(ajax_hits) if any(k in u.lower() for k in ("est", "ofe", "pic", "def", "ajax", "tab", "data", "jug", "equ", "login", "suscrip"))]
    # Texto visible sin scripts/styles
    no_js = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", chunk, flags=re.IGNORECASE | re.DOTALL)
    vis = clean_cell(re.sub(r"<[^>]+>", " ", no_js))
    return f"body_text='{vis[:320]}' | php_refs={ajax_hits[:6]}"


def parse_page(html_str: str) -> NestedTableAndLinkParser:
    p = NestedTableAndLinkParser()
    p.feed(html_str or "")
    return p


def to_int(val: Any) -> int:
    s = re.sub(r"[^\d\-]", "", str(val or ""))
    try:
        return int(s) if s and s != "-" else 0
    except ValueError:
        return 0


def to_float(val: Any) -> float:
    s = str(val or "").replace(",", ".").strip()
    m = re.search(r"-?\d*\.?\d+", s)
    if not m:
        return 0.0
    try:
        return float(m.group(0))
    except ValueError:
        return 0.0


def parse_baseball_rate(val: Any, allow_above_one: bool = False) -> float:
    s = str(val or "").strip().replace(",", ".")
    if not s or "---" in s or "nan" in s.lower():
        return 0.0
    if s in (".1000", "1000", "1.000"):
        return 1.0
    if s.startswith(".") and len(s) >= 5 and s[1:].isdigit():
        return round(int(s[1:]) / 1000.0, 3)
    try:
        num = float(s)
    except ValueError:
        return 0.0
    if num > 5.0:
        num = num / 1000.0
    if not allow_above_one and num > 1.0:
        num = min(1.0, num)
    return round(num, 3)


def parse_innings(val: Any) -> float:
    f = to_float(val)
    whole = int(f)
    frac = round((f - whole) * 10)
    if frac == 1:
        return whole + (1.0 / 3.0)
    if frac == 2:
        return whole + (2.0 / 3.0)
    return f


def extract_query_param(href: str, param: str) -> str:
    m = re.search(rf"[?&]{param}=([^&#]+)", href, re.IGNORECASE)
    return urllib.parse.unquote(m.group(1)).strip() if m else ""


def normalize_position(raw: str) -> str:
    s = norm_text(raw)
    if not s or "total" in s:
        return ""
    if "lanz" in s or "pitch" in s or s == "p" or "(1)" in s:
        return "P"
    if "recep" in s or "catch" in s or s == "c" or "(2)" in s:
        return "C"
    if "1ra" in s or "primera" in s or "1b" in s or "(3)" in s:
        return "1B"
    if "2da" in s or "segunda" in s or "2b" in s or "(4)" in s:
        return "2B"
    if "3ra" in s or "tercera" in s or "3b" in s or "(5)" in s:
        return "3B"
    if "campo corto" in s or "short stop" in s or "shortstop" in s or s == "ss" or "(6)" in s:
        return "SS"
    if "izquierd" in s or "left" in s or s == "lf" or "(7)" in s:
        return "LF"
    if "central" in s or "center" in s or s == "cf" or "(8)" in s:
        return "CF"
    if "derech" in s or "right" in s or s == "rf" or "(9)" in s:
        return "RF"
    if "sfe" in s or "externo" in s or "4to" in s or "cuarto" in s or "(11)" in s:
        return "SFE"
    if "sfi" in s or "interno" in s or "short field" in s or "shortfield" in s or s == "sf" or "(10)" in s:
        return "SFI"
    if "design" in s or s in ("bd", "dh", "ep") or "bateador" in s:
        return "BD"
    return raw.strip()


def find_header_row(rows: List[List[Dict[str, Any]]], required_tokens: Tuple[str, ...], min_hits: int = 1) -> Tuple[int, List[str]]:
    for idx, row in enumerate(rows[:8]):
        cols = [norm_text(c["text"]) for c in row]
        hits = sum(1 for tok in required_tokens if any(tok == col or (len(tok) >= 3 and tok in col) for col in cols))
        if hits >= min_hits:
            return idx, cols
    return -1, []


def col_val(row: List[Dict[str, Any]], headers: List[str], *aliases: str) -> str:
    for al in aliases:
        al_n = norm_text(al)
        for i, h in enumerate(headers):
            if i < len(row) and h == al_n:
                return row[i]["text"]
    for al in aliases:
        al_n = norm_text(al)
        if len(al_n) < 3:
            continue
        for i, h in enumerate(headers):
            if i < len(row) and al_n in h:
                return row[i]["text"]
    return ""


def extract_row_player(r: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Busca el nombre del jugador y su jug_id en las primeras 5 celdas."""
    for c in r[:5]:
        for href, ltxt in c["links"]:
            if "jugador.php" in href.lower():
                jid = extract_query_param(href, "jug")
                nm = ltxt or c["text"]
                if nm:
                    return nm, jid
    for c in r[:4]:
        txt = c["text"]
        if txt and not re.fullmatch(r"[\d.\-/#]+", txt) and len(txt) >= 3:
            return txt, ""
    return "", ""


def is_junk_player_name(name: str) -> bool:
    n = norm_text(name)
    if not n or len(n) < 2:
        return True
    return any(w in n for w in ("total", "equipo", "promedio", "jugador", "lanzador", "al campo", "defensiva", "pitcheo", "ofensiva"))


# ==============================================================================
# PARSERS POR PÁGINA DE BEISBOLYSOFTBOL.COM
# ==============================================================================

def discover_tournaments(league_html: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    p = parse_page(league_html)
    min_num = int(cfg.get("min_tournament_number", 87))
    squad_map = cfg.get("tournaments_squad_map", {})
    default_sq = cfg.get("default_new_tournament_squad", "A")

    cams: Dict[str, Dict[str, Any]] = {}
    for href, txt in p.all_links:
        if "campeonato.php" in href.lower():
            cid = extract_query_param(href, "cam")
            if not cid or cid in cams:
                continue
            raw_name = clean_cell(txt) or f"Campeonato {cid}"
            name = re.sub(r"^[^A-Za-z0-9ÁÉÍÓÚÑáéíóúñ]+", "", raw_name).strip() or raw_name
            m_num = re.search(r"torneo\s*(\d+)", norm_text(name))
            t_num = int(m_num.group(1)) if m_num else 0
            if t_num and t_num < min_num:
                continue
            squad = squad_map.get(str(t_num), default_sq)
            cams[cid] = {"cam_id": cid, "number": t_num, "name": name, "squad": squad, "url": href}

    return sorted(cams.values(), key=lambda x: (-x["number"], -int(x["cam_id"]) if x["cam_id"].isdigit() else 0))


def parse_campeonato_standings(cam_html: str) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    p = parse_page(cam_html)
    standings_blocks: List[Dict[str, Any]] = []
    teams_found: Dict[str, Dict[str, Any]] = {}

    for tbl in p.tables:
        rows = tbl["rows"]
        h_idx, headers = find_header_row(rows, ("pts", "ca", "cp", "avg"), min_hits=3)
        if h_idx < 0:
            continue

        phase_title = tbl.get("heading") or "Eliminatoria"
        if h_idx > 0 and rows[0] and len(rows[0][0]["text"]) > 4:
            phase_title = rows[0][0]["text"]
        for c in rows[h_idx]:
            if "torneo" in norm_text(c["text"]) or "equipos participantes" in norm_text(c["text"]):
                phase_title = c["text"]
                break

        parsed_rows = []
        for r in rows[h_idx + 1:]:
            if len(r) < 6:
                continue
            team_name = ""
            equ_id = ""
            for cell in r[:4]:
                for href, ltxt in cell["links"]:
                    if "equipo.php" in href.lower():
                        equ_id = extract_query_param(href, "equ")
                        team_name = ltxt or cell["text"]
                        break
                if team_name:
                    break
            if not team_name:
                team_name = r[1]["text"] if len(r) > 1 else r[0]["text"]
            if not team_name or norm_text(team_name) in ("total", "totales", "equipo"):
                continue

            j = to_int(col_val(r, headers, "j", "jj"))
            g = to_int(col_val(r, headers, "g", "jg"))
            pr = to_int(col_val(r, headers, "p", "jp"))
            e = to_int(col_val(r, headers, "e", "je"))
            ca = to_int(col_val(r, headers, "ca"))
            cp = to_int(col_val(r, headers, "cp"))
            df = to_int(col_val(r, headers, "df", "dif"))
            if df == 0 and (ca or cp):
                df = ca - cp
            avg = parse_baseball_rate(col_val(r, headers, "avg", "ave"))
            if avg == 0 and (g + pr) > 0:
                avg = round(g / (g + pr), 3)
            pts = to_int(col_val(r, headers, "pts"))

            parsed_rows.append({
                "pos": len(parsed_rows) + 1, "equ_id": equ_id, "team": team_name,
                "j": j, "g": g, "p": pr, "e": e, "ca": ca, "cp": cp, "df": df, "avg": avg, "pts": pts,
            })
            if equ_id and equ_id not in teams_found:
                teams_found[equ_id] = {"equ_id": equ_id, "name": team_name}

        if parsed_rows:
            standings_blocks.append({"phase": phase_title, "rows": parsed_rows})

    for href, txt in p.all_links:
        if "equipo.php" in href.lower() and txt:
            eid = extract_query_param(href, "equ")
            if eid and eid not in teams_found:
                teams_found[eid] = {"equ_id": eid, "name": txt}

    return standings_blocks, teams_found


def parse_all_results(res_html: str) -> List[Dict[str, Any]]:
    p = parse_page(res_html)
    games: List[Dict[str, Any]] = []
    seen = set()
    for tbl in p.tables:
        rows = tbl["rows"]
        h_idx, _ = find_header_row(rows, ("visitante", "local", "boxscore", "fecha"), min_hits=2)
        if h_idx < 0:
            continue
        for r in rows[h_idx + 1:]:
            if len(r) < 3:
                continue
            nj = r[0]["text"]
            date_str = r[1]["text"] if len(r) > 1 else ""
            mid_cells = [c["text"] for c in r[2:] if norm_text(c["text"]) not in ("ver", "boxscore", "")]
            m = re.search(r"(.+?)\s*\(\s*(\d+)\s*\)\s*[-–]\s*\(\s*(\d+)\s*\)\s*(.+)", " ".join(mid_cells))
            if not m:
                continue
            vis_name, vis_score = clean_cell(m.group(1)), int(m.group(2))
            loc_score, loc_name = int(m.group(3)), clean_cell(m.group(4))
            jue_id = ""
            for c in r:
                for href, _ in c["links"]:
                    if "detallejuego.php" in href.lower():
                        jue_id = extract_query_param(href, "jue")
                        break
            key = jue_id or f"{date_str}_{vis_name}_{loc_name}_{vis_score}_{loc_score}"
            if key in seen:
                continue
            seen.add(key)
            games.append({
                "jue_id": jue_id, "nj": nj, "date": date_str,
                "visitor": vis_name, "visitor_score": vis_score, "local": loc_name, "local_score": loc_score,
            })
    return games


def parse_team_roster(html_str: str) -> List[Dict[str, str]]:
    """Extrae jugadores inscritos desde roster.php (útil para torneos recién iniciados como T90)."""
    p = parse_page(html_str)
    found: Dict[str, Dict[str, str]] = {}
    for href, txt in p.all_links:
        if "jugador.php" in href.lower() and txt and not is_junk_player_name(txt):
            jid = extract_query_param(href, "jug")
            k = norm_text(txt)
            if k not in found:
                found[k] = {"jug_id": jid, "name": txt}
    return list(found.values())


def parse_team_batting(html_str: str) -> List[Dict[str, Any]]:
    p = parse_page(html_str)
    players: List[Dict[str, Any]] = []
    for tbl in p.tables:
        rows = tbl["rows"]
        h_idx, headers = find_header_row(rows, ("vb", "avg", "slg", "ops", "pde", "ci", "h"), min_hits=3)
        if h_idx < 0 or ("vb" not in headers and "ab" not in headers):
            continue
        for r in rows[h_idx + 1:]:
            if len(r) < 5:
                continue
            name, jug_id = extract_row_player(r)
            if is_junk_player_name(name):
                continue

            jj = to_int(col_val(r, headers, "jj", "j"))
            vb = to_int(col_val(r, headers, "vb", "ab"))
            ca = to_int(col_val(r, headers, "ca", "r"))
            h = to_int(col_val(r, headers, "h", "hc"))
            h2 = to_int(col_val(r, headers, "h2", "2b"))
            h3 = to_int(col_val(r, headers, "h3", "3b"))
            hr = to_int(col_val(r, headers, "hr"))
            ci = to_int(col_val(r, headers, "ci", "rbi"))
            bb = to_int(col_val(r, headers, "bb"))
            k = to_int(col_val(r, headers, "k", "so"))
            br = to_int(col_val(r, headers, "br", "sb"))
            sf = to_int(col_val(r, headers, "sf"))
            gp = to_int(col_val(r, headers, "gp", "hbp"))
            al = to_int(col_val(r, headers, "al", "pa"))

            avg = round(h / vb, 3) if vb > 0 else parse_baseball_rate(col_val(r, headers, "avg", "ave"))
            denom_obp = al if al >= (vb + bb + gp + sf) and al > 0 else (vb + bb + gp + sf)
            obp = round((h + bb + gp) / denom_obp, 3) if denom_obp > 0 else parse_baseball_rate(col_val(r, headers, "pde", "obp"))
            tb = h + h2 + 2 * h3 + 3 * hr
            slg = round(tb / vb, 3) if vb > 0 else parse_baseball_rate(col_val(r, headers, "slg"), allow_above_one=True)
            ops = round(obp + slg, 3)

            players.append({
                "jug_id": jug_id, "name": name,
                "jj": jj, "vb": vb, "al": max(al, vb + bb + gp + sf),
                "ca": ca, "h": h, "h2": h2, "h3": h3, "hr": hr,
                "ci": ci, "bb": bb, "k": k, "br": br, "sf": sf, "gp": gp,
                "avg": avg, "obp": obp, "slg": slg, "ops": ops,
            })
        if players:
            break
    return players


def parse_team_pitching(html_str: str, debug_tag: str = "") -> List[Dict[str, Any]]:
    """
    Extrae tabla de pitcheo desde estadisticasequipo.php?...&est=pic.
    Columnas reales UNIMET: N | PITCHER | G | P | B | IP | VB | HP | H2 | H3 | HR | CP | CL | K | BB | SF | WP | EFE | AVG | WHIP
    """
    p = parse_page(html_str)
    pitchers: List[Dict[str, Any]] = []
    seen_headers = []

    for tbl in p.tables:
        rows = tbl["rows"]
        if rows:
            seen_headers.append([norm_text(c["text"]) for c in rows[0][:14]])
        h_idx, headers = find_header_row(
            rows,
            ("pitcher", "efe", "era", "ip", "il", "el", "cl", "cp", "hp", "whip", "wp"),
            min_hits=4,
        )
        if h_idx < 0:
            continue
        # Evitar confundir con bateo (tiene SLG/OPS/PDE) o defensa (tiene PO/LT/PDF)
        if "slg" in headers or "ops" in headers or "pde" in headers or "po" in headers or "pdf" in headers:
            continue

        for r in rows[h_idx + 1:]:
            if len(r) < 5:
                continue
            name, jug_id = extract_row_player(r)
            if is_junk_player_name(name):
                continue

            jj = to_int(col_val(r, headers, "jj", "j", "jl"))
            ji = to_int(col_val(r, headers, "ji", "gs"))
            g = to_int(col_val(r, headers, "jg", "g", "pg", "w"))
            pr = to_int(col_val(r, headers, "jp", "p", "pp", "l"))
            s = to_int(col_val(r, headers, "js", "s", "sv"))
            ip_raw = to_float(col_val(r, headers, "ip", "il", "el", "inn", "in", "ej", "entradas"))
            ip_real = parse_innings(ip_raw)
            h = to_int(col_val(r, headers, "hp", "h", "hc", "hits"))
            ca = to_int(col_val(r, headers, "cp", "ca", "c", "r"))
            cl = to_int(col_val(r, headers, "cl", "er"))
            bb = to_int(col_val(r, headers, "bb", "bo"))
            k = to_int(col_val(r, headers, "k", "so", "pn", "kp"))
            hr = to_int(col_val(r, headers, "hr", "jr"))
            wp = to_int(col_val(r, headers, "wp"))
            vb_enf = to_int(col_val(r, headers, "vb"))
            avg_against = parse_baseball_rate(col_val(r, headers, "avg", "ave"))
            efe_str = col_val(r, headers, "efe", "era", "efec", "ef")
            efe_pub = to_float(efe_str)
            efe = round(efe_pub, 2) if (efe_str.strip() != "" and "---" not in efe_str) else (round(cl * 7.0 / ip_real, 2) if ip_real > 0 else 0.0)
            whip_str = col_val(r, headers, "whip")
            whip_pub = to_float(whip_str)
            whip = round(whip_pub, 2) if whip_pub > 0 else (round((h + bb) / ip_real, 2) if ip_real > 0 else 0.0)

            if jj == 0 and ip_real == 0 and g == 0 and pr == 0 and h == 0 and bb == 0:
                continue
            if jj == 0:
                jj = max(g + pr, 1 if ip_real > 0 else 0)

            pitchers.append({
                "jug_id": jug_id, "name": name,
                "jj": jj, "ji": ji, "g": g, "p": pr, "s": s,
                "ip": ip_raw, "ip_real": round(ip_real, 2),
                "vb_enf": vb_enf, "h": h, "ca": ca, "cl": cl,
                "bb": bb, "k": k, "hr": hr, "wp": wp,
                "efe": efe, "whip": whip, "avg_against": avg_against,
            })
        if pitchers:
            break

    if not pitchers and debug_tag:
        print(f"       [DEBUG {debug_tag} est=pic] 0 pitchers. Headers vistos: {seen_headers[:4]}")
    return pitchers


def parse_team_defense(html_str: str, debug_tag: str = "") -> List[Dict[str, Any]]:
    """
    Extrae tabla de defensiva desde estadisticasequipo.php?...&est=def.
    Columnas reales UNIMET: N | JUGADOR | IJ | PO | A | E | DP | LT | PDF
    """
    p = parse_page(html_str)
    fielders: List[Dict[str, Any]] = []
    seen_headers = []

    for tbl in p.tables:
        rows = tbl["rows"]
        if rows:
            seen_headers.append([norm_text(c["text"]) for c in rows[0][:14]])
        h_idx, headers = find_header_row(
            rows,
            ("ij", "ej", "po", "as", "a", "e", "err", "dp", "lt", "tl", "pdf", "fld"),
            min_hits=4,
        )
        if h_idx < 0:
            continue
        if "vb" in headers or "efe" in headers or "era" in headers or "slg" in headers:
            continue

        for r in rows[h_idx + 1:]:
            if len(r) < 5:
                continue
            name, jug_id = extract_row_player(r)
            if is_junk_player_name(name):
                continue

            jj = to_int(col_val(r, headers, "jj", "j"))
            ij_raw = to_float(col_val(r, headers, "ij", "ej", "il", "ip", "inn", "in"))
            ej = round(parse_innings(ij_raw), 2)
            po = to_int(col_val(r, headers, "po", "o"))
            asist = to_int(col_val(r, headers, "a", "as"))
            err = to_int(col_val(r, headers, "e", "err"))
            dp = to_int(col_val(r, headers, "dp"))
            lt = po + asist + err
            pdf = round((po + asist) / lt, 3) if lt > 0 else parse_baseball_rate(col_val(r, headers, "pdf", "fld", "avg"))
            pos_col = normalize_position(col_val(r, headers, "pos", "posicion", "al campo"))

            if jj == 0 and po == 0 and asist == 0 and err == 0 and ej == 0:
                continue

            fielders.append({
                "jug_id": jug_id, "name": name, "pos": pos_col,
                "jj": jj, "po": po, "as": asist, "e": err, "dp": dp, "ej": ej, "pdf": pdf,
            })
        if fielders:
            break

    if not fielders and debug_tag:
        print(f"       [DEBUG {debug_tag} est=def] 0 defensores. Headers vistos: {seen_headers[:4]}")
    return fielders


def parse_player_detail(html_str: str, tournament_name: str = "", tournament_num: int = 0) -> Dict[str, Any]:
    """
    Extrae desde jugador.php:
      1. Defensiva POR POSICIÓN (`AL CAMPO`)
      2. Pitcheo individual (si lanzó) — sumando juego a juego para evitar desfase por colspan
      3. Bateo completo del torneo (desde `Registro Historico Personal` filtrando el campeonato actual
         y/o sumando `Numeros Juego a Juego`)
    """
    p = parse_page(html_str)
    positions: List[Dict[str, Any]] = []
    game_log: List[Dict[str, Any]] = []
    pitching_summary: Optional[Dict[str, Any]] = None
    batting_from_hist: Optional[Dict[str, Any]] = None
    t_norm = norm_text(tournament_name)
    t_num_pat = f"torneo {tournament_num}" if tournament_num else ""

    for tbl in p.tables:
        rows = tbl["rows"]

        # 1. Tabla Defensiva por posición: AL CAMPO | JJ | PO | AS | E | DP | ... | EJ | PDF
        h_def, headers_def = find_header_row(rows, ("al campo", "po", "as", "pdf"), min_hits=3)
        if h_def >= 0 and "al campo" in headers_def:
            for r in rows[h_def + 1:]:
                if len(r) < 5:
                    continue
                pos_raw = r[0]["text"]
                pos_code = normalize_position(pos_raw)
                if not pos_code:
                    continue
                jj = to_int(col_val(r, headers_def, "jj", "j"))
                po = to_int(col_val(r, headers_def, "po"))
                asist = to_int(col_val(r, headers_def, "as", "a"))
                err = to_int(col_val(r, headers_def, "e"))
                dp = to_int(col_val(r, headers_def, "dp"))
                ej = round(parse_innings(to_float(col_val(r, headers_def, "ej", "ij", "il", "ip"))), 2)
                lt = po + asist + err
                pdf = round((po + asist) / lt, 3) if lt > 0 else parse_baseball_rate(col_val(r, headers_def, "pdf"))
                positions.append({
                    "pos": pos_code, "pos_raw": pos_raw,
                    "jj": jj, "po": po, "as": asist, "e": err, "dp": dp, "ej": ej, "pdf": pdf,
                })
            continue

        # 2. Tabla de Pitcheo individual (permite VB; excluye SLG/OPS/AL CAMPO/CAMPEONATO)
        h_pic, headers_pic = find_header_row(rows, ("efe", "era", "ip", "il", "el", "cl", "cp", "hp", "whip"), min_hits=4)
        if h_pic >= 0 and "slg" not in headers_pic and "ops" not in headers_pic and "al campo" not in headers_pic and "campeonato" not in headers_pic:
            pic_games = []
            for r in rows[h_pic + 1:]:
                if len(r) < 6:
                    continue
                if any("total" in norm_text(c["text"]) for c in r[:3]):
                    continue
                ip_raw = to_float(col_val(r, headers_pic, "ip", "il", "el", "inn"))
                ip_real = parse_innings(ip_raw)
                h = to_int(col_val(r, headers_pic, "hp", "h", "hc"))
                cl = to_int(col_val(r, headers_pic, "cl", "er"))
                ca = to_int(col_val(r, headers_pic, "cp", "ca", "c"))
                bb = to_int(col_val(r, headers_pic, "bb"))
                k = to_int(col_val(r, headers_pic, "k", "so"))
                hr = to_int(col_val(r, headers_pic, "hr"))
                g = to_int(col_val(r, headers_pic, "jg", "g"))
                pr = to_int(col_val(r, headers_pic, "jp", "p"))
                if ip_real > 0 or h > 0 or bb > 0 or g > 0 or pr > 0:
                    pic_games.append({"ip_real": ip_real, "h": h, "cl": cl, "ca": ca, "bb": bb, "k": k, "hr": hr, "g": g, "p": pr})
            if pic_games:
                ip_tot = round(sum(x["ip_real"] for x in pic_games), 2)
                h_tot = sum(x["h"] for x in pic_games)
                cl_tot = sum(x["cl"] for x in pic_games)
                ca_tot = sum(x["ca"] for x in pic_games)
                bb_tot = sum(x["bb"] for x in pic_games)
                k_tot = sum(x["k"] for x in pic_games)
                hr_tot = sum(x["hr"] for x in pic_games)
                g_tot = sum(x["g"] for x in pic_games)
                p_tot = sum(x["p"] for x in pic_games)
                efe = round(cl_tot * 7.0 / ip_tot, 2) if ip_tot > 0 else 0.0
                whip = round((h_tot + bb_tot) / ip_tot, 2) if ip_tot > 0 else 0.0
                pitching_summary = {
                    "jj": len(pic_games), "ji": 0, "g": g_tot, "p": p_tot, "s": 0,
                    "ip": ip_tot, "ip_real": ip_tot,
                    "h": h_tot, "ca": ca_tot, "cl": cl_tot, "bb": bb_tot, "k": k_tot, "hr": hr_tot,
                    "efe": efe, "whip": whip,
                }
            continue

        # 3. Registro Historico Personal: Campeonato | Equipo | JJ | VB | CA | HC | BB | SH | SF | GP | AL | H2 | H3 | HR | CI | BR | K | AVG
        h_hist, headers_hist = find_header_row(rows, ("campeonato", "equipo", "vb", "hc"), min_hits=3)
        if h_hist >= 0 and "campeonato" in headers_hist and "vb" in headers_hist:
            for r in rows[h_hist + 1:]:
                if len(r) < 8:
                    continue
                camp_txt = norm_text(col_val(r, headers_hist, "campeonato"))
                if not camp_txt:
                    continue
                matches_t = (t_num_pat and t_num_pat in camp_txt) or (t_norm and t_norm in camp_txt)
                if not matches_t:
                    continue
                jj = to_int(col_val(r, headers_hist, "jj", "j"))
                vb = to_int(col_val(r, headers_hist, "vb"))
                ca = to_int(col_val(r, headers_hist, "ca"))
                h = to_int(col_val(r, headers_hist, "hc", "h"))
                h2 = to_int(col_val(r, headers_hist, "h2"))
                h3 = to_int(col_val(r, headers_hist, "h3"))
                hr = to_int(col_val(r, headers_hist, "hr"))
                ci = to_int(col_val(r, headers_hist, "ci"))
                bb = to_int(col_val(r, headers_hist, "bb"))
                k = to_int(col_val(r, headers_hist, "k"))
                br = to_int(col_val(r, headers_hist, "br"))
                sf = to_int(col_val(r, headers_hist, "sf"))
                gp = to_int(col_val(r, headers_hist, "gp"))
                al = to_int(col_val(r, headers_hist, "al"))
                denom_obp = max(al, vb + bb + gp + sf)
                avg = round(h / vb, 3) if vb > 0 else 0.0
                obp = round((h + bb + gp) / denom_obp, 3) if denom_obp > 0 else 0.0
                tb = h + h2 + 2 * h3 + 3 * hr
                slg = round(tb / vb, 3) if vb > 0 else 0.0
                ops = round(obp + slg, 3)
                if vb > 0 or al > 0 or jj > 0:
                    batting_from_hist = {
                        "jj": jj, "vb": vb, "al": denom_obp, "ca": ca, "h": h, "h2": h2, "h3": h3,
                        "hr": hr, "ci": ci, "bb": bb, "k": k, "br": br, "sf": sf, "gp": gp,
                        "avg": avg, "obp": obp, "slg": slg, "ops": ops,
                    }
            continue

        # 4. Tabla Juego a Juego ofensivo: NJ | Dia | Vs | VB | H | H2 | H3 | HR | CI | CA | BB | K | AL | PDE | SLG | AVG | OPS
        h_log, headers_log = find_header_row(rows, ("dia", "vs", "vb"), min_hits=3)
        if h_log >= 0 and "vb" in headers_log and "slg" in headers_log:
            for r in rows[h_log + 1:]:
                if len(r) < 8:
                    continue
                if "total" in norm_text(r[0]["text"]) or "total" in norm_text(r[1]["text"]):
                    continue
                game_log.append({
                    "nj": r[0]["text"],
                    "date": col_val(r, headers_log, "dia", "fecha"),
                    "vs": col_val(r, headers_log, "vs"),
                    "vb": to_int(col_val(r, headers_log, "vb")),
                    "h": to_int(col_val(r, headers_log, "h", "hc")),
                    "h2": to_int(col_val(r, headers_log, "h2")),
                    "h3": to_int(col_val(r, headers_log, "h3")),
                    "hr": to_int(col_val(r, headers_log, "hr")),
                    "ci": to_int(col_val(r, headers_log, "ci")),
                    "ca": to_int(col_val(r, headers_log, "ca")),
                    "bb": to_int(col_val(r, headers_log, "bb")),
                    "k": to_int(col_val(r, headers_log, "k")),
                    "al": to_int(col_val(r, headers_log, "al")),
                })

    # Construir batting_backup combinando Registro Historico (preferido porque trae SF/GP/BR) o suma de game_log
    batting_backup = batting_from_hist
    if not batting_backup and game_log:
        jj = len(game_log)
        vb = sum(g["vb"] for g in game_log)
        h = sum(g["h"] for g in game_log)
        h2 = sum(g["h2"] for g in game_log)
        h3 = sum(g["h3"] for g in game_log)
        hr = sum(g["hr"] for g in game_log)
        ci = sum(g["ci"] for g in game_log)
        ca = sum(g["ca"] for g in game_log)
        bb = sum(g["bb"] for g in game_log)
        k = sum(g["k"] for g in game_log)
        al = sum(g.get("al", 0) for g in game_log)
        denom_obp = max(al, vb + bb)
        avg = round(h / vb, 3) if vb > 0 else 0.0
        obp = round((h + bb) / denom_obp, 3) if denom_obp > 0 else 0.0
        tb = h + h2 + 2 * h3 + 3 * hr
        slg = round(tb / vb, 3) if vb > 0 else 0.0
        ops = round(obp + slg, 3)
        batting_backup = {
            "jj": jj, "vb": vb, "al": denom_obp, "ca": ca, "h": h, "h2": h2, "h3": h3,
            "hr": hr, "ci": ci, "bb": bb, "k": k, "br": 0, "sf": 0, "gp": 0,
            "avg": avg, "obp": obp, "slg": slg, "ops": ops,
        }

    return {
        "positions": positions,
        "game_log": game_log,
        "batting_backup": batting_backup,
        "pitching_backup": pitching_summary,
    }


def parse_lideres_table(html_str: str, mode: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Respaldo para equipos rivales desde `lideresV1.php?lig=174&cam=...&dep=AVE` (bateo)
    o `dep=EFE` (pitcheo), agrupado por nombre de equipo normalizado.
    """
    p = parse_page(html_str)
    by_team: Dict[str, List[Dict[str, Any]]] = {}
    for tbl in p.tables:
        rows = tbl["rows"]
        if mode == "bat":
            h_idx, headers = find_header_row(rows, ("vb", "avg", "h", "equipo"), min_hits=3)
            if h_idx < 0 or "vb" not in headers:
                continue
        else:
            h_idx, headers = find_header_row(rows, ("efe", "ip", "il", "equipo"), min_hits=3)
            if h_idx < 0:
                continue

        for r in rows[h_idx + 1:]:
            if len(r) < 5:
                continue
            name, jug_id = extract_row_player(r)
            if is_junk_player_name(name):
                continue
            tname = col_val(r, headers, "equipo", "eq")
            if not tname:
                for c in r[:5]:
                    for href, ltxt in c["links"]:
                        if "equipo.php" in href.lower() and ltxt:
                            tname = ltxt
                            break
            if not tname:
                continue
            tk = norm_text(tname)
            if mode == "bat":
                vb = to_int(col_val(r, headers, "vb", "ab"))
                h = to_int(col_val(r, headers, "h", "hc"))
                h2 = to_int(col_val(r, headers, "h2", "2b"))
                h3 = to_int(col_val(r, headers, "h3", "3b"))
                hr = to_int(col_val(r, headers, "hr"))
                ci = to_int(col_val(r, headers, "ci"))
                ca = to_int(col_val(r, headers, "ca"))
                bb = to_int(col_val(r, headers, "bb"))
                k = to_int(col_val(r, headers, "k"))
                jj = to_int(col_val(r, headers, "jj", "j"))
                al = to_int(col_val(r, headers, "al"))
                denom = max(al, vb + bb)
                avg = round(h / vb, 3) if vb > 0 else parse_baseball_rate(col_val(r, headers, "avg", "ave"))
                obp = round((h + bb) / denom, 3) if denom > 0 else parse_baseball_rate(col_val(r, headers, "pde", "obp"))
                tb = h + h2 + 2 * h3 + 3 * hr
                slg = round(tb / vb, 3) if vb > 0 else parse_baseball_rate(col_val(r, headers, "slg"), allow_above_one=True)
                by_team.setdefault(tk, []).append({
                    "jug_id": jug_id, "name": name, "jj": jj, "vb": vb, "al": denom,
                    "ca": ca, "h": h, "h2": h2, "h3": h3, "hr": hr, "ci": ci,
                    "bb": bb, "k": k, "br": 0, "sf": 0, "gp": 0,
                    "avg": avg, "obp": obp, "slg": slg, "ops": round(obp + slg, 3),
                })
            else:
                ip_raw = to_float(col_val(r, headers, "ip", "il", "el"))
                ip_real = parse_innings(ip_raw)
                g = to_int(col_val(r, headers, "g", "jg"))
                pr = to_int(col_val(r, headers, "p", "jp"))
                h = to_int(col_val(r, headers, "hp", "h", "hc"))
                cl = to_int(col_val(r, headers, "cl", "er"))
                ca = to_int(col_val(r, headers, "cp", "ca"))
                bb = to_int(col_val(r, headers, "bb"))
                k = to_int(col_val(r, headers, "k"))
                hr = to_int(col_val(r, headers, "hr"))
                efe_str = col_val(r, headers, "efe", "era")
                efe = round(to_float(efe_str), 2) if efe_str.strip() else (round(cl * 7.0 / ip_real, 2) if ip_real > 0 else 0.0)
                whip = round((h + bb) / ip_real, 2) if ip_real > 0 else to_float(col_val(r, headers, "whip"))
                if ip_real > 0 or g > 0 or pr > 0:
                    by_team.setdefault(tk, []).append({
                        "jug_id": jug_id, "name": name, "jj": max(g + pr, 1), "ji": 0,
                        "g": g, "p": pr, "s": 0, "ip": ip_raw, "ip_real": round(ip_real, 2),
                        "h": h, "ca": ca, "cl": cl, "bb": bb, "k": k, "hr": hr,
                        "efe": efe, "whip": whip,
                    })
        if by_team:
            break
    return by_team


# ==============================================================================
# FLUJO PRINCIPAL
# ==============================================================================


import subprocess as _subprocess


def inspect_tail_html(html_str: str) -> str:
    """Devuelve los últimos 500 caracteres del HTML para detectar errores PHP, bloqueos o cortes."""
    if not html_str:
        return "VACÍO"
    has_body_close = "</body>" in html_str.lower()
    has_table = "<table" in html_str.lower()
    tail = re.sub(r"\s+", " ", html_str[-550:]).strip()
    return f"len={len(html_str)} has_table={has_table} has_body_close={has_body_close} tail='{tail}'"


class BrowserFetcher:
    """Fallback opcional con Playwright (Chromium real) si urllib es bloqueado o falta JS."""
    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._page = None
        self.available = False

    def start(self) -> bool:
        if self.available:
            return True
        try:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)
            ctx = self._browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="es-VE",
                viewport={"width": 1280, "height": 800},
            )
            self._page = ctx.new_page()
            # Bloquear anuncios, imágenes y analytics para cargar cada página en <0.5s
            def _route_filter(route):
                url_l = route.request.url.lower()
                rtype = route.request.resource_type
                if rtype in ("image", "media", "font") or any(d in url_l for d in (
                    "googlesyndication", "doubleclick", "googletagmanager", "google-analytics",
                    "facebook", "adservice", "pagead", "amazon-adsystem"
                )):
                    route.abort()
                else:
                    route.continue_()
            self._page.route("**/*", _route_filter)
            self.available = True
            print("[INFO] Navegador Playwright (Chromium) iniciado como respaldo automático.")
            return True
        except Exception as e:
            print(f"[WARN] Playwright no disponible: {e}")
            self.available = False
            return False

    def get(self, url: str, wait_ms: int = 700) -> str:
        if not self.available or self._page is None:
            return ""
        full_url = url if url.startswith("http") else urllib.parse.urljoin(BASE_SITE, url.lstrip("/"))
        try:
            self._page.goto(full_url, wait_until="domcontentloaded", timeout=25000)
            if wait_ms > 0:
                self._page.wait_for_timeout(wait_ms)
            return self._page.content()
        except Exception as e:
            print(f"[WARN] Playwright fallo en {full_url}: {e}")
            return ""

    def close(self) -> None:
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self.available = False


def snapshot_has_real_stats(snap: Dict[str, Any]) -> int:
    """Cuenta cuántos registros de bateo reales existen en un snapshot."""
    total = 0
    for t in snap.get("tournaments", []):
        for td in (t.get("teams") or {}).values():
            total += len(td.get("batting") or [])
    return total


def load_best_previous_snapshot(output_path: Path) -> Dict[str, Dict[str, Any]]:
    """
    1) Intenta leer `data/softbol_snapshot.json` actual.
    2) Si está vacío (0 bateadores porque una corrida previa lo borró), busca automáticamente
       en el historial de Git el último commit donde `data/softbol_snapshot.json` SÍ tenía datos reales.
    """
    if output_path.exists():
        try:
            cur = json.loads(output_path.read_text(encoding="utf-8"))
            cnt = snapshot_has_real_stats(cur)
            if cnt > 0:
                print(f"[INFO] Cache previo válido detectado en {output_path} ({cnt} bateadores).")
                return {str(t.get("cam_id")): t for t in cur.get("tournaments", []) if t.get("cam_id")}
        except Exception:
            pass

    # Rescate automático desde el historial de Git (requiere fetch-depth: 0 en checkout)
    try:
        rel_p = output_path.as_posix()
        log_res = _subprocess.run(
            ["git", "log", "-n", "30", "--format=%H", "--", rel_p],
            capture_output=True, text=True, timeout=15
        )
        if log_res.returncode == 0:
            for commit_hash in log_res.stdout.splitlines():
                commit_hash = commit_hash.strip()
                if not commit_hash:
                    continue
                show_res = _subprocess.run(
                    ["git", "show", f"{commit_hash}:{rel_p}"],
                    capture_output=True, text=True, timeout=15
                )
                if show_res.returncode != 0:
                    continue
                try:
                    cand = json.loads(show_res.stdout)
                except Exception:
                    continue
                cnt = snapshot_has_real_stats(cand)
                if cnt > 0:
                    print(f"[RESCATE GIT] Snapshot válido recuperado del commit {commit_hash[:7]} ({cnt} bateadores)!")
                    return {str(t.get("cam_id")): t for t in cand.get("tournaments", []) if t.get("cam_id")}
    except Exception as e:
        print(f"[WARN] No se pudo consultar historial de Git para rescate: {e}")

    return {}


def load_previous_snapshot(output_path: Path) -> Dict[str, Dict[str, Any]]:
    """Carga el snapshot anterior (indexado por cam_id) para NUNCA sobrescribir datos buenos con ceros."""
    if not output_path.exists():
        return {}
    try:
        prev = json.loads(output_path.read_text(encoding="utf-8"))
        return {str(t.get("cam_id")): t for t in prev.get("tournaments", []) if t.get("cam_id")}
    except Exception:
        return {}


def run_extraction(config_path: Path, output_path: Path) -> None:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    lig_id = cfg["league_id"]
    our_kw = norm_text(cfg.get("our_team_keyword", "Relampago"))
    prev_by_cam = load_best_previous_snapshot(output_path)

    print(f"[INFO] Leyendo liga {lig_id}: {cfg['league_url']}")
    league_html = fetch_html(cfg["league_url"])
    if not league_html:
        if prev_by_cam:
            print("[WARN] No se pudo conectar con beisbolysoftbol.com; conservando snapshot válido.")
            return
        print("[ERROR] No se pudo conectar con beisbolysoftbol.com.")
        sys.exit(1)

    candidates = discover_tournaments(league_html, cfg)
    print(f"[INFO] Campeonatos candidatos (>= T{cfg.get('min_tournament_number', 87)}): {[(c['name'], c['cam_id'], c['squad']) for c in candidates]}")

    browser = BrowserFetcher()
    use_browser_for_stats = False
    tested_browser = False
    tournaments_out: List[Dict[str, Any]] = []

    try:
        for c_info in candidates:
            cam_id = str(c_info["cam_id"])
            prev_t = prev_by_cam.get(cam_id, {})
            cam_url_full = f"{BASE_SITE}campeonato.php?lig={lig_id}&cam={cam_id}"
            cam_html = fetch_html(f"campeonato.php?lig={lig_id}&cam={cam_id}", referer=cfg["league_url"])
            standings_blocks, teams_map = parse_campeonato_standings(cam_html)

            if not standings_blocks and prev_t.get("standings_blocks"):
                standings_blocks = prev_t["standings_blocks"]

            has_relampago = any(our_kw in norm_text(t["name"]) for t in teams_map.values()) or any(
                our_kw in norm_text(r["team"]) for blk in standings_blocks for r in blk["rows"]
            )
            if not has_relampago:
                print(f"[SKIP] {c_info['name']} (cam={cam_id}): no participa {cfg['our_team_display']}.")
                continue

            if not teams_map and prev_t.get("teams"):
                for tname, td in prev_t["teams"].items():
                    if td.get("equ_id"):
                        teams_map[str(td["equ_id"])] = {"equ_id": str(td["equ_id"]), "name": tname}

            # Verificar si el torneo ya tiene juegos jugados (en T90 con 0 juegos es normal tener 0 bateadores)
            torneo_tiene_juegos = any(
                r.get("j", 0) > 0 for blk in standings_blocks for r in blk.get("rows", [])
            )

            print(f"[INFO] Procesando {c_info['name']} (cam={cam_id}, Equipo {c_info['squad']}, juegos_jugados={torneo_tiene_juegos}) — {len(teams_map)} equipos...")
            res_html = fetch_html(f"todosresultados.php?lig={lig_id}&cam={cam_id}", referer=cam_url_full)
            games = parse_all_results(res_html)
            if not games and prev_t.get("games"):
                games = prev_t["games"]

            teams_data: Dict[str, Dict[str, Any]] = {}
            relampago_player_ids: Dict[str, str] = {}
            relampago_roster_names: List[Dict[str, str]] = []
            our_tname = ""
            cam_name_q = urllib.parse.quote(c_info["name"])

            # Procesar Relámpago PRIMERO para detectar al instante si urllib funciona o si debemos usar Playwright
            ordered_items = sorted(
                teams_map.items(),
                key=lambda kv: (0 if our_kw in norm_text(kv[1]["name"]) else 1, kv[1]["name"]),
            )

            for equ_id, t_meta in ordered_items:
                tname = t_meta["name"]
                is_ours = our_kw in norm_text(tname)
                if is_ours:
                    our_tname = tname
                dbg = f"{tname} T{c_info['number']}" if is_ours else ""
                eq_ref = f"{BASE_SITE}equipo.php?equ={equ_id}&lig={lig_id}&cam={cam_id}"

                ofe_url = f"estadisticasequipo.php?equ={equ_id}&lig={lig_id}&cam={cam_id}&est=ofe&{cam_name_q}"
                pic_url = f"estadisticasequipo.php?equ={equ_id}&lig={lig_id}&cam={cam_id}&est=pic&{cam_name_q}"
                def_url = f"estadisticasequipo.php?equ={equ_id}&lig={lig_id}&cam={cam_id}&est=def&{cam_name_q}"

                if use_browser_for_stats and browser.available:
                    ofe_html = browser.get(ofe_url)
                    pic_html = browser.get(pic_url)
                    def_html = browser.get(def_url)
                else:
                    ofe_html = fetch_html(ofe_url, referer=eq_ref)
                    time.sleep(0.18)
                    pic_html = fetch_html(pic_url, referer=eq_ref)
                    time.sleep(0.18)
                    def_html = fetch_html(def_url, referer=eq_ref)
                    time.sleep(0.18)

                batting = parse_team_batting(ofe_html)
                pitching = parse_team_pitching(pic_html, debug_tag=dbg if torneo_tiene_juegos else "")
                defense = parse_team_defense(def_html, debug_tag=dbg if torneo_tiene_juegos else "")

                # Si es un torneo CON juegos y Relámpago vino sin bateo por urllib, imprimir el TAIL exacto
                # y probar automáticamente con navegador Chromium real (Playwright)!
                if is_ours and torneo_tiene_juegos and not batting and not tested_browser:
                    tested_browser = True
                    print(f"       [TAIL urllib {dbg} est=ofe] {inspect_tail_html(ofe_html)}")
                    if browser.start():
                        # Abrir liga -> campeonato -> equipo -> estadisticasequipo como un usuario real
                        browser.get(cfg["league_url"], wait_ms=500)
                        browser.get(eq_ref, wait_ms=500)
                        ofe_pw = browser.get(ofe_url, wait_ms=900)
                        bat_pw = parse_team_batting(ofe_pw)
                        if bat_pw:
                            use_browser_for_stats = True
                            batting = bat_pw
                            pic_pw = browser.get(pic_url, wait_ms=700)
                            def_pw = browser.get(def_url, wait_ms=700)
                            pitching = parse_team_pitching(pic_pw, debug_tag=dbg)
                            defense = parse_team_defense(def_pw, debug_tag=dbg)
                            print(f"       [PLAYWRIGHT OK] {dbg}: bateo={len(batting)}, pitcheo={len(pitching)}, defensa={len(defense)}!")
                        else:
                            print(f"       [TAIL Playwright {dbg} est=ofe] {inspect_tail_html(ofe_pw)}")

                # Rescate automático desde cache/Git si la web devolvió vacío
                prev_team = (prev_t.get("teams") or {}).get(tname, {})
                if not batting and prev_team.get("batting"):
                    batting = prev_team["batting"]
                if not pitching and prev_team.get("pitching"):
                    pitching = prev_team["pitching"]
                if not defense and prev_team.get("defense"):
                    defense = prev_team["defense"]

                if is_ours:
                    ros_html = browser.get(f"roster.php?equ={equ_id}&lig={lig_id}&cam={cam_id}", wait_ms=500) if (use_browser_for_stats and browser.available) else fetch_html(f"roster.php?equ={equ_id}&lig={lig_id}&cam={cam_id}", referer=eq_ref)
                    relampago_roster_names = parse_team_roster(ros_html)
                    if not relampago_roster_names and prev_team.get("roster"):
                        relampago_roster_names = prev_team["roster"]
                    for p in relampago_roster_names:
                        if p.get("jug_id"):
                            relampago_player_ids[p["jug_id"]] = p["name"]
                    for lst in (batting, pitching, defense):
                        for p in lst:
                            if p.get("jug_id"):
                                relampago_player_ids[p["jug_id"]] = p["name"]
                    print(f"       Relámpago T{c_info['number']}: roster={len(relampago_roster_names)}, bateo={len(batting)}, pitcheo={len(pitching)}, defensa={len(defense)}")

                teams_data[tname] = {
                    "equ_id": equ_id, "name": tname, "is_ours": is_ours,
                    "roster": relampago_roster_names if is_ours else [],
                    "batting": batting, "pitching": pitching, "defense": defense,
                }

            # Fichas detalladas de Relámpago (posiciones AL CAMPO + backup de bateo y pitcheo)
            player_details: Dict[str, Dict[str, Any]] = dict(prev_t.get("relampago_player_details") or {})
            if relampago_player_ids and torneo_tiene_juegos:
                print(f"       Leyendo fichas individuales de {len(relampago_player_ids)} jugadores de Relámpago...")
                printed_jug_tail = False
                for jug_id, pname in relampago_player_ids.items():
                    j_url = f"jugador.php?jug={jug_id}&cam={cam_id}&{urllib.parse.quote(pname)}"
                    j_html = browser.get(j_url, wait_ms=500) if (use_browser_for_stats and browser.available) else fetch_html(j_url, referer=cam_url_full)
                    if j_html:
                        det = parse_player_detail(j_html, tournament_name=c_info["name"], tournament_num=c_info["number"])
                        det["name"] = pname
                        det["jug_id"] = jug_id
                        if det["positions"] or det["game_log"] or det["batting_backup"] or det["pitching_backup"]:
                            player_details[jug_id] = det
                        elif not printed_jug_tail:
                            printed_jug_tail = True
                            print(f"       [TAIL jugador.php {pname}] {inspect_tail_html(j_html)}")
                    if not use_browser_for_stats:
                        time.sleep(0.12)

            # Reconstrucción desde jugador.php si estadisticasequipo.php estuvo vacío
            if our_tname and our_tname in teams_data and player_details:
                td = teams_data[our_tname]
                if not td["batting"]:
                    rebuilt_bat = [{"jug_id": jid, "name": det["name"], **det["batting_backup"]} for jid, det in player_details.items() if det.get("batting_backup") and (det["batting_backup"].get("vb", 0) > 0 or det["batting_backup"].get("al", 0) > 0)]
                    if rebuilt_bat:
                        td["batting"] = rebuilt_bat
                        print(f"       [BACKUP jugador.php] Bateo de Relámpago T{c_info['number']}: {len(rebuilt_bat)} bateadores.")
                if not td["pitching"]:
                    rebuilt_pic = [{"jug_id": jid, "name": det["name"], **det["pitching_backup"]} for jid, det in player_details.items() if det.get("pitching_backup") and det["pitching_backup"].get("ip_real", 0) > 0]
                    if rebuilt_pic:
                        td["pitching"] = rebuilt_pic
                        print(f"       [BACKUP jugador.php] Pitcheo de Relámpago T{c_info['number']}: {len(rebuilt_pic)} pitchers.")
                if not td["defense"]:
                    rebuilt_def = []
                    for jid, det in player_details.items():
                        pos_rows = det.get("positions") or []
                        if pos_rows:
                            jj_d = sum(x.get("jj", 0) for x in pos_rows)
                            po_d = sum(x.get("po", 0) for x in pos_rows)
                            as_d = sum(x.get("as", 0) for x in pos_rows)
                            e_d = sum(x.get("e", 0) for x in pos_rows)
                            dp_d = sum(x.get("dp", 0) for x in pos_rows)
                            ej_d = round(sum(float(x.get("ej", 0) or 0) for x in pos_rows), 2)
                            lt_d = po_d + as_d + e_d
                            pdf_d = round((po_d + as_d) / lt_d, 3) if lt_d > 0 else 0.0
                            rebuilt_def.append({"jug_id": jid, "name": det["name"], "pos": pos_rows[0]["pos"], "jj": jj_d, "po": po_d, "as": as_d, "e": e_d, "dp": dp_d, "ej": ej_d, "pdf": pdf_d})
                    if rebuilt_def:
                        td["defense"] = rebuilt_def
                        print(f"       [BACKUP jugador.php] Defensiva de Relámpago T{c_info['number']}: {len(rebuilt_def)} defensores.")

            # Respaldo para rivales desde lideresV1.php
            rivals_missing_bat = [tn for tn, td in teams_data.items() if not td["is_ours"] and not td["batting"]]
            if rivals_missing_bat and torneo_tiene_juegos:
                lid_bat_url = f"lideresV1.php?lig={lig_id}&cam={cam_id}&dep=AVE"
                lid_pic_url = f"lideresV1.php?lig={lig_id}&cam={cam_id}&dep=EFE"
                lid_bat_html = browser.get(lid_bat_url, wait_ms=700) if (use_browser_for_stats and browser.available) else fetch_html(lid_bat_url, referer=cam_url_full)
                lid_pic_html = browser.get(lid_pic_url, wait_ms=700) if (use_browser_for_stats and browser.available) else fetch_html(lid_pic_url, referer=cam_url_full)
                lid_bat_by_t = parse_lideres_table(lid_bat_html, "bat")
                lid_pic_by_t = parse_lideres_table(lid_pic_html, "pic")
                filled_r = 0
                for tn, td in teams_data.items():
                    tk = norm_text(tn)
                    if not td["batting"] and tk in lid_bat_by_t:
                        td["batting"] = lid_bat_by_t[tk]
                        filled_r += 1
                    if not td["pitching"] and tk in lid_pic_by_t:
                        td["pitching"] = lid_pic_by_t[tk]
                if filled_r:
                    print(f"       [BACKUP lideresV1.php] Estadísticas de {filled_r} equipos recuperadas desde Líderes.")

            tournaments_out.append({
                "cam_id": cam_id, "number": c_info["number"], "name": c_info["name"], "squad": c_info["squad"],
                "standings_blocks": standings_blocks, "games": games,
                "teams": teams_data, "relampago_player_details": player_details,
            })
    finally:
        browser.close()

    snapshot = {
        "extracted_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "league_id": lig_id,
        "league_name": cfg.get("league_name", "Liga de Softbol VENEZUELA-UNIMET"),
        "tournaments": tournaments_out,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    total_bat = snapshot_has_real_stats(snapshot)
    print(f"[OK] Snapshot v6 guardado en {output_path} ({len(tournaments_out)} torneos, {total_bat} bateadores totales).")


if __name__ == "__main__":
    cfg_p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("config_softbol.json")
    out_p = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/softbol_snapshot.json")
    run_extraction(cfg_p, out_p)
