#!/usr/bin/env python3
"""
Extractor automático — Liga de Softbol VENEZUELA-UNIMET (beisbolysoftbol.com)
=============================================================================
Sin dependencias externas y SIN necesidad de contraseñas (página pública).

Extrae automáticamente para todos los torneos donde participa Relámpago (>= Torneo 87):
  1. Tablas de posiciones (Eliminatoria, Semifinal, Final)
  2. Todos los resultados de juegos (Visitante vs Local y marcadores)
  3. Estadísticas completas de TODOS los equipos: Ofensiva, Pitcheo y Defensiva
  4. Fichas individuales de los jugadores de Relámpago (posiciones defensivas reales
     AL CAMPO + historial juego a juego)

Guarda todo en `data/softbol_snapshot.json`.
"""

import html
import json
import re
import sys
import time
import unicodedata
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


def fetch_html(url: str, retries: int = 2) -> str:
    full_url = url if url.startswith("http") else urllib.parse.urljoin(BASE_SITE, url.lstrip("/"))
    # Codificar espacios en querystring si los hay
    parsed = urllib.parse.urlsplit(full_url)
    safe_url = urllib.parse.urlunsplit((
        parsed.scheme, parsed.netloc,
        urllib.parse.quote(parsed.path, safe="/"),
        urllib.parse.quote(parsed.query, safe="=&%+-_."),
        parsed.fragment,
    ))
    req = urllib.request.Request(safe_url, headers=HEADERS)
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = resp.read()
                try:
                    return raw.decode("utf-8")
                except UnicodeDecodeError:
                    return raw.decode("latin-1", errors="replace")
        except Exception as e:
            if attempt < retries:
                time.sleep(0.8)
            else:
                print(f"[WARN] No se pudo leer {safe_url}: {e}")
                return ""
    return ""


class TableAndLinkParser(HTMLParser):
    """Extrae todas las tablas HTML (con texto y enlaces de cada celda) + enlaces globales + encabezados."""
    def __init__(self) -> None:
        super().__init__()
        self.all_links: List[Tuple[str, str]] = []
        self.tables: List[Dict[str, Any]] = []
        self._in_a = False
        self._cur_href = ""
        self._cur_a_text: List[str] = []

        self._table_depth = 0
        self._cur_table: Optional[Dict[str, Any]] = None
        self._in_tr = False
        self._cur_row: List[Dict[str, Any]] = []
        self._in_cell = False
        self._cur_cell_text: List[str] = []
        self._cur_cell_links: List[Tuple[str, str]] = []
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
            self._table_depth += 1
            if self._table_depth == 1:
                self._cur_table = {"heading": self._last_heading, "rows": []}
        elif t == "tr" and self._table_depth == 1 and self._cur_table is not None:
            self._in_tr = True
            self._cur_row = []
        elif t in ("td", "th") and self._in_tr:
            self._in_cell = True
            self._cur_cell_text = []
            self._cur_cell_links = []

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
                if self._in_cell:
                    self._cur_cell_links.append((self._cur_href, txt))
            self._cur_href = ""
        elif t in ("td", "th") and self._in_cell:
            self._in_cell = False
            self._cur_row.append({
                "text": clean_cell("".join(self._cur_cell_text)),
                "links": list(self._cur_cell_links),
            })
        elif t == "tr" and self._in_tr:
            self._in_tr = False
            if self._cur_row and self._cur_table is not None:
                self._cur_table["rows"].append(self._cur_row)
        elif t == "table":
            if self._table_depth == 1 and self._cur_table is not None:
                if self._cur_table["rows"]:
                    self.tables.append(self._cur_table)
                self._cur_table = None
            self._table_depth = max(0, self._table_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self._cur_heading.append(data)
        if self._in_a:
            self._cur_a_text.append(data)
        if self._in_cell:
            self._cur_cell_text.append(data)


def parse_page(html_str: str) -> TableAndLinkParser:
    p = TableAndLinkParser()
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
    """
    Normaliza los formatos peculiares de beisbolysoftbol.com:
      '.600' -> 0.600 | '.1000' -> 1.000 | '889' -> 0.889 | '1266' -> 1.266 | '---' -> 0.0
    """
    s = str(val or "").strip().replace(",", ".")
    if not s or "---" in s or "nan" in s.lower():
        return 0.0
    if s in (".1000", "1000", "1.000"):
        return 1.0
    if s.startswith(".") and len(s) >= 5 and s[1:].isdigit():
        # Ej. '.1000' -> 1.000, '.1266' -> 1.266, '.2000' -> 2.000
        return round(int(s[1:]) / 1000.0, 3)
    try:
        num = float(s)
    except ValueError:
        return 0.0
    if num > 5.0:
        # Formato entero en milésimas (ej. 889 -> 0.889, 1266 -> 1.266)
        num = num / 1000.0
    if not allow_above_one and num > 1.0:
        num = min(1.0, num)
    return round(num, 3)


def parse_innings(val: Any) -> float:
    """Convierte innings tipo '5.2' (5 y 2/3) a innings reales (5.667) para EFE/WHIP."""
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
    if "campo corto" in s or "short stop" in s or "shortstop" in s or "ss" == s or "(6)" in s:
        return "SS"
    if "izquierd" in s or "left" in s or "lf" == s or "(7)" in s:
        return "LF"
    if "central" in s or "center" in s or "cf" == s or "(8)" in s:
        return "CF"
    if "derech" in s or "right" in s or "rf" == s or "(9)" in s:
        return "RF"
    if "short field" in s or "shortfield" in s or "sf" == s or "(10)" in s or "4to" in s or "cuarto" in s or "(11)" in s:
        return "SF"
    if "design" in s or "bd" == s or "dh" == s or "bateador" in s or "ep" == s:
        return "BD"
    return raw.strip()


def find_header_row(rows: List[List[Dict[str, Any]]], required_any: Tuple[str, ...]) -> Tuple[int, List[str]]:
    for idx, row in enumerate(rows[:4]):
        cols = [norm_text(c["text"]) for c in row]
        if any(any(req == col or req in col for col in cols) for req in required_any):
            return idx, cols
    return -1, []


def col_val(row: List[Dict[str, Any]], headers: List[str], *aliases: str) -> str:
    for al in aliases:
        al_n = norm_text(al)
        for i, h in enumerate(headers):
            if i < len(row) and (h == al_n or (len(al_n) >= 3 and al_n in h)):
                return row[i]["text"]
    return ""


# ==============================================================================
# PARSERS POR PÁGINA DE BEISBOLYSOFTBOL.COM
# ==============================================================================

def discover_tournaments(league_html: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Encuentra todos los campeonatos en liga.php y filtra los de Relámpago >= min_tournament_number."""
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
            cams[cid] = {
                "cam_id": cid,
                "number": t_num,
                "name": name,
                "squad": squad,
                "url": href,
            }

    ordered = sorted(cams.values(), key=lambda x: (-x["number"], -int(x["cam_id"]) if x["cam_id"].isdigit() else 0))
    return ordered


def parse_campeonato_standings(cam_html: str) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Extrae todas las tablas de posiciones (Eliminatoria/Semifinal/Final) y mapa de equipos con equ_id."""
    p = parse_page(cam_html)
    standings_blocks: List[Dict[str, Any]] = []
    teams_found: Dict[str, Dict[str, Any]] = {}

    for tbl in p.tables:
        rows = tbl["rows"]
        h_idx, headers = find_header_row(rows, ("pts", "ca", "cp", "avg"))
        if h_idx < 0 or ("ca" not in headers and "pts" not in headers):
            continue

        # Buscar título de fase (ej. "Torneo 87 Lanz Lento - Eliminatoria" o en la fila anterior)
        phase_title = tbl.get("heading") or "Eliminatoria"
        if h_idx > 0 and rows[0]:
            first_txt = rows[0][0]["text"]
            if len(first_txt) > 4:
                phase_title = first_txt
        # Detectar si el título viene en la primera celda del header
        for c in rows[h_idx]:
            if "torneo" in norm_text(c["text"]) or "equipos participantes" in norm_text(c["text"]):
                phase_title = c["text"]
                break

        parsed_rows = []
        for r in rows[h_idx + 1:]:
            if len(r) < 6:
                continue
            # Buscar celda con enlace a equipo.php o texto de nombre
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
                # Fallback: segunda celda
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
                "pos": len(parsed_rows) + 1,
                "equ_id": equ_id,
                "team": team_name,
                "j": j, "g": g, "p": pr, "e": e,
                "ca": ca, "cp": cp, "df": df,
                "avg": avg, "pts": pts,
            })

            if equ_id and equ_id not in teams_found:
                teams_found[equ_id] = {"equ_id": equ_id, "name": team_name}

        if parsed_rows:
            standings_blocks.append({"phase": phase_title, "rows": parsed_rows})

    # También capturar cualquier equipo.php enlazado fuera de tablas
    for href, txt in p.all_links:
        if "equipo.php" in href.lower() and txt:
            eid = extract_query_param(href, "equ")
            if eid and eid not in teams_found:
                teams_found[eid] = {"equ_id": eid, "name": txt}

    return standings_blocks, teams_found


def parse_all_results(res_html: str) -> List[Dict[str, Any]]:
    """Extrae todos los resultados desde todosresultados.php."""
    p = parse_page(res_html)
    games: List[Dict[str, Any]] = []
    seen = set()

    for tbl in p.tables:
        rows = tbl["rows"]
        h_idx, headers = find_header_row(rows, ("visitante", "local", "boxscore", "fecha"))
        if h_idx < 0:
            continue
        for r in rows[h_idx + 1:]:
            if len(r) < 3:
                continue
            nj = r[0]["text"]
            date_str = r[1]["text"] if len(r) > 1 else ""
            # Unir las celdas de marcador entre fecha y boxscore
            mid_cells = [c["text"] for c in r[2:] if norm_text(c["text"]) not in ("ver", "boxscore", "")]
            blob = " ".join(mid_cells)
            # Buscar patrón "Equipo A (11) - (7) Equipo B"
            m = re.search(r"(.+?)\s*\(\s*(\d+)\s*\)\s*[-–]\s*\(\s*(\d+)\s*\)\s*(.+)", blob)
            if not m:
                continue
            vis_name = clean_cell(m.group(1))
            vis_score = int(m.group(2))
            loc_score = int(m.group(3))
            loc_name = clean_cell(m.group(4))

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
                "jue_id": jue_id,
                "nj": nj,
                "date": date_str,
                "visitor": vis_name,
                "visitor_score": vis_score,
                "local": loc_name,
                "local_score": loc_score,
            })
    return games


def parse_team_batting(html_str: str) -> List[Dict[str, Any]]:
    """Extrae tabla de ofensiva desde estadisticasequipo.php?...&est=ofe."""
    p = parse_page(html_str)
    players: List[Dict[str, Any]] = []
    for tbl in p.tables:
        rows = tbl["rows"]
        h_idx, headers = find_header_row(rows, ("vb", "avg", "slg", "ops", "pde"))
        if h_idx < 0 or "vb" not in headers:
            continue
        for r in rows[h_idx + 1:]:
            if len(r) < 6:
                continue
            name = ""
            jug_id = ""
            for c in r[:3]:
                for href, ltxt in c["links"]:
                    if "jugador.php" in href.lower():
                        jug_id = extract_query_param(href, "jug")
                        name = ltxt or c["text"]
                        break
                if name:
                    break
            if not name:
                # Buscar primera celda no numérica
                for c in r[:3]:
                    if c["text"] and not re.fullmatch(r"[\d.\-]+", c["text"]):
                        name = c["text"]
                        break
            if not name or any(k in norm_text(name) for k in ("total", "equipo", "promedio", "jugador")):
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

            # Recalcular tasas exactas (más confiables que formatos truncados)
            avg = round(h / vb, 3) if vb > 0 else parse_baseball_rate(col_val(r, headers, "avg", "ave"))
            denom_obp = al if al >= (vb + bb + gp + sf) and al > 0 else (vb + bb + gp + sf)
            obp = round((h + bb + gp) / denom_obp, 3) if denom_obp > 0 else parse_baseball_rate(col_val(r, headers, "pde", "obp"))
            # Validar contra PDE publicado si hay SF no listado
            pde_pub = parse_baseball_rate(col_val(r, headers, "pde", "obp"))
            if pde_pub > 0 and obp == 0:
                obp = pde_pub
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


def parse_team_pitching(html_str: str) -> List[Dict[str, Any]]:
    """Extrae tabla de pitcheo desde estadisticasequipo.php?...&est=pic."""
    p = parse_page(html_str)
    pitchers: List[Dict[str, Any]] = []
    for tbl in p.tables:
        rows = tbl["rows"]
        h_idx, headers = find_header_row(rows, ("efe", "era", "il", "ip", "el", "cl"))
        if h_idx < 0:
            continue
        for r in rows[h_idx + 1:]:
            if len(r) < 5:
                continue
            name = ""
            jug_id = ""
            for c in r[:3]:
                for href, ltxt in c["links"]:
                    if "jugador.php" in href.lower():
                        jug_id = extract_query_param(href, "jug")
                        name = ltxt or c["text"]
                        break
                if name:
                    break
            if not name:
                for c in r[:3]:
                    if c["text"] and not re.fullmatch(r"[\d.\-]+", c["text"]):
                        name = c["text"]
                        break
            if not name or any(k in norm_text(name) for k in ("total", "equipo", "promedio", "jugador", "lanzador")):
                continue

            jj = to_int(col_val(r, headers, "jj", "j"))
            ji = to_int(col_val(r, headers, "ji", "gs"))
            g = to_int(col_val(r, headers, "g", "jg", "w"))
            pr = to_int(col_val(r, headers, "p", "jp", "l"))
            s = to_int(col_val(r, headers, "s", "js", "sv"))
            ip_raw = to_float(col_val(r, headers, "il", "ip", "el", "ej"))
            ip_real = parse_innings(ip_raw)
            h = to_int(col_val(r, headers, "h", "hc", "hp"))
            ca = to_int(col_val(r, headers, "ca", "cp"))
            cl = to_int(col_val(r, headers, "cl", "er"))
            bb = to_int(col_val(r, headers, "bb"))
            k = to_int(col_val(r, headers, "k", "so"))
            hr = to_int(col_val(r, headers, "hr"))
            efe_pub = to_float(col_val(r, headers, "efe", "era"))
            # En softbol (7 innings) EFE = CL * 7 / IP si no viene publicada
            efe = round(efe_pub, 2) if efe_pub > 0 else (round(cl * 7.0 / ip_real, 2) if ip_real > 0 else 0.0)
            whip = round((h + bb) / ip_real, 2) if ip_real > 0 else to_float(col_val(r, headers, "whip"))

            pitchers.append({
                "jug_id": jug_id, "name": name,
                "jj": jj, "ji": ji, "g": g, "p": pr, "s": s,
                "ip": ip_raw, "ip_real": round(ip_real, 2),
                "h": h, "ca": ca, "cl": cl, "bb": bb, "k": k, "hr": hr,
                "efe": efe, "whip": whip,
            })
        if pitchers:
            break
    return pitchers


def parse_team_defense(html_str: str) -> List[Dict[str, Any]]:
    """Extrae tabla de defensiva general del equipo desde estadisticasequipo.php?...&est=def."""
    p = parse_page(html_str)
    fielders: List[Dict[str, Any]] = []
    for tbl in p.tables:
        rows = tbl["rows"]
        h_idx, headers = find_header_row(rows, ("po", "as", "pdf", "lt", "ej"))
        if h_idx < 0:
            continue
        for r in rows[h_idx + 1:]:
            if len(r) < 5:
                continue
            name = ""
            jug_id = ""
            for c in r[:3]:
                for href, ltxt in c["links"]:
                    if "jugador.php" in href.lower():
                        jug_id = extract_query_param(href, "jug")
                        name = ltxt or c["text"]
                        break
                if name:
                    break
            if not name:
                for c in r[:3]:
                    if c["text"] and not re.fullmatch(r"[\d.\-]+", c["text"]):
                        name = c["text"]
                        break
            if not name or any(k in norm_text(name) for k in ("total", "equipo", "promedio", "jugador", "al campo")):
                continue

            jj = to_int(col_val(r, headers, "jj", "j"))
            po = to_int(col_val(r, headers, "po"))
            asist = to_int(col_val(r, headers, "as", "a"))
            err = to_int(col_val(r, headers, "e", "err"))
            dp = to_int(col_val(r, headers, "dp"))
            ej = to_float(col_val(r, headers, "ej", "il", "ip"))
            lt = po + asist + err
            pdf = round((po + asist) / lt, 3) if lt > 0 else parse_baseball_rate(col_val(r, headers, "pdf", "fld"))

            fielders.append({
                "jug_id": jug_id, "name": name,
                "jj": jj, "po": po, "as": asist, "e": err, "dp": dp, "ej": ej, "pdf": pdf,
            })
        if fielders:
            break
    return fielders


def parse_player_detail(html_str: str) -> Dict[str, Any]:
    """Extrae defensiva POR POSICIÓN (`AL CAMPO`) y juego-a-juego de un jugador desde jugador.php."""
    p = parse_page(html_str)
    positions: List[Dict[str, Any]] = []
    game_log: List[Dict[str, Any]] = []

    for tbl in p.tables:
        rows = tbl["rows"]
        # Tabla Defensiva por posición: AL CAMPO | JJ | PO | AS | E | DP | ... | EJ | PDF
        h_def, headers_def = find_header_row(rows, ("al campo",))
        if h_def >= 0:
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
                ej = to_float(col_val(r, headers_def, "ej"))
                lt = po + asist + err
                pdf = round((po + asist) / lt, 3) if lt > 0 else parse_baseball_rate(col_val(r, headers_def, "pdf"))
                positions.append({
                    "pos": pos_code, "pos_raw": pos_raw,
                    "jj": jj, "po": po, "as": asist, "e": err, "dp": dp, "ej": ej, "pdf": pdf,
                })
            continue

        # Tabla Juego a Juego ofensivo: NJ | DIA | VS | VB | H | H2 | H3 | HR | CI | CA | BB | K
        h_log, headers_log = find_header_row(rows, ("dia", "vs"))
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

    return {"positions": positions, "game_log": game_log}


# ==============================================================================
# FLUJO PRINCIPAL
# ==============================================================================

def run_extraction(config_path: Path, output_path: Path) -> None:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    lig_id = cfg["league_id"]
    our_kw = norm_text(cfg.get("our_team_keyword", "Relampago"))

    print(f"[INFO] Leyendo liga {lig_id}: {cfg['league_url']}")
    league_html = fetch_html(cfg["league_url"])
    if not league_html:
        print("[ERROR] No se pudo conectar con beisbolysoftbol.com.")
        sys.exit(1)

    candidates = discover_tournaments(league_html, cfg)
    print(f"[INFO] Campeonatos candidatos (>= T{cfg.get('min_tournament_number', 87)}): {[(c['name'], c['cam_id'], c['squad']) for c in candidates]}")

    tournaments_out: List[Dict[str, Any]] = []

    for c_info in candidates:
        cam_id = c_info["cam_id"]
        cam_url = f"campeonato.php?lig={lig_id}&cam={cam_id}"
        cam_html = fetch_html(cam_url)
        standings_blocks, teams_map = parse_campeonato_standings(cam_html)

        # Verificar si Relámpago participa en este torneo
        has_relampago = any(our_kw in norm_text(t["name"]) for t in teams_map.values())
        if not has_relampago:
            # Revisar también en texto de standings
            has_relampago = any(
                our_kw in norm_text(r["team"])
                for blk in standings_blocks for r in blk["rows"]
            )
        if not has_relampago:
            print(f"[SKIP] {c_info['name']} (cam={cam_id}): no participa {cfg['our_team_display']}.")
            continue

        print(f"[INFO] Procesando {c_info['name']} (cam={cam_id}, Equipo {c_info['squad']}) — {len(teams_map)} equipos...")

        # 1. Todos los resultados del torneo
        res_html = fetch_html(f"todosresultados.php?lig={lig_id}&cam={cam_id}")
        games = parse_all_results(res_html)
        print(f"       Resultados extraídos: {len(games)} juegos.")

        # 2. Estadísticas de TODOS los equipos del torneo
        teams_data: Dict[str, Dict[str, Any]] = {}
        relampago_player_ids: Dict[str, str] = {}

        for equ_id, t_meta in teams_map.items():
            tname = t_meta["name"]
            is_ours = our_kw in norm_text(tname)

            ofe_html = fetch_html(f"estadisticasequipo.php?equ={equ_id}&lig={lig_id}&cam={cam_id}&est=ofe")
            pic_html = fetch_html(f"estadisticasequipo.php?equ={equ_id}&lig={lig_id}&cam={cam_id}&est=pic")
            def_html = fetch_html(f"estadisticasequipo.php?equ={equ_id}&lig={lig_id}&cam={cam_id}&est=def")

            batting = parse_team_batting(ofe_html)
            pitching = parse_team_pitching(pic_html)
            defense = parse_team_defense(def_html)

            if is_ours:
                for lst in (batting, pitching, defense):
                    for p in lst:
                        if p.get("jug_id"):
                            relampago_player_ids[p["jug_id"]] = p["name"]

            teams_data[tname] = {
                "equ_id": equ_id,
                "name": tname,
                "is_ours": is_ours,
                "batting": batting,
                "pitching": pitching,
                "defense": defense,
            }
            time.sleep(0.08)

        # 3. Fichas detalladas (defensiva POR POSICIÓN + game log) de nuestros jugadores de Relámpago
        player_details: Dict[str, Dict[str, Any]] = {}
        if relampago_player_ids:
            print(f"       Extrayendo posiciones defensivas de {len(relampago_player_ids)} jugadores de Relámpago...")
            for jug_id, pname in relampago_player_ids.items():
                j_html = fetch_html(f"jugador.php?jug={jug_id}&cam={cam_id}")
                if j_html:
                    det = parse_player_detail(j_html)
                    det["name"] = pname
                    det["jug_id"] = jug_id
                    player_details[jug_id] = det
                time.sleep(0.06)

        tournaments_out.append({
            "cam_id": cam_id,
            "number": c_info["number"],
            "name": c_info["name"],
            "squad": c_info["squad"],
            "standings_blocks": standings_blocks,
            "games": games,
            "teams": teams_data,
            "relampago_player_details": player_details,
        })

    snapshot = {
        "extracted_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "league_id": lig_id,
        "league_name": cfg.get("league_name", "Liga de Softbol VENEZUELA-UNIMET"),
        "tournaments": tournaments_out,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Snapshot de softbol guardado en {output_path} ({len(tournaments_out)} torneos de Relámpago).")


if __name__ == "__main__":
    cfg_p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("config_softbol.json")
    out_p = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/softbol_snapshot.json")
    run_extraction(cfg_p, out_p)
