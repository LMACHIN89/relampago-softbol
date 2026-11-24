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
            name = clean_cell(txt) or f"Campeonato {cid}"
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


def parse_player_detail(html_str: str) -> Dict[str, Any]:
    """Extrae defensiva POR POSICIÓN (`AL CAMPO`), pitcheo (si lanzó) y juego-a-juego desde jugador.php."""
    p = parse_page(html_str)
    positions: List[Dict[str, Any]] = []
    game_log: List[Dict[str, Any]] = []
    pitching_summary: Optional[Dict[str, Any]] = None

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
                asist = to_int(col_val(r, headers_def, "as"))
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

        # 2. Tabla de Pitcheo individual (si el jugador lanzó)
        h_pic, headers_pic = find_header_row(rows, ("efe", "era", "il", "el", "cl", "bb", "k"), min_hits=4)
        if h_pic >= 0 and "vb" not in headers_pic and "al campo" not in headers_pic:
            # Buscar fila de Totales o sumar juego a juego
            tot_row = None
            for r in rows[h_pic + 1:]:
                if any("total" in norm_text(c["text"]) for c in r[:3]):
                    tot_row = r
                    break
            if tot_row and len(tot_row) >= 5:
                ip_raw = to_float(col_val(tot_row, headers_pic, "il", "el", "ip", "inn"))
                ip_real = parse_innings(ip_raw)
                h = to_int(col_val(tot_row, headers_pic, "h", "hc", "hp"))
                cl = to_int(col_val(tot_row, headers_pic, "cl", "er"))
                ca = to_int(col_val(tot_row, headers_pic, "cp", "ca", "c"))
                bb = to_int(col_val(tot_row, headers_pic, "bb"))
                k = to_int(col_val(tot_row, headers_pic, "k", "so"))
                hr = to_int(col_val(tot_row, headers_pic, "hr"))
                g = to_int(col_val(tot_row, headers_pic, "jg", "g"))
                pr = to_int(col_val(tot_row, headers_pic, "jp", "p"))
                efe_pub = to_float(col_val(tot_row, headers_pic, "efe", "era"))
                efe = round(efe_pub, 2) if efe_pub > 0 else (round(cl * 7.0 / ip_real, 2) if ip_real > 0 else 0.0)
                whip = round((h + bb) / ip_real, 2) if ip_real > 0 else 0.0
                if ip_real > 0:
                    pitching_summary = {
                        "jj": max(1, len(rows) - h_pic - 2), "ji": 0, "g": g, "p": pr, "s": 0,
                        "ip": ip_raw, "ip_real": round(ip_real, 2),
                        "h": h, "ca": ca, "cl": cl, "bb": bb, "k": k, "hr": hr, "efe": efe, "whip": whip,
                    }
            continue

        # 3. Tabla Juego a Juego ofensivo
        h_log, headers_log = find_header_row(rows, ("dia", "vs", "vb"), min_hits=2)
        if h_log >= 0 and "vb" in headers_log:
            for r in rows[h_log + 1:]:
                if len(r) < 6:
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
                })

    return {"positions": positions, "game_log": game_log, "pitching_backup": pitching_summary}


# ==============================================================================
# FLUJO PRINCIPAL
# ==============================================================================

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
    prev_by_cam = load_previous_snapshot(output_path)

    print(f"[INFO] Leyendo liga {lig_id}: {cfg['league_url']}")
    league_html = fetch_html(cfg["league_url"])
    if not league_html:
        if prev_by_cam:
            print("[WARN] No se pudo conectar con beisbolysoftbol.com; conservando snapshot anterior intacto.")
            return
        print("[ERROR] No se pudo conectar con beisbolysoftbol.com.")
        sys.exit(1)

    candidates = discover_tournaments(league_html, cfg)
    print(f"[INFO] Campeonatos candidatos (>= T{cfg.get('min_tournament_number', 87)}): {[(c['name'], c['cam_id'], c['squad']) for c in candidates]}")

    tournaments_out: List[Dict[str, Any]] = []

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

        # Si el torneo tiene standings pero teams_map vino vacío (fallo temporal de enlaces), restaurar desde previo
        if not teams_map and prev_t.get("teams"):
            for tname, td in prev_t["teams"].items():
                if td.get("equ_id"):
                    teams_map[str(td["equ_id"])] = {"equ_id": str(td["equ_id"]), "name": tname}

        print(f"[INFO] Procesando {c_info['name']} (cam={cam_id}, Equipo {c_info['squad']}) — {len(teams_map)} equipos...")
        res_html = fetch_html(f"todosresultados.php?lig={lig_id}&cam={cam_id}", referer=cam_url_full)
        games = parse_all_results(res_html)
        if not games and prev_t.get("games"):
            games = prev_t["games"]

        teams_data: Dict[str, Dict[str, Any]] = {}
        relampago_player_ids: Dict[str, str] = {}
        relampago_roster_names: List[Dict[str, str]] = []
        cam_name_q = urllib.parse.quote(c_info["name"])

        for equ_id, t_meta in teams_map.items():
            tname = t_meta["name"]
            is_ours = our_kw in norm_text(tname)
            dbg = f"{tname} T{c_info['number']}" if is_ours else ""
            eq_ref = f"{BASE_SITE}equipo.php?equ={equ_id}&lig={lig_id}&cam={cam_id}"

            # 1) Pausa cortés para evitar bloqueos/rate-limit de beisbolysoftbol.com
            ofe_html = fetch_html(f"estadisticasequipo.php?equ={equ_id}&lig={lig_id}&cam={cam_id}&est=ofe&{cam_name_q}", referer=eq_ref)
            time.sleep(0.25)
            pic_html = fetch_html(f"estadisticasequipo.php?equ={equ_id}&lig={lig_id}&cam={cam_id}&est=pic&{cam_name_q}", referer=eq_ref)
            time.sleep(0.25)
            def_html = fetch_html(f"estadisticasequipo.php?equ={equ_id}&lig={lig_id}&cam={cam_id}&est=def&{cam_name_q}", referer=eq_ref)
            time.sleep(0.25)

            batting = parse_team_batting(ofe_html)
            pitching = parse_team_pitching(pic_html, debug_tag=dbg)
            defense = parse_team_defense(def_html, debug_tag=dbg)

            # Diagnóstico si Relámpago vino sin bateo pese a tener HTML
            if is_ours and not batting and ofe_html:
                snippet = re.sub(r"\s+", " ", ofe_html)[:260]
                print(f"       [DEBUG {dbg} est=ofe] 0 bateadores (len={len(ofe_html)}). Inicio HTML: {snippet}")

            # Protección anti-borrado: si vino vacío pero teníamos datos válidos previos, conservarlos
            prev_team = (prev_t.get("teams") or {}).get(tname, {})
            if not batting and prev_team.get("batting"):
                batting = prev_team["batting"]
                print(f"       [CACHE] Conservando bateo previo para {tname} ({len(batting)} jug.)")
            if not pitching and prev_team.get("pitching"):
                pitching = prev_team["pitching"]
                print(f"       [CACHE] Conservando pitcheo previo para {tname} ({len(pitching)} lanz.)")
            if not defense and prev_team.get("defense"):
                defense = prev_team["defense"]
                print(f"       [CACHE] Conservando defensa previa para {tname} ({len(defense)} def.)")

            if is_ours:
                ros_html = fetch_html(f"roster.php?equ={equ_id}&lig={lig_id}&cam={cam_id}&{cam_name_q}", referer=eq_ref)
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

        # Fichas detalladas de Relámpago (posiciones AL CAMPO + backup de pitcheo)
        player_details: Dict[str, Dict[str, Any]] = dict(prev_t.get("relampago_player_details") or {})
        if relampago_player_ids:
            print(f"       Leyendo fichas individuales de {len(relampago_player_ids)} jugadores de Relámpago...")
            for jug_id, pname in relampago_player_ids.items():
                j_html = fetch_html(f"jugador.php?jug={jug_id}&cam={cam_id}", referer=cam_url_full)
                if j_html:
                    det = parse_player_detail(j_html)
                    det["name"] = pname
                    det["jug_id"] = jug_id
                    if det["positions"] or det["game_log"] or det["pitching_backup"] or jug_id not in player_details:
                        player_details[jug_id] = det
                time.sleep(0.20)

        tournaments_out.append({
            "cam_id": cam_id, "number": c_info["number"], "name": c_info["name"], "squad": c_info["squad"],
            "standings_blocks": standings_blocks, "games": games,
            "teams": teams_data, "relampago_player_details": player_details,
        })

    snapshot = {
        "extracted_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "league_id": lig_id,
        "league_name": cfg.get("league_name", "Liga de Softbol VENEZUELA-UNIMET"),
        "tournaments": tournaments_out,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Snapshot v4 guardado en {output_path} ({len(tournaments_out)} torneos de Relámpago).")


if __name__ == "__main__":
    cfg_p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("config_softbol.json")
    out_p = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/softbol_snapshot.json")
    run_extraction(cfg_p, out_p)
