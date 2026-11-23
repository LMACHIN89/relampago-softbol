#!/usr/bin/env python3
"""
Compilador del Portal de Scouting — Relámpago del Caribe (Softbol UNIMET)
=========================================================================
Genera en `docs/`:
  - `docs/index.html`: Portada con Logo oficial de Relámpago, filtros por Equipo (A / B / Todos)
    y por Torneo (T90, T89, T87, Histórico), Generador Inteligente de Lineup Ofensivo + Defensivo
    (con Diamante SVG) + Recomendación de Pitcher según Rival, Tablas y Scouting de Rivales.
  - `docs/equipos/*.html`: Ficha completa de scouting de cada equipo rival (Ofensiva, Pitcheo,
    Defensiva, Historial de Juegos y H2H vs Relámpago).
  - Copia `logo_relampago.png` a `docs/logo_relampago.png`.

Uso normal:
    python generar_portal_softbol.py --config config_softbol.json --snapshot data/softbol_snapshot.json

Modo prueba:
    python generar_portal_softbol.py --demo
"""

import argparse
import csv
import json
import re
import shutil
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def norm_text(s: str) -> str:
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(s))
    asc = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", asc).strip().lower()


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm_text(s)).strip("-") or "equipo"


def load_manual_positions(csv_path: Path) -> Dict[str, Dict[str, Any]]:
    """Carga preferencias defensivas/pitcheo opcionales desde data/posiciones_manuales.csv."""
    out: Dict[str, Dict[str, Any]] = {}
    if not csv_path.exists():
        return out
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            name = (r.get("jugador") or r.get("name") or "").strip()
            if not name:
                continue
            out[norm_text(name)] = {
                "pos1": (r.get("pos_primaria") or "").strip().upper(),
                "pos2": (r.get("pos_secundaria") or "").strip().upper(),
                "is_pitcher": norm_text(r.get("es_pitcher") or "") in ("si", "yes", "1", "true"),
                "pitcher_role": (r.get("rol_pitcher") or "").strip(),
            }
    return out


def aggregate_batting(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Suma estadísticas de bateo de un jugador o equipo y recalcula AVG/OBP/SLG/OPS."""
    jj = sum(r.get("jj", 0) for r in rows)
    vb = sum(r.get("vb", 0) for r in rows)
    al = sum(r.get("al", 0) for r in rows)
    ca = sum(r.get("ca", 0) for r in rows)
    h = sum(r.get("h", 0) for r in rows)
    h2 = sum(r.get("h2", 0) for r in rows)
    h3 = sum(r.get("h3", 0) for r in rows)
    hr = sum(r.get("hr", 0) for r in rows)
    ci = sum(r.get("ci", 0) for r in rows)
    bb = sum(r.get("bb", 0) for r in rows)
    k = sum(r.get("k", 0) for r in rows)
    br = sum(r.get("br", 0) for r in rows)
    sf = sum(r.get("sf", 0) for r in rows)
    gp = sum(r.get("gp", 0) for r in rows)

    avg = round(h / vb, 3) if vb > 0 else 0.0
    denom_obp = max(al, vb + bb + gp + sf)
    obp = round((h + bb + gp) / denom_obp, 3) if denom_obp > 0 else 0.0
    tb = h + h2 + 2 * h3 + 3 * hr
    slg = round(tb / vb, 3) if vb > 0 else 0.0
    ops = round(obp + slg, 3)
    return {
        "jj": jj, "vb": vb, "al": denom_obp, "ca": ca, "h": h, "h2": h2, "h3": h3,
        "hr": hr, "ci": ci, "bb": bb, "k": k, "br": br, "sf": sf, "gp": gp,
        "avg": avg, "obp": obp, "slg": slg, "ops": ops,
    }


def aggregate_pitching(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    jj = sum(r.get("jj", 0) for r in rows)
    ji = sum(r.get("ji", 0) for r in rows)
    g = sum(r.get("g", 0) for r in rows)
    p = sum(r.get("p", 0) for r in rows)
    s = sum(r.get("s", 0) for r in rows)
    ip_real = round(sum(float(r.get("ip_real", r.get("ip", 0)) or 0) for r in rows), 2)
    h = sum(r.get("h", 0) for r in rows)
    ca = sum(r.get("ca", 0) for r in rows)
    cl = sum(r.get("cl", 0) for r in rows)
    bb = sum(r.get("bb", 0) for r in rows)
    k = sum(r.get("k", 0) for r in rows)
    hr = sum(r.get("hr", 0) for r in rows)

    efe = round(cl * 7.0 / ip_real, 2) if ip_real > 0 else 0.0
    whip = round((h + bb) / ip_real, 2) if ip_real > 0 else 0.0
    bb7 = round(bb * 7.0 / ip_real, 2) if ip_real > 0 else 0.0
    k7 = round(k * 7.0 / ip_real, 2) if ip_real > 0 else 0.0
    hr7 = round(hr * 7.0 / ip_real, 2) if ip_real > 0 else 0.0
    return {
        "jj": jj, "ji": ji, "g": g, "p": p, "s": s,
        "ip": ip_real, "h": h, "ca": ca, "cl": cl, "bb": bb, "k": k, "hr": hr,
        "efe": efe, "whip": whip, "bb7": bb7, "k7": k7, "hr7": hr7,
    }


def aggregate_defense(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    jj = sum(r.get("jj", 0) for r in rows)
    po = sum(r.get("po", 0) for r in rows)
    asist = sum(r.get("as", 0) for r in rows)
    e = sum(r.get("e", 0) for r in rows)
    dp = sum(r.get("dp", 0) for r in rows)
    ej = round(sum(float(r.get("ej", 0) or 0) for r in rows), 1)
    lt = po + asist + e
    pdf = round((po + asist) / lt, 3) if lt > 0 else 0.0
    return {"jj": jj, "po": po, "as": asist, "e": e, "dp": dp, "ej": ej, "pdf": pdf}


def classify_opponent_offense(team_bat: Dict[str, Any], games_played: int) -> Dict[str, Any]:
    """Clasifica el perfil ofensivo de un rival para recomendar el mejor pitcher."""
    j = max(games_played, 1)
    hr_pg = team_bat["hr"] / j
    bb_pg = team_bat["bb"] / j
    if team_bat["vb"] < 15:
        return {"style": "Muestra baja", "tag": "Sin datos suficientes", "pitcher_focus": "balanced", "desc": "Pocos turnos registrados aún; priorizar abridor con mejor WHIP y control."}
    if team_bat["slg"] >= 0.500 or hr_pg >= 0.7:
        return {"style": "Poder / Jonroneros", "tag": "Peligro de poder", "pitcher_focus": "anti_power", "desc": f"Alto SLG ({team_bat['slg']:.3f}) y {team_bat['hr']} HR. Conviene pitcher que limite batazos largos (menor EFE y HR/7) y mantenga la bola bajita."}
    if team_bat["obp"] >= 0.430 and bb_pg >= 2.2:
        return {"style": "Pacientes / Embasadores", "tag": "Toman boletos", "pitcher_focus": "command", "desc": f"OBP de {team_bat['obp']:.3f} con {bb_pg:.1f} BB/juego. Clave usar pitcher de máximo control (menor BB/7 y WHIP) para no regalar bases."}
    if team_bat["avg"] >= 0.340:
        return {"style": "Contacto / Línea", "tag": "Bateo de contacto", "pitcher_focus": "whip_def", "desc": f"AVG colectivo de {team_bat['avg']:.3f}. Priorizar pitcher de bajo WHIP respaldado por nuestra mejor defensa en el centro del cuadro."}
    return {"style": "Ofensiva controlada", "tag": "Rival atacable", "pitcher_focus": "balanced", "desc": f"AVG de {team_bat['avg']:.3f} y OPS de {team_bat['ops']:.3f}. Ideal para atacar la zona con strikes y darle innings a la rotación."}


def build_view_for_tournaments(
    view_id: str,
    view_label: str,
    squad_tag: str,
    selected_tournaments: List[Dict[str, Any]],
    dual_squad_players: set,
    manual_pos: Dict[str, Dict[str, Any]],
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    """Compila todos los datos filtrados para una vista (Torneo específico, Equipo A, Equipo B o Global)."""
    our_kw = norm_text(cfg.get("our_team_keyword", "Relampago"))
    our_display = cfg.get("our_team_display", "Relámpago del Caribe")

    # 1. Consolidar tablas de posiciones (si es 1 torneo mostramos sus fases reales; si son varios, mostramos la más reciente)
    standings_blocks = selected_tournaments[0].get("standings_blocks", []) if len(selected_tournaments) == 1 else []

    # 2. Consolidar juegos de los torneos seleccionados
    all_games = []
    for t in selected_tournaments:
        for g in t.get("games", []):
            gc = dict(g)
            gc["tournament"] = t["name"]
            gc["squad"] = t["squad"]
            all_games.append(gc)

    # 3. Consolidar estadísticas por equipo
    teams_bat_raw: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    teams_pic_raw: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    teams_def_raw: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    team_records: Dict[str, Dict[str, int]] = defaultdict(lambda: {"j": 0, "g": 0, "p": 0, "e": 0, "ca": 0, "cp": 0, "pts": 0})
    team_is_ours: Dict[str, bool] = {}

    # Para Relámpago: agregar por jugador (bates, pitcheo, posiciones defensivas reales)
    our_bat_by_p: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    our_pic_by_p: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    our_def_by_p: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    our_pos_by_p: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    our_display_names: Dict[str, str] = {}

    for t in selected_tournaments:
        # Tomar récord de Eliminatoria desde standings_blocks[0]
        if t.get("standings_blocks"):
            for r in t["standings_blocks"][0].get("rows", []):
                tn = r["team"]
                team_records[tn]["j"] += r.get("j", 0)
                team_records[tn]["g"] += r.get("g", 0)
                team_records[tn]["p"] += r.get("p", 0)
                team_records[tn]["e"] += r.get("e", 0)
                team_records[tn]["ca"] += r.get("ca", 0)
                team_records[tn]["cp"] += r.get("cp", 0)
                team_records[tn]["pts"] += r.get("pts", 0)
                if our_kw in norm_text(tn):
                    team_is_ours[tn] = True

        # Detalle de posiciones por jugador de Relámpago
        pdet = t.get("relampago_player_details", {})
        for jid, det in pdet.items():
            pn = norm_text(det.get("name", ""))
            if not pn:
                continue
            our_display_names[pn] = det["name"]
            for pos_row in det.get("positions", []):
                our_pos_by_p[pn][pos_row["pos"]].append(pos_row)

        for tname, tdata in t.get("teams", {}).items():
            is_ours = bool(tdata.get("is_ours")) or (our_kw in norm_text(tname))
            team_is_ours[tname] = is_ours
            teams_bat_raw[tname].extend(tdata.get("batting", []))
            teams_pic_raw[tname].extend(tdata.get("pitching", []))
            teams_def_raw[tname].extend(tdata.get("defense", []))

            if is_ours:
                for b in tdata.get("batting", []):
                    k = norm_text(b["name"])
                    our_display_names[k] = b["name"]
                    our_bat_by_p[k].append(b)
                for pc in tdata.get("pitching", []):
                    k = norm_text(pc["name"])
                    our_display_names[k] = pc["name"]
                    our_pic_by_p[k].append(pc)
                for df in tdata.get("defense", []):
                    k = norm_text(df["name"])
                    our_display_names[k] = df["name"]
                    our_def_by_p[k].append(df)

    # 4. Construir roster consolidado de Relámpago para esta vista (Ofensiva + Pitcheo + Posiciones Defensivas)
    all_our_keys = set(our_display_names.keys()) | set(our_bat_by_p.keys()) | set(our_pic_by_p.keys()) | set(our_def_by_p.keys())
    relampago_roster: List[Dict[str, Any]] = []

    for pk in sorted(all_our_keys):
        disp_name = our_display_names.get(pk, pk.title())
        bat = aggregate_batting(our_bat_by_p.get(pk, []))
        pic = aggregate_pitching(our_pic_by_p.get(pk, []))
        dfn = aggregate_defense(our_def_by_p.get(pk, []))

        # Posiciones defensivas reales agregadas + manual fallback
        pos_list = []
        for pos_code, plist in our_pos_by_p.get(pk, {}).items():
            agg_p = aggregate_defense(plist)
            agg_p["pos"] = pos_code
            pos_list.append(agg_p)
        pos_list.sort(key=lambda x: (-x["ej"], -x["jj"], -x["pdf"]))

        mp = manual_pos.get(pk, {})
        if not pos_list:
            if mp.get("pos1"):
                pos_list.append({"pos": mp["pos1"], "jj": 0, "po": 0, "as": 0, "e": 0, "dp": 0, "ej": 1.0, "pdf": 0.900})
            if mp.get("pos2"):
                pos_list.append({"pos": mp["pos2"], "jj": 0, "po": 0, "as": 0, "e": 0, "dp": 0, "ej": 0.5, "pdf": 0.850})
        if pic["ip"] > 0 and not any(x["pos"] == "P" for x in pos_list):
            pos_list.append({"pos": "P", "jj": pic["jj"], "po": 0, "as": 0, "e": 0, "dp": 0, "ej": pic["ip"], "pdf": dfn["pdf"] or 0.900})

        is_pitcher = (pic["ip"] > 0) or bool(mp.get("is_pitcher"))
        relampago_roster.append({
            "name": disp_name,
            "dual_squad": pk in dual_squad_players,
            "batting": bat,
            "pitching": pic,
            "defense": dfn,
            "positions": pos_list,
            "primary_pos": pos_list[0]["pos"] if pos_list else "UTIL",
            "is_pitcher": is_pitcher,
            "pitcher_role": mp.get("pitcher_role", ""),
        })

    relampago_roster.sort(key=lambda x: (-x["batting"]["ops"], -x["batting"]["vb"], x["name"]))

    # 5. Consolidar perfiles de TODOS los equipos (incluyendo rivales para el selector del simulador)
    teams_summary: List[Dict[str, Any]] = []
    rivals_profiles: List[Dict[str, Any]] = []
    our_kpis = {"j": 0, "g": 0, "p": 0, "e": 0, "ca": 0, "cp": 0, "df": 0, "avg": 0.0, "ops": 0.0, "efe": 0.0, "whip": 0.0}

    all_team_names = sorted(set(team_records.keys()) | set(teams_bat_raw.keys()))
    for tname in all_team_names:
        is_ours = team_is_ours.get(tname, our_kw in norm_text(tname))
        rec = team_records[tname]
        # Agregar bateo/pitcheo/defensa por jugador dentro del equipo
        p_bat_grp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        p_pic_grp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        p_def_grp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        p_names: Dict[str, str] = {}

        for b in teams_bat_raw.get(tname, []):
            k = norm_text(b["name"]); p_names[k] = b["name"]; p_bat_grp[k].append(b)
        for pc in teams_pic_raw.get(tname, []):
            k = norm_text(pc["name"]); p_names[k] = pc["name"]; p_pic_grp[k].append(pc)
        for df in teams_def_raw.get(tname, []):
            k = norm_text(df["name"]); p_names[k] = df["name"]; p_def_grp[k].append(df)

        bat_players = [{"name": p_names[k], **aggregate_batting(v)} for k, v in p_bat_grp.items()]
        bat_players.sort(key=lambda x: (-x["ops"], -x["vb"]))
        pic_players = [{"name": p_names[k], **aggregate_pitching(v)} for k, v in p_pic_grp.items()]
        pic_players.sort(key=lambda x: (x["efe"] if x["ip"] > 0 else 99, x["whip"]))
        def_players = [{"name": p_names[k], **aggregate_defense(v)} for k, v in p_def_grp.items()]
        def_players.sort(key=lambda x: (-x["e"], -x["jj"]))

        t_bat = aggregate_batting(bat_players)
        t_pic = aggregate_pitching(pic_players)
        t_def = aggregate_defense(def_players)
        profile = classify_opponent_offense(t_bat, rec["j"])

        # Juegos de este equipo y H2H contra Relámpago
        t_games = []
        h2h_games = []
        tn_norm = norm_text(tname)
        for gm in all_games:
            is_v = norm_text(gm["visitor"]) == tn_norm
            is_l = norm_text(gm["local"]) == tn_norm
            if not (is_v or is_l):
                continue
            sc_for = gm["visitor_score"] if is_v else gm["local_score"]
            sc_ag = gm["local_score"] if is_v else gm["visitor_score"]
            opp = gm["local"] if is_v else gm["visitor"]
            res = "G" if sc_for > sc_ag else ("P" if sc_for < sc_ag else "E")
            item = {
                "date": gm["date"], "tournament": gm["tournament"], "venue": "Visita" if is_v else "Local",
                "opponent": opp, "score_for": sc_for, "score_against": sc_ag, "result": res,
            }
            t_games.append(item)
            if not is_ours and our_kw in norm_text(opp):
                h2h_games.append(item)

        t_obj = {
            "name": tname,
            "slug": slugify(tname),
            "is_ours": is_ours,
            "j": rec["j"], "g": rec["g"], "p": rec["p"], "e": rec["e"],
            "ca": rec["ca"], "cp": rec["cp"], "df": rec["ca"] - rec["cp"], "pts": rec["pts"],
            "ca_pg": round(rec["ca"] / rec["j"], 1) if rec["j"] else 0.0,
            "cp_pg": round(rec["cp"] / rec["j"], 1) if rec["j"] else 0.0,
            "team_bat": t_bat,
            "team_pic": t_pic,
            "team_def": t_def,
            "profile": profile,
            "top_batters": bat_players[:3],
            "top_pitchers": pic_players[:2],
            "batting": bat_players,
            "pitching": pic_players,
            "defense": def_players,
            "games": t_games,
            "h2h_vs_relampago": h2h_games,
        }
        teams_summary.append(t_obj)

        if is_ours:
            our_kpis = {
                "j": rec["j"], "g": rec["g"], "p": rec["p"], "e": rec["e"],
                "ca": rec["ca"], "cp": rec["cp"], "df": rec["ca"] - rec["cp"],
                "avg": t_bat["avg"], "ops": t_bat["ops"], "efe": t_pic["efe"], "whip": t_pic["whip"],
            }
        else:
            rivals_profiles.append({
                "name": tname, "slug": slugify(tname),
                "j": rec["j"], "g": rec["g"], "p": rec["p"],
                "ca_pg": t_obj["ca_pg"], "cp_pg": t_obj["cp_pg"],
                "avg": t_bat["avg"], "obp": t_bat["obp"], "slg": t_bat["slg"], "ops": t_bat["ops"],
                "hr": t_bat["hr"], "bb": t_bat["bb"], "efe": t_pic["efe"],
                "profile": profile,
                "top_batters": [{"name": b["name"], "avg": b["avg"], "ops": b["ops"], "hr": b["hr"]} for b in bat_players[:3]],
            })

    teams_summary.sort(key=lambda x: (0 if x["is_ours"] else 1, -x["pts"], -x["g"], -x["df"], x["name"]))
    rivals_profiles.sort(key=lambda x: (-x["ops"], -x["g"], x["name"]))

    return {
        "id": view_id,
        "label": view_label,
        "squad": squad_tag,
        "our_kpis": our_kpis,
        "standings_blocks": standings_blocks,
        "relampago_roster": relampago_roster,
        "rivals_profiles": rivals_profiles,
        "teams": teams_summary,
        "games": all_games,
    }


def render_main_portal(portal_data: Dict[str, Any]) -> str:
    data_json = json.dumps(portal_data, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Scouting {portal_data['brand']} — Softbol UNIMET</title>
  <style>
    :root {{
      --navy: #0e2644;
      --navy-mid: #133150;
      --navy-soft: #e6eef7;
      --gold: #f0d72b;
      --gold-dark: #b48a04;
      --gold-soft: #fef9c3;
      --bg: #f3f5f8;
      --surface: #ffffff;
      --surface-alt: #f8fafc;
      --border: #e2e8f0;
      --border-strong: #cbd5e1;
      --text: #0f172a;
      --muted: #475569;
      --light: #64748b;
      --green: #15803d;
      --green-soft: #dcfce7;
      --red: #dc2626;
      --red-soft: #fee2e2;
      --shadow: 0 2px 6px rgba(14,38,68,0.06), 0 6px 18px rgba(14,38,68,0.05);
      --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ font-family:var(--font); background:var(--bg); color:var(--text); line-height:1.5; }}
    .wrap {{ max-width:1180px; margin:0 auto; padding:18px 16px 64px; }}

    /* Hero with Relampago Logo */
    .hero {{
      background: linear-gradient(135deg, #091a30 0%, #133150 65%, #1a426b 100%);
      color:#fff; border-radius:18px; padding:24px 26px; margin-bottom:16px;
      border-bottom:4px solid var(--gold); box-shadow:0 12px 30px rgba(9,26,48,0.22);
    }}
    .hero-top {{ display:flex; align-items:center; gap:20px; flex-wrap:wrap; margin-bottom:18px; }}
    .logo-wrap {{
      background: rgba(255,255,255,0.95); border-radius:16px; padding:8px 12px;
      border:2px solid var(--gold); box-shadow:0 4px 14px rgba(0,0,0,0.25); flex-shrink:0;
      display:flex; align-items:center; justify-content:center;
    }}
    .logo-wrap img {{ height:72px; width:auto; display:block; }}
    .slogan-pill {{ display:inline-block; background:var(--gold); color:var(--navy); font-size:11px; font-weight:900; letter-spacing:1px; padding:2px 10px; border-radius:999px; margin-bottom:6px; }}
    .hero h1 {{ font-size:clamp(22px,3vw,30px); font-weight:900; line-height:1.15; margin-bottom:4px; }}
    .hero-sub {{ color:#cbd5e1; font-size:13.5px; }}
    .kpi-grid {{ display:grid; grid-template-columns:repeat(5,1fr); gap:10px; }}
    .kpi {{ background:rgba(255,255,255,0.09); border:1px solid rgba(240,215,43,0.28); border-radius:10px; padding:12px 14px; }}
    .kpi-v {{ font-size:22px; font-weight:800; color:#fff; font-variant-numeric:tabular-nums; }}
    .kpi-v.gold {{ color:var(--gold); }}
    .kpi-l {{ font-size:11.5px; color:#cbd5e1; }}

    /* Sticky Dual Filter Bar (Equipo A/B + Torneo) */
    .filter-bar {{
      position:sticky; top:8px; z-index:60; background:rgba(255,255,255,0.97); backdrop-filter:blur(10px);
      border:1px solid var(--border-strong); border-radius:14px; padding:12px 16px; margin-bottom:20px;
      box-shadow:0 6px 20px rgba(14,38,68,0.1); display:flex; flex-direction:column; gap:10px;
    }}
    .filter-row {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
    .f-label {{ font-size:11.5px; font-weight:800; text-transform:uppercase; letter-spacing:0.6px; color:var(--navy); min-width:80px; }}
    .pills {{ display:inline-flex; flex-wrap:wrap; gap:6px; }}
    .pill-btn {{
      border:1px solid var(--border-strong); background:var(--surface-alt); color:var(--muted);
      padding:6px 13px; border-radius:999px; font-size:12.5px; font-weight:700; cursor:pointer; transition:all .15s;
    }}
    .pill-btn:hover {{ border-color:var(--navy); color:var(--navy); background:var(--navy-soft); }}
    .pill-btn.active {{ background:var(--navy); border-color:var(--navy); color:#fff; }}
    .pill-btn.gold-active {{ background:var(--gold); border-color:var(--gold-dark); color:var(--navy); font-weight:900; }}

    .section {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:22px; margin-bottom:20px; box-shadow:var(--shadow); }}
    .sec-head {{ display:flex; justify-content:space-between; align-items:flex-end; flex-wrap:wrap; gap:10px; margin-bottom:16px; }}
    h2 {{ font-size:19px; font-weight:900; color:var(--navy); }}
    .sub {{ font-size:13px; color:var(--light); margin-top:2px; }}

    /* Strategy / Lineup Optimizer */
    .strat-controls {{ display:flex; gap:12px; align-items:center; flex-wrap:wrap; background:var(--navy-soft); border:1px solid #c5d7ee; border-radius:12px; padding:14px; margin-bottom:16px; }}
    .sel {{ padding:8px 12px; border:1px solid var(--border-strong); border-radius:8px; font-size:13.5px; font-weight:700; background:#fff; color:var(--navy); min-width:230px; }}
    .btn {{ border:1px solid var(--border-strong); background:#fff; color:var(--navy); padding:8px 13px; border-radius:8px; font-size:12.5px; font-weight:800; cursor:pointer; }}
    .btn:hover {{ background:var(--navy-soft); border-color:var(--navy); }}
    .btn-gold {{ background:var(--gold); border-color:var(--gold-dark); color:var(--navy); }}
    .btn-gold:hover {{ background:#e5c914; }}
    .btn-green {{ background:var(--green); border-color:var(--green); color:#fff; }}
    .btn-green:hover {{ background:#166534; }}

    .avail-box {{ background:var(--surface-alt); border:1px solid var(--border); border-radius:10px; padding:12px 14px; margin-bottom:16px; }}
    .avail-grid {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }}
    .avail-chip {{ display:inline-flex; align-items:center; gap:5px; padding:5px 10px; border-radius:8px; border:1px solid var(--border-strong); background:#fff; font-size:12px; font-weight:600; cursor:pointer; user-select:none; }}
    .avail-chip.on {{ background:var(--navy); color:#fff; border-color:var(--navy); }}
    .avail-chip .dual {{ font-size:10px; background:var(--gold); color:var(--navy); padding:0 5px; border-radius:4px; font-weight:900; }}

    .three-col {{ display:grid; grid-template-columns:1fr 1.15fr; gap:18px; margin-top:14px; }}
    .subcard {{ background:var(--surface-alt); border:1px solid var(--border); border-radius:12px; padding:16px; }}
    .subcard h3 {{ font-size:15px; font-weight:800; color:var(--navy); margin-bottom:10px; display:flex; justify-content:space-between; align-items:center; }}

    .pitcher-card {{ background:#fff; border:1px solid var(--border); border-left:4px solid var(--navy); border-radius:10px; padding:12px 14px; margin-bottom:10px; }}
    .pitcher-card.best {{ border-left-color:var(--green); background:#f0fdf4; }}
    .pitcher-top {{ display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:4px; }}
    .rival-alert {{ background:var(--gold-soft); border:1px solid #eab308; color:#713f12; border-radius:10px; padding:10px 14px; font-size:13px; margin-bottom:12px; }}

    .lineup-row {{ display:grid; grid-template-columns:30px 1.2fr 92px 1fr; gap:8px; align-items:center; background:#fff; border:1px solid var(--border); border-radius:8px; padding:8px 10px; margin-bottom:6px; font-size:12.5px; }}
    .ord-num {{ width:26px; height:26px; border-radius:7px; background:var(--navy); color:var(--gold); font-weight:900; display:flex; align-items:center; justify-content:center; font-size:12px; }}
    .role-tag {{ font-size:10.5px; font-weight:800; padding:2px 7px; border-radius:999px; background:var(--navy-soft); color:var(--navy); text-align:center; white-space:nowrap; }}
    .role-tag.power {{ background:var(--gold-soft); color:#854d0e; }}
    .role-tag.lead {{ background:var(--green-soft); color:var(--green); }}
    .stat-mono {{ font-family:var(--mono); font-size:11.5px; color:var(--muted); text-align:right; }}

    /* SVG Softball Diamond */
    .diamond-wrap {{ background:linear-gradient(180deg,#166534 0%,#15803d 100%); border-radius:12px; padding:10px; margin-bottom:12px; position:relative; }}
    .diamond-svg {{ width:100%; height:auto; display:block; max-height:310px; }}
    .def-list {{ display:grid; grid-template-columns:repeat(2,1fr); gap:6px; }}
    .def-slot {{ display:flex; align-items:center; gap:6px; background:#fff; border:1px solid var(--border); border-radius:8px; padding:6px 8px; font-size:12px; }}
    .pos-b {{ font-family:var(--mono); font-weight:900; font-size:11px; background:var(--navy); color:var(--gold); padding:2px 6px; border-radius:5px; min-width:30px; text-align:center; }}
    .def-sel {{ flex:1; border:1px solid var(--border); border-radius:6px; padding:4px 6px; font-size:12px; font-family:var(--font); }}

    /* Tables & Cards */
    .tw {{ overflow-x:auto; border:1px solid var(--border); border-radius:10px; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th {{ background:var(--surface-alt); color:var(--muted); font-size:11px; text-transform:uppercase; padding:10px 10px; border-bottom:1px solid var(--border); text-align:left; white-space:nowrap; }}
    td {{ padding:9px 10px; border-bottom:1px solid var(--border); font-variant-numeric:tabular-nums; }}
    tr:last-child td {{ border-bottom:none; }}
    tr.own td {{ background:#fefce8; font-weight:700; }}
    td a {{ color:var(--navy); font-weight:700; text-decoration:none; }}
    td a:hover {{ text-decoration:underline; }}
    .num {{ text-align:right; }}
    .center {{ text-align:center; }}

    .cards-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(270px,1fr)); gap:14px; }}
    .t-card {{ display:block; text-decoration:none; color:inherit; background:#fff; border:1px solid var(--border); border-radius:12px; padding:15px; transition:all .15s; }}
    .t-card:hover {{ transform:translateY(-2px); border-color:var(--navy); box-shadow:0 6px 18px rgba(14,38,68,0.1); }}
    .t-card.own {{ border:2px solid var(--gold-dark); background:#fefce8; }}
    .tc-top {{ display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:6px; }}
    .tc-name {{ font-size:15.5px; font-weight:800; color:var(--navy); }}
    .badge {{ font-size:11px; font-weight:800; padding:2px 8px; border-radius:999px; background:var(--navy-soft); color:var(--navy); }}
    .badge.danger {{ background:var(--red-soft); color:var(--red); }}
    .badge.ok {{ background:var(--green-soft); color:var(--green); }}
    .footer {{ text-align:center; font-size:12px; color:var(--light); margin-top:28px; }}

    @media (max-width:920px) {{
      .kpi-grid {{ grid-template-columns:repeat(2,1fr); }}
      .three-col {{ grid-template-columns:1fr; }}
    }}
    @media (max-width:600px) {{
      .def-list {{ grid-template-columns:1fr; }}
      .lineup-row {{ grid-template-columns:28px 1fr; }}
      .stat-mono {{ text-align:left; }}
    }}
  </style>
</head>
<body>
  <div class="wrap" id="app"></div>
  <script>
    const PORTAL = {data_json};
    (function initSoftbol(data) {{
      const root = document.getElementById("app");
      const esc = (s) => String(s ?? "").replace(/[&<>"']/g, m => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[m]));
      const fmtRate = (v) => v ? (v >= 1 ? v.toFixed(3) : v.toFixed(3).replace(/^0/, "")) : ".000";

      let activeSquad = data.default_squad || "A";
      let activeViewId = data.default_view_id;
      let selectedRivalName = "";
      let unavailableSet = new Set();
      let customDefMap = {{}}; // pos -> playerName override

      function getViewsForSquad(sq) {{
        return data.view_index.filter(v => sq === "ALL" ? true : (v.squad === sq));
      }}

      function recommendPitchers(roster, rival) {{
        const pitchers = roster.filter(p => p.is_pitcher || (p.pitching && p.pitching.ip > 0));
        const focus = rival && rival.profile ? rival.profile.pitcher_focus : "balanced";
        return pitchers.map(p => {{
          const pc = p.pitching;
          const ip = pc.ip || 0;
          // Puntaje táctico (mayor = mejor matchup contra este rival)
          let score = 50;
          if (ip > 0) {{
            const efeScore = Math.max(0, 12 - pc.efe) * 4;
            const whipScore = Math.max(0, 3.0 - pc.whip) * 18;
            const bbScore = Math.max(0, 6 - pc.bb7) * 5;
            const hrScore = Math.max(0, 2 - pc.hr7) * 10;
            const kScore = Math.min(pc.k7, 7) * 2.5;
            const expBonus = Math.min(ip, 25) * 0.4;
            if (focus === "anti_power") score = efeScore * 1.2 + hrScore * 1.5 + whipScore + expBonus;
            else if (focus === "command") score = bbScore * 1.6 + whipScore * 1.3 + efeScore * 0.8 + expBonus;
            else if (focus === "whip_def") score = whipScore * 1.4 + efeScore + kScore + expBonus;
            else score = efeScore + whipScore + bbScore * 0.8 + expBonus;
          }}
          let reason = "Rotación disponible";
          if (ip === 0) reason = "Sin innings oficiales en este torneo (habilitado manualmente).";
          else if (focus === "anti_power") reason = `EFE ${{pc.efe.toFixed(2)}} y ${{pc.hr7.toFixed(1)}} HR/7 — mejor perfil para contener poder.`;
          else if (focus === "command") reason = `Solo ${{pc.bb7.toFixed(1)}} BB/7 y WHIP ${{pc.whip.toFixed(2)}} — ideal ante rival que toma boletos.`;
          else reason = `EFE ${{pc.efe.toFixed(2)}} · WHIP ${{pc.whip.toFixed(2)}} en ${{pc.ip.toFixed(1)}} IP (${{pc.g}}–${{pc.p}}).`;
          return {{ player: p, score, reason }};
        }}).sort((a, b) => b.score - a.score);
      }}

      function buildOffensiveLineup(availPlayers) {{
        // Suavizado bayesiano (3 VB virtuales de liga .330/.380/.420) para no inflar muestras de 1 turno
        const scored = availPlayers.map(p => {{
          const b = p.batting;
          const w = b.vb || 0;
          const adjAvg = (b.h + 1.0) / (w + 3);
          const adjObp = ((b.h + b.bb + (b.gp||0)) + 1.15) / ((b.al || w) + 3);
          const tb = b.h + b.h2 + 2 * b.h3 + 3 * b.hr;
          const adjSlg = (tb + 1.25) / (w + 3);
          const adjOps = adjObp + adjSlg;
          return {{ p, adjAvg, adjObp, adjSlg, adjOps }};
        }});

        const pool = [...scored];
        const takeBest = (fn) => {{
          if (!pool.length) return null;
          pool.sort((a, b) => fn(b) - fn(a));
          return pool.shift();
        }};

        const slots = new Array(Math.min(10, scored.length)).fill(null);
        const roles = [
          {{ lbl: "1° Leadoff", cls: "lead" }},
          {{ lbl: "2° Contacto", cls: "lead" }},
          {{ lbl: "3° Mejor Bate", cls: "power" }},
          {{ lbl: "4° Cleanup", cls: "power" }},
          {{ lbl: "5° Poder", cls: "power" }},
          {{ lbl: "6° Producción", cls: "" }},
          {{ lbl: "7° Contacto", cls: "" }},
          {{ lbl: "8° Soporte", cls: "" }},
          {{ lbl: "9° Puente", cls: "" }},
          {{ lbl: "10° 2do Leadoff", cls: "lead" }},
        ];

        // Asignación sabermétrica óptima
        if (slots.length >= 1) slots[0] = takeBest(x => x.adjObp * 1.4 + (x.p.batting.ca * 0.02));
        if (slots.length >= 4) slots[3] = takeBest(x => x.adjSlg * 1.3 + x.adjOps * 0.5 + x.p.batting.hr * 0.08 + x.p.batting.ci * 0.015);
        if (slots.length >= 3) slots[2] = takeBest(x => x.adjOps * 1.3 + x.adjAvg * 0.4);
        if (slots.length >= 2) slots[1] = takeBest(x => x.adjObp * 0.9 + x.adjAvg * 0.9);
        if (slots.length >= 5) slots[4] = takeBest(x => x.adjSlg + x.adjOps);
        // Si hay 10, guardar buen OBP para el 10mo bate (vuelta al orden)
        if (slots.length === 10) slots[9] = takeBest(x => x.adjObp * 1.2 + x.adjAvg * 0.4);
        for (let i = 0; i < slots.length; i++) {{
          if (!slots[i]) slots[i] = takeBest(x => x.adjOps);
        }}
        // Cualquier jugador extra disponible pasa como Bateador Extra (BE)
        const extras = pool.map((x, idx) => ({{ ...x, order: slots.length + idx + 1, role: {{ lbl: "BE / Banca", cls: "" }} }}));
        return slots.filter(Boolean).map((x, idx) => ({{ ...x, order: idx + 1, role: roles[idx] || {{ lbl: "Bate", cls: "" }} }})).concat(extras);
      }}

      function buildDefensiveAlignment(availPlayers, topPitcherName) {{
        const POS_ORDER = ["P", "SS", "2B", "CF", "SF", "1B", "3B", "C", "LF", "RF"];
        const assigned = {{}};
        const used = new Set();

        // Respetar overrides manuales primero si el jugador sigue disponible
        const availNames = new Set(availPlayers.map(p => p.name));
        for (const pos of POS_ORDER) {{
          if (customDefMap[pos] && availNames.has(customDefMap[pos]) && !used.has(customDefMap[pos])) {{
            assigned[pos] = customDefMap[pos];
            used.add(customDefMap[pos]);
          }}
        }}

        // Asignar P al pitcher recomendado si no fue fijado manualmente
        if (!assigned["P"] && topPitcherName && availNames.has(topPitcherName) && !used.has(topPitcherName)) {{
          assigned["P"] = topPitcherName;
          used.add(topPitcherName);
        }}

        // Puntaje de un jugador en una posición según innings (EJ) y PDF real
        const posScore = (p, pos) => {{
          const hit = (p.positions || []).find(x => x.pos === pos);
          if (hit) return 100 + (hit.ej || 0) * 3 + (hit.pdf || 0.85) * 40 + (hit.jj || 0) * 4;
          // Afinidad de respaldo entre posiciones cercanas
          const prim = p.primary_pos;
          if (["LF","CF","RF","SF"].includes(pos) && ["LF","CF","RF","SF"].includes(prim)) return 35;
          if (["2B","SS","3B"].includes(pos) && ["2B","SS","3B"].includes(prim)) return 30;
          if (pos === "1B" && ["3B","C"].includes(prim)) return 25;
          return 10 + (p.defense.pdf || 0) * 10;
        }};

        for (const pos of POS_ORDER) {{
          if (assigned[pos]) continue;
          const cands = availPlayers.filter(p => !used.has(p.name));
          if (!cands.length) {{ assigned[pos] = "Por definir"; continue; }}
          cands.sort((a, b) => posScore(b, pos) - posScore(a, pos));
          assigned[pos] = cands[0].name;
          used.add(cands[0].name);
        }}
        return {{ order: POS_ORDER, map: assigned }};
      }}

      function renderDiamondSVG(defMap) {{
        const shortName = (n) => {{
          if (!n || n === "Por definir") return "—";
          const parts = n.split(" ");
          return parts.length >= 2 ? `${{parts[0][0]}}. ${{parts[1]}}` : parts[0].slice(0, 10);
        }};
        const coords = {{
          CF: [210, 42], LF: [78, 86], RF: [342, 86], SF: [210, 112],
          SS: [148, 148], "2B": [272, 148], "3B": [112, 206], "1B": [308, 206],
          P: [210, 210], C: [210, 286]
        }};
        const nodes = Object.entries(coords).map(([pos, [x, y]]) => `
          <g transform="translate(${{x}},${{y}})">
            <rect x="-46" y="-15" width="92" height="30" rx="7" fill="#0e2644" stroke="#f0d72b" stroke-width="1.6" />
            <text x="0" y="-2" text-anchor="middle" fill="#f0d72b" font-size="9.5" font-weight="900" font-family="monospace">${{pos}}</text>
            <text x="0" y="10" text-anchor="middle" fill="#ffffff" font-size="10" font-weight="700" font-family="sans-serif">${{esc(shortName(defMap[pos]))}}</text>
          </g>
        `).join("");

        return `
          <svg class="diamond-svg" viewBox="0 0 420 315" xmlns="http://www.w3.org/2000/svg">
            <!-- Outfield arc -->
            <path d="M 20 190 Q 210 -25 400 190 L 210 305 Z" fill="#1e7e45" stroke="rgba(255,255,255,0.35)" stroke-width="2" />
            <!-- Infield dirt -->
            <polygon points="210,128 310,208 210,290 110,208" fill="#c28d57" opacity="0.92" stroke="#f8fafc" stroke-width="2" />
            <!-- Infield grass -->
            <polygon points="210,152 280,208 210,264 140,208" fill="#166534" />
            <!-- Bases -->
            <rect x="205" y="124" width="10" height="10" transform="rotate(45 210 129)" fill="#fff" />
            <rect x="305" y="203" width="10" height="10" transform="rotate(45 310 208)" fill="#fff" />
            <rect x="105" y="203" width="10" height="10" transform="rotate(45 110 208)" fill="#fff" />
            <polygon points="204,284 216,284 216,291 210,296 204,291" fill="#fff" />
            <!-- Pitcher mound -->
            <circle cx="210" cy="210" r="14" fill="#c28d57" stroke="#fff" stroke-width="1" />
            ${{nodes}}
          </svg>
        `;
      }}

      function render() {{
        const squadViews = getViewsForSquad(activeSquad);
        if (!squadViews.some(v => v.id === activeViewId)) {{
          activeViewId = squadViews[0]?.id || data.view_index[0].id;
        }}
        const view = data.views[activeViewId];
        const k = view.our_kpis;
        const roster = view.relampago_roster || [];
        const rivals = view.rivals_profiles || [];
        if (!rivals.some(r => r.name === selectedRivalName)) {{
          selectedRivalName = rivals[0]?.name || "";
        }}
        const curRival = rivals.find(r => r.name === selectedRivalName) || null;
        const availPlayers = roster.filter(p => !unavailableSet.has(p.name));

        const pitcherRecs = recommendPitchers(availPlayers, curRival);
        const topPitcherName = pitcherRecs[0]?.player?.name || "";
        const lineup = buildOffensiveLineup(availPlayers);
        const defense = buildDefensiveAlignment(availPlayers, topPitcherName);
        const qSuffix = `?view=${{encodeURIComponent(activeViewId)}}`;

        root.innerHTML = `
          <header class="hero">
            <div class="hero-top">
              <div class="logo-wrap"><img src="logo_relampago.png" alt="Logo Relámpago del Caribe" /></div>
              <div>
                <div class="slogan-pill">⚡ ${{esc(data.slogan)}} · SCOUTING SOFTBOL UNIMET</div>
                <h1>${{esc(data.brand)}} — Portal Táctico A &amp; B</h1>
                <div class="hero-sub">${{esc(data.league_name)}} · Vista activa: <strong>${{esc(view.label)}}</strong> · Actualizado: ${{esc(data.updated_at)}}</div>
              </div>
            </div>
            <div class="kpi-grid">
              <div class="kpi"><div class="kpi-v gold">${{k.g}}–${{k.p}}${{k.e ? "–" + k.e : ""}}</div><div class="kpi-l">Récord Relámpago</div></div>
              <div class="kpi"><div class="kpi-v">${{k.ca}} / ${{k.cp}}</div><div class="kpi-l">Carreras CA / CP (${{k.df >= 0 ? "+" : ""}}${{k.df}})</div></div>
              <div class="kpi"><div class="kpi-v">${{fmtRate(k.avg)}}</div><div class="kpi-l">AVG Colectivo</div></div>
              <div class="kpi"><div class="kpi-v">${{fmtRate(k.ops)}}</div><div class="kpi-l">OPS Colectivo</div></div>
              <div class="kpi"><div class="kpi-v">${{k.efe.toFixed(2)}}</div><div class="kpi-l">EFE Pitcheo (WHIP ${{k.whip.toFixed(2)}})</div></div>
            </div>
          </header>

          <!-- BARRA DE FILTROS: EQUIPO A / B + TORNEO -->
          <div class="filter-bar">
            <div class="filter-row">
              <span class="f-label">⚡ Equipo:</span>
              <div class="pills" id="squad-pills">
                <button class="pill-btn ${{activeSquad === "A" ? "gold-active" : ""}}" data-sq="A">Equipo A (T89 / T87)</button>
                <button class="pill-btn ${{activeSquad === "B" ? "gold-active" : ""}}" data-sq="B">Equipo B (T90)</button>
                <button class="pill-btn ${{activeSquad === "ALL" ? "gold-active" : ""}}" data-sq="ALL">Todos (A + B)</button>
              </div>
            </div>
            <div class="filter-row">
              <span class="f-label">🏆 Torneo:</span>
              <div class="pills" id="view-pills">
                ${{squadViews.map(v => `<button class="pill-btn ${{v.id === activeViewId ? "active" : ""}}" data-vid="${{esc(v.id)}}">${{esc(v.label)}}</button>`).join("")}}
              </div>
            </div>
          </div>

          <!-- GENERADOR DE ESTRATEGIA DE JUEGO (PITCHER + LINEUP OFENSIVO + DEFENSA) -->
          <section class="section" id="sec-estrategia">
            <div class="sec-head">
              <div>
                <h2>🧠 Estrategia de Juego — Lineup Ofensivo, Defensivo y Pitcher</h2>
                <div class="sub">Selecciona el rival y los jugadores disponibles hoy para generar automáticamente el mejor abridor, orden al bate y cuadro defensivo</div>
              </div>
            </div>

            <div class="strat-controls">
              <label style="font-size:13px;font-weight:800;color:var(--navy)">🆚 Rival a enfrentar:</label>
              <select class="sel" id="rival-select">
                ${{rivals.map(r => `<option value="${{esc(r.name)}}" ${{r.name === selectedRivalName ? "selected" : ""}}>${{esc(r.name)}} (${{r.g}}–${{r.p}} · OPS ${{fmtRate(r.ops)}})</option>`).join("") || `<option value="">Sin rivales cargados</option>`}}
              </select>
              <button class="btn" id="btn-reset-def">🔄 Resetear Defensa</button>
              <button class="btn btn-green" id="btn-copy-wa" style="margin-left:auto">📋 Copiar Lineup para WhatsApp</button>
            </div>

            <div class="avail-box">
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                <strong style="font-size:13px;color:var(--navy)">✅ Jugadores disponibles hoy (${{availPlayers.length}} de ${{roster.length}}) — haz clic para activar/desactivar:</strong>
                <div style="display:flex;gap:6px">
                  <button class="btn" id="btn-all-on" style="padding:4px 9px;font-size:11.5px">Marcar todos</button>
                </div>
              </div>
              <div class="avail-grid" id="avail-grid">
                ${{roster.map(p => {{
                  const on = !unavailableSet.has(p.name);
                  return `<span class="avail-chip ${{on ? "on" : ""}}" data-pname="${{esc(p.name)}}">${{on ? "✓" : "✕"}} ${{esc(p.name)}} <span style="opacity:.75;font-size:11px">(${{esc(p.primary_pos)}})</span>${{p.dual_squad ? ' <span class="dual">A+B</span>' : ""}}</span>`;
                }}).join("") || `<span style="color:var(--light);font-size:12.5px">Todavía no hay jugadores registrados con estadísticas en este torneo (si es T90 recién iniciado, selecciona Equipo A o Histórico para proyectar con tus jugadores compartidos).</span>`}}
              </div>
            </div>

            ${{curRival ? `
              <div class="rival-alert">
                <strong>🔎 Radiografía de ${{esc(curRival.name)}}:</strong>
                <span class="badge danger" style="margin:0 6px">${{esc(curRival.profile.style)}}</span>
                ${{esc(curRival.profile.desc)}}
                ${{curRival.top_batters.length ? `<br><span style="font-size:12px"><strong>Bates a cuidar:</strong> ${{curRival.top_batters.map(b => `${{esc(b.name)}} (${{fmtRate(b.avg)}} / ${{b.hr}} HR)`).join(" · ")}}</span>` : ""}}
              </div>
            ` : ""}}

            <!-- RECOMENDACIÓN DE PITCHER -->
            <div class="subcard" style="margin-bottom:18px">
              <h3>⚾ Recomendación de Pitcheo vs ${{esc(curRival ? curRival.name : "Rival")}}</h3>
              ${{pitcherRecs.length ? pitcherRecs.slice(0, 3).map((rec, idx) => {{
                const pc = rec.player.pitching;
                const label = idx === 0 ? "⭐ Abridor Recomendado" : (idx === 1 ? "🔁 Relevo Principal" : "🛡️ Opción #3");
                return `
                  <div class="pitcher-card ${{idx === 0 ? "best" : ""}}">
                    <div class="pitcher-top">
                      <div><strong>${{esc(rec.player.name)}}</strong> <span class="badge ${{idx === 0 ? "ok" : ""}}">${{label}}</span></div>
                      <div style="font-family:var(--mono);font-size:12.5px;font-weight:800;color:var(--navy)">EFE ${{pc.efe.toFixed(2)}} · WHIP ${{pc.whip.toFixed(2)}} · ${{pc.ip.toFixed(1)}} IP (${{pc.g}}–${{pc.p}})</div>
                    </div>
                    <div style="font-size:12.5px;color:var(--muted)">${{esc(rec.reason)}} · K: ${{pc.k}} · BB: ${{pc.bb}} · HR permitidos: ${{pc.hr}}</div>
                  </div>
                `;
              }}).join("") : `<p style="font-size:13px;color:var(--light)">No hay pitchers con innings registrados entre los jugadores disponibles de esta vista.</p>`}}
            </div>

            <!-- LINEUP OFENSIVO + DEFENSIVO LADO A LADO -->
            <div class="three-col">
              <div class="subcard">
                <h3>🏏 Lineup Ofensivo Sugerido (1° al 10°) <span style="font-size:11.5px;color:var(--light);font-weight:600">Basado en OBP / SLG / OPS</span></h3>
                ${{lineup.map(slot => {{
                  const b = slot.p.batting;
                  return `
                    <div class="lineup-row">
                      <div class="ord-num">${{slot.order}}</div>
                      <div><strong>${{esc(slot.p.name)}}</strong> <span style="font-size:11px;color:var(--light)">(${{esc(slot.p.primary_pos)}})</span></div>
                      <span class="role-tag ${{slot.role.cls}}">${{esc(slot.role.lbl)}}</span>
                      <div class="stat-mono">AVG ${{fmtRate(b.avg)}} · OBP ${{fmtRate(b.obp)}} · OPS ${{fmtRate(b.ops)}}</div>
                    </div>
                  `;
                }}).join("") || `<p style="font-size:13px;color:var(--light)">Activa jugadores disponibles arriba para generar el orden al bate.</p>`}}
              </div>

              <div class="subcard">
                <h3>🧤 Alineación Defensiva Sugerida (Campo) <span style="font-size:11.5px;color:var(--light);font-weight:600">Editable</span></h3>
                <div class="diamond-wrap">${{renderDiamondSVG(defense.map)}}</div>
                <div class="def-list">
                  ${{defense.order.map(pos => `
                    <div class="def-slot">
                      <span class="pos-b">${{pos}}</span>
                      <select class="def-sel" data-def-pos="${{pos}}">
                        <option value="Por definir">— Por definir —</option>
                        ${{availPlayers.map(p => {{
                          const hit = (p.positions || []).find(x => x.pos === pos);
                          const extra = hit ? ` (${{hit.ej}} EJ · PDF ${{fmtRate(hit.pdf)}})` : ` (${{p.primary_pos}})`;
                          return `<option value="${{esc(p.name)}}" ${{defense.map[pos] === p.name ? "selected" : ""}}>${{esc(p.name)}}${{extra}}</option>`;
                        }}).join("")}}
                      </select>
                    </div>
                  `).join("")}}
                </div>
              </div>
            </div>
          </section>

          <!-- TABLAS DE POSICIONES -->
          ${{view.standings_blocks.length ? `
            <section class="section" id="sec-tablas">
              <div class="sec-head"><div><h2>📊 Tabla de Posiciones — ${{esc(view.label)}}</h2><div class="sub">Haz clic en cualquier rival para abrir su reporte completo de bateo, pitcheo y defensa</div></div></div>
              ${{view.standings_blocks.map(blk => `
                <h3 style="font-size:14.5px;color:var(--navy);margin:12px 0 8px">${{esc(blk.phase)}}</h3>
                <div class="tw" style="margin-bottom:14px">
                  <table>
                    <thead><tr><th class="center">Pos</th><th>Equipo</th><th class="num">J</th><th class="num">G</th><th class="num">P</th><th class="num">E</th><th class="num">CA</th><th class="num">CP</th><th class="num">DF</th><th class="num">AVG</th><th class="num">Pts</th></tr></thead>
                    <tbody>
                      ${{blk.rows.map(r => {{
                        const isOurs = r.team.toLowerCase().includes("relampago") || r.team.toLowerCase().includes("relámpago");
                        return `<tr class="${{isOurs ? "own" : ""}}"><td class="center">${{r.pos}}</td><td><a href="equipos/${{r.slug}}.html${{qSuffix}}">${{esc(r.team)}}</a>${{isOurs ? ' <span class="badge" style="background:var(--gold);color:var(--navy)">Nosotros</span>' : ""}}</td><td class="num">${{r.j}}</td><td class="num"><strong>${{r.g}}</strong></td><td class="num">${{r.p}}</td><td class="num">${{r.e}}</td><td class="num">${{r.ca}}</td><td class="num">${{r.cp}}</td><td class="num">${{r.df >= 0 ? "+" : ""}}${{r.df}}</td><td class="num">${{fmtRate(r.avg)}}</td><td class="num"><strong>${{r.pts}}</strong></td></tr>`;
                      }}).join("")}}
                    </tbody>
                  </table>
                </div>
              `).join("")}}
            </section>
          ` : ""}}

          <!-- SCOUTING DE EQUIPOS -->
          <section class="section" id="sec-rivales">
            <div class="sec-head"><div><h2>🎯 Scouting de Equipos — ${{esc(view.label)}}</h2><div class="sub">Abre cualquier equipo para ver sus bates más peligrosos, estadísticas de pitcheo y errores defensivos</div></div></div>
            <div class="cards-grid">
              ${{view.teams.map(t => `
                <a class="t-card ${{t.is_ours ? "own" : ""}}" href="equipos/${{t.slug}}.html${{qSuffix}}">
                  <div class="tc-top">
                    <div class="tc-name">${{esc(t.name)}}</div>
                    <span class="badge ${{t.is_ours ? "" : (t.team_bat.ops >= 0.900 ? "danger" : "ok")}}">${{t.g}}–${{t.p}}${{t.e ? "–" + t.e : ""}}</span>
                  </div>
                  <div style="font-size:12px;color:var(--muted);margin-bottom:6px">
                    ${{t.is_ours ? "⚡ Nuestro equipo" : `Perfil: <strong>${{esc(t.profile.style)}}</strong>`}}
                  </div>
                  <div style="font-size:12px;color:var(--light);display:flex;justify-content:space-between">
                    <span>AVG <strong>${{fmtRate(t.team_bat.avg)}}</strong> · OPS <strong>${{fmtRate(t.team_bat.ops)}}</strong></span>
                    <span>EFE <strong>${{t.team_pic.efe.toFixed(2)}}</strong></span>
                  </div>
                </a>
              `).join("")}}
            </div>
          </section>

          <footer class="footer">⚡ ${{esc(data.brand)}} — ${{esc(data.slogan)}} · Fuente automática: BeisbolySoftbol.com (UNIMET)</footer>
        `;

        // Event listeners
        document.querySelectorAll("#squad-pills .pill-btn").forEach(b => b.addEventListener("click", () => {{
          activeSquad = b.dataset.sq;
          const vs = getViewsForSquad(activeSquad);
          activeViewId = vs[0]?.id || activeViewId;
          customDefMap = {{}};
          render();
        }}));
        document.querySelectorAll("#view-pills .pill-btn").forEach(b => b.addEventListener("click", () => {{
          activeViewId = b.dataset.vid;
          customDefMap = {{}};
          render();
        }}));
        document.getElementById("rival-select").addEventListener("change", (e) => {{
          selectedRivalName = e.target.value;
          render();
        }});
        document.querySelectorAll("#avail-grid .avail-chip").forEach(ch => ch.addEventListener("click", () => {{
          const pn = ch.dataset.pname;
          if (unavailableSet.has(pn)) unavailableSet.delete(pn); else unavailableSet.add(pn);
          render();
        }}));
        document.getElementById("btn-all-on").addEventListener("click", () => {{ unavailableSet.clear(); render(); }});
        document.getElementById("btn-reset-def").addEventListener("click", () => {{ customDefMap = {{}}; render(); }});
        document.querySelectorAll("[data-def-pos]").forEach(sel => sel.addEventListener("change", (e) => {{
          customDefMap[e.target.dataset.defPos] = e.target.value;
          render();
        }}));
        document.getElementById("btn-copy-wa").addEventListener("click", () => {{
          const lines = [
            `⚡ *RELÁMPAGO DEL CARIBE (${{view.label}})* — ¡CACHAM!`,
            `🆚 *Rival:* ${{curRival ? curRival.name : "Por definir"}}`,
            `⚾ *Pitcher sugerido:* ${{topPitcherName || "Por definir"}}`,
            "",
            "*🏏 LINEUP OFENSIVO:*",
            ...lineup.slice(0, 10).map(s => `${{s.order}}. ${{s.p.name}} (${{s.role.lbl}} · AVG ${{fmtRate(s.p.batting.avg)}})`) ,
            "",
            "*🧤 DEFENSA:*",
            ...defense.order.map(pos => `• *${{pos}}:* ${{defense.map[pos]}}`),
          ];
          navigator.clipboard?.writeText(lines.join("\\n"));
          const btn = document.getElementById("btn-copy-wa");
          const prev = btn.textContent;
          btn.textContent = "✅ ¡Copiado para WhatsApp!";
          setTimeout(() => btn.textContent = prev, 1800);
        }});
      }}
      render();
    }})(PORTAL);
  </script>
</body>
</html>"""


def render_team_report(team_payload: Dict[str, Any]) -> str:
    data_json = json.dumps(team_payload, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{team_payload['team_name']} — Scouting Softbol Relámpago</title>
  <style>
    :root {{
      --navy:#0e2644; --navy-soft:#e6eef7; --gold:#f0d72b; --gold-soft:#fef9c3;
      --bg:#f3f5f8; --surface:#fff; --alt:#f8fafc; --border:#e2e8f0;
      --text:#0f172a; --muted:#475569; --light:#64748b;
      --green:#15803d; --gsoft:#dcfce7; --red:#dc2626; --rsoft:#fee2e2;
      --font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
      --mono:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ font-family:var(--font); background:var(--bg); color:var(--text); line-height:1.5; }}
    .wrap {{ max-width:1140px; margin:0 auto; padding:16px 16px 60px; }}
    .top {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:8px; }}
    .back {{ text-decoration:none; color:var(--navy); font-weight:800; font-size:13px; background:#fff; border:1px solid var(--border); padding:6px 12px; border-radius:8px; }}
    .back:hover {{ background:var(--navy-soft); }}
    .hero {{ background:linear-gradient(135deg,#091a30,#133150); color:#fff; border-radius:16px; padding:24px; margin-bottom:18px; border-bottom:4px solid var(--gold); }}
    .hero-top {{ display:flex; align-items:center; gap:16px; flex-wrap:wrap; margin-bottom:16px; }}
    .mini-logo {{ background:#fff; border-radius:12px; padding:5px 8px; border:2px solid var(--gold); }}
    .mini-logo img {{ height:52px; display:block; }}
    .hero h1 {{ font-size:clamp(22px,3vw,28px); font-weight:900; }}
    .hero-sub {{ color:#cbd5e1; font-size:13px; }}
    .kpis {{ display:grid; grid-template-columns:repeat(5,1fr); gap:10px; }}
    .kpi {{ background:rgba(255,255,255,0.09); border:1px solid rgba(240,215,43,0.28); border-radius:10px; padding:11px 13px; }}
    .kpi-v {{ font-size:21px; font-weight:800; font-variant-numeric:tabular-nums; }}
    .kpi-l {{ font-size:11.5px; color:#cbd5e1; }}
    .sec {{ background:#fff; border:1px solid var(--border); border-radius:12px; padding:20px; margin-bottom:18px; }}
    h2 {{ font-size:18px; font-weight:900; color:var(--navy); margin-bottom:6px; }}
    .sub {{ font-size:12.5px; color:var(--light); margin-bottom:14px; }}
    .pills {{ display:flex; gap:6px; flex-wrap:wrap; margin-bottom:16px; }}
    .pbtn {{ border:1px solid #cbd5e1; background:#f8fafc; color:var(--muted); padding:6px 12px; border-radius:999px; font-size:12px; font-weight:700; cursor:pointer; }}
    .pbtn.active {{ background:var(--navy); color:#fff; border-color:var(--navy); }}
    .ins-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
    .ins {{ background:var(--alt); border:1px solid var(--border); border-top:3px solid var(--navy); border-radius:10px; padding:12px 14px; }}
    .ins.danger {{ border-top-color:var(--red); }}
    .ins.gold {{ border-top-color:#eab308; }}
    .ins-k {{ font-size:10.5px; font-weight:800; text-transform:uppercase; color:var(--light); }}
    .ins-h {{ font-size:14px; font-weight:800; margin:3px 0; }}
    .ins-b {{ font-size:12.5px; color:var(--muted); }}
    .tw {{ overflow-x:auto; border:1px solid var(--border); border-radius:10px; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th {{ background:var(--alt); color:var(--muted); font-size:11px; text-transform:uppercase; padding:9px 10px; border-bottom:1px solid var(--border); text-align:left; white-space:nowrap; }}
    td {{ padding:9px 10px; border-bottom:1px solid var(--border); font-variant-numeric:tabular-nums; }}
    tr:last-child td {{ border-bottom:none; }}
    .num {{ text-align:right; }}
    .tag {{ display:inline-block; font-size:10.5px; font-weight:800; padding:2px 7px; border-radius:999px; }}
    .tag-r {{ background:var(--rsoft); color:var(--red); }}
    .tag-g {{ background:var(--gsoft); color:var(--green); }}
    .tag-y {{ background:var(--gold-soft); color:#854d0e; }}
    .res-b {{ display:inline-flex; width:22px; height:22px; border-radius:5px; align-items:center; justify-content:center; font-size:11px; font-weight:900; }}
    .res-b.G {{ background:var(--gsoft); color:var(--green); }}
    .res-b.P {{ background:var(--rsoft); color:var(--red); }}
    .res-b.E {{ background:var(--gold-soft); color:#854d0e; }}
    @media (max-width:850px) {{ .kpis {{ grid-template-columns:repeat(2,1fr); }} .ins-grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap" id="team-app"></div>
  <script>
    const TDATA = {data_json};
    (function initTeam(data) {{
      const root = document.getElementById("team-app");
      const esc = (s) => String(s ?? "").replace(/[&<>"']/g, m => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[m]));
      const fmtRate = (v) => v ? (v >= 1 ? v.toFixed(3) : v.toFixed(3).replace(/^0/, "")) : ".000";
      const keys = Object.keys(data.by_view);
      const urlV = new URLSearchParams(window.location.search).get("view");
      let activeV = (urlV && data.by_view[urlV]) ? urlV : keys[0];

      function render() {{
        const v = data.by_view[activeV];
        const tb = v.team_bat, tp = v.team_pic, td = v.team_def;
        const bestBat = v.batting[0];
        const bestPic = v.pitching[0];
        const mostErr = [...v.defense].sort((a,b) => b.e - a.e)[0];

        root.innerHTML = `
          <div class="top">
            <a class="back" href="../index.html">← Volver al Portal Relámpago &amp; Lineup</a>
            <span style="font-size:12.5px;color:var(--light)">Actualizado: ${{esc(data.updated_at)}}</span>
          </div>

          <header class="hero">
            <div class="hero-top">
              <div class="mini-logo"><img src="../logo_relampago.png" alt="Relámpago" /></div>
              <div>
                <div style="font-size:11px;color:var(--gold);font-weight:800;text-transform:uppercase">SCOUTING RELÁMPAGO · ${{esc(v.view_label)}}</div>
                <h1>${{esc(data.team_name)}}</h1>
                <div class="hero-sub">Perfil ofensivo: <strong>${{esc(v.profile.style)}}</strong> · ${{v.batting.length}} bateadores · ${{v.pitching.length}} pitchers</div>
              </div>
            </div>
            <div class="kpis">
              <div class="kpi"><div class="kpi-v" style="color:var(--gold)">${{v.g}}–${{v.p}}${{v.e ? "–" + v.e : ""}}</div><div class="kpi-l">Récord (Pts: ${{v.pts}})</div></div>
              <div class="kpi"><div class="kpi-v">${{v.ca_pg.toFixed(1)}} / ${{v.cp_pg.toFixed(1)}}</div><div class="kpi-l">CA / CP por juego</div></div>
              <div class="kpi"><div class="kpi-v">${{fmtRate(tb.avg)}}</div><div class="kpi-l">AVG · OBP ${{fmtRate(tb.obp)}}</div></div>
              <div class="kpi"><div class="kpi-v">${{fmtRate(tb.ops)}}</div><div class="kpi-l">OPS · ${{tb.hr}} HR</div></div>
              <div class="kpi"><div class="kpi-v">${{tp.efe.toFixed(2)}}</div><div class="kpi-l">EFE Pitcheo · PDF ${{fmtRate(td.pdf)}}</div></div>
            </div>
          </header>

          ${{keys.length > 1 ? `
            <div class="pills" id="vpills">
              ${{keys.map(k => `<button class="pbtn ${{k===activeV?"active":""}}" data-vk="${{esc(k)}}">${{esc(data.by_view[k].view_label)}}</button>`).join("")}}
            </div>
          ` : ""}}

          <section class="sec">
            <h2>⚡ Lo esencial en 30 segundos</h2>
            <div class="ins-grid">
              <div class="ins gold">
                <div class="ins-k">Perfil ofensivo</div>
                <div class="ins-h">${{esc(v.profile.style)}}</div>
                <div class="ins-b">${{esc(v.profile.desc)}}</div>
              </div>
              <div class="ins danger">
                <div class="ins-k">Bate #1 a cuidar</div>
                <div class="ins-h">${{bestBat ? esc(bestBat.name) : "Sin datos"}}</div>
                <div class="ins-b">${{bestBat ? `AVG ${{fmtRate(bestBat.avg)}} · OPS ${{fmtRate(bestBat.ops)}} · ${{bestBat.hr}} HR · ${{bestBat.ci}} CI en ${{bestBat.vb}} VB.` : "Sin turnos registrados."}}</div>
              </div>
              <div class="ins">
                <div class="ins-k">Pitcheo y Defensa</div>
                <div class="ins-h">${{bestPic ? `Abridor: ${{esc(bestPic.name)}}` : "Sin pitchers"}}</div>
                <div class="ins-b">${{bestPic ? `EFE ${{bestPic.efe.toFixed(2)}} · WHIP ${{bestPic.whip.toFixed(2)}} (${{bestPic.ip}} IP).` : ""}} ${{mostErr && mostErr.e > 0 ? `Defensa: ${{td.e}} errores (${{esc(mostErr.name)}} acumula ${{mostErr.e}} E).` : `PDF colectivo: ${{fmtRate(td.pdf)}}.`}}</div>
              </div>
            </div>
          </section>

          <section class="sec">
            <h2>🏏 Estadísticas de Bateo (${{v.batting.length}} jugadores)</h2>
            <div class="sub">Ordenados por OPS. Los bates con OPS ≥ 1.000 aparecen marcados como Peligro.</div>
            <div class="tw">
              <table>
                <thead><tr><th>Jugador</th><th class="num">JJ</th><th class="num">VB</th><th class="num">H</th><th class="num">2B</th><th class="num">3B</th><th class="num">HR</th><th class="num">CI</th><th class="num">CA</th><th class="num">BB</th><th class="num">K</th><th class="num">AVG</th><th class="num">OBP</th><th class="num">SLG</th><th class="num">OPS</th></tr></thead>
                <tbody>
                  ${{v.batting.map(b => `
                    <tr>
                      <td><strong>${{esc(b.name)}}</strong>${{b.ops >= 1.000 && b.vb >= 5 ? ' <span class="tag tag-r">Peligro</span>' : ""}}</td>
                      <td class="num">${{b.jj}}</td><td class="num">${{b.vb}}</td><td class="num">${{b.h}}</td>
                      <td class="num">${{b.h2}}</td><td class="num">${{b.h3}}</td><td class="num"><strong>${{b.hr}}</strong></td>
                      <td class="num">${{b.ci}}</td><td class="num">${{b.ca}}</td><td class="num">${{b.bb}}</td><td class="num">${{b.k}}</td>
                      <td class="num"><strong>${{fmtRate(b.avg)}}</strong></td><td class="num">${{fmtRate(b.obp)}}</td>
                      <td class="num">${{fmtRate(b.slg)}}</td><td class="num"><strong>${{fmtRate(b.ops)}}</strong></td>
                    </tr>
                  `).join("") || `<tr><td colspan="15" style="text-align:center;color:var(--light)">Sin estadísticas de bateo registradas aún.</td></tr>`}}
                </tbody>
              </table>
            </div>
          </section>

          <section class="sec">
            <h2>⚾ Pitcheo (${{v.pitching.length}}) &amp; 🧤 Defensiva (${{v.defense.length}})</h2>
            <div class="tw" style="margin-bottom:16px">
              <table>
                <thead><tr><th>Pitcher</th><th class="num">JJ</th><th class="num">G–P</th><th class="num">IP</th><th class="num">H</th><th class="num">CL</th><th class="num">BB</th><th class="num">K</th><th class="num">HR</th><th class="num">EFE</th><th class="num">WHIP</th></tr></thead>
                <tbody>
                  ${{v.pitching.map(p => `
                    <tr>
                      <td><strong>${{esc(p.name)}}</strong></td>
                      <td class="num">${{p.jj}}</td><td class="num">${{p.g}}–${{p.p}}</td><td class="num">${{p.ip.toFixed(1)}}</td>
                      <td class="num">${{p.h}}</td><td class="num">${{p.cl}}</td><td class="num">${{p.bb}}</td><td class="num">${{p.k}}</td>
                      <td class="num">${{p.hr}}</td><td class="num"><strong>${{p.efe.toFixed(2)}}</strong></td><td class="num"><strong>${{p.whip.toFixed(2)}}</strong></td>
                    </tr>
                  `).join("") || `<tr><td colspan="11" style="text-align:center;color:var(--light)">Sin pitcheo registrado aún.</td></tr>`}}
                </tbody>
              </table>
            </div>
            <div class="tw">
              <table>
                <thead><tr><th>Defensor</th><th class="num">JJ</th><th class="num">EJ</th><th class="num">PO</th><th class="num">AS</th><th class="num">E</th><th class="num">DP</th><th class="num">PDF</th></tr></thead>
                <tbody>
                  ${{v.defense.map(d => `
                    <tr>
                      <td><strong>${{esc(d.name)}}</strong>${{d.e >= 3 ? ' <span class="tag tag-y">Atacar</span>' : ""}}</td>
                      <td class="num">${{d.jj}}</td><td class="num">${{d.ej.toFixed(1)}}</td><td class="num">${{d.po}}</td>
                      <td class="num">${{d.as}}</td><td class="num" style="color:${{d.e>=2?'var(--red)':'inherit'}}"><strong>${{d.e}}</strong></td>
                      <td class="num">${{d.dp}}</td><td class="num"><strong>${{fmtRate(d.pdf)}}</strong></td>
                    </tr>
                  `).join("") || `<tr><td colspan="8" style="text-align:center;color:var(--light)">Sin defensiva registrada aún.</td></tr>`}}
                </tbody>
              </table>
            </div>
          </section>

          <section class="sec">
            <h2>📅 Historial de Juegos (${{v.games.length}})</h2>
            <div class="tw">
              <table>
                <thead><tr><th>Res</th><th>Fecha</th><th>Torneo</th><th>Condición</th><th>Rival</th><th class="num">Marcador</th></tr></thead>
                <tbody>
                  ${{v.games.map(g => `
                    <tr>
                      <td><span class="res-b ${{g.result}}">${{g.result}}</span></td>
                      <td>${{esc(g.date)}}</td><td>${{esc(g.tournament)}}</td><td>${{esc(g.venue)}}</td>
                      <td><strong>${{esc(g.opponent)}}</strong></td>
                      <td class="num"><strong>${{g.score_for}} – ${{g.score_against}}</strong></td>
                    </tr>
                  `).join("") || `<tr><td colspan="6" style="text-align:center;color:var(--light)">Sin juegos registrados en esta vista.</td></tr>`}}
                </tbody>
              </table>
            </div>
          </section>
        `;

        document.querySelectorAll("#vpills .pbtn").forEach(b => b.addEventListener("click", () => {{
          activeV = b.dataset.vk;
          render();
        }}));
      }}
      render();
    }})(TDATA);
  </script>
</body>
</html>"""


def build_demo_snapshot() -> Dict[str, Any]:
    """Datos demo realistas basados en Torneo 89 (Equipo A) y Torneo 90 (Equipo B) de UNIMET."""
    return {
        "extracted_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "league_id": 174,
        "league_name": "Liga de Softbol VENEZUELA-UNIMET",
        "tournaments": [
            {
                "cam_id": "3110", "number": 90, "name": "Torneo 90 Lanz Lento", "squad": "B",
                "standings_blocks": [{"phase": "Eliminatoria", "rows": [
                    {"pos": 1, "equ_id": "201", "team": "Relampago del Caribe", "j": 0, "g": 0, "p": 0, "e": 0, "ca": 0, "cp": 0, "df": 0, "avg": 0.0, "pts": 0},
                    {"pos": 2, "equ_id": "202", "team": "Indios Terepaima", "j": 0, "g": 0, "p": 0, "e": 0, "ca": 0, "cp": 0, "df": 0, "avg": 0.0, "pts": 0},
                    {"pos": 3, "equ_id": "203", "team": "Tapiceria Felix Garcia", "j": 0, "g": 0, "p": 0, "e": 0, "ca": 0, "cp": 0, "df": 0, "avg": 0.0, "pts": 0},
                ]}],
                "games": [],
                "teams": {
                    "Relampago del Caribe": {"equ_id": "201", "name": "Relampago del Caribe", "is_ours": True, "batting": [
                        {"jug_id": "374108", "name": "Leonardo Machin", "jj": 0, "vb": 0, "al": 0, "ca": 0, "h": 0, "h2": 0, "h3": 0, "hr": 0, "ci": 0, "bb": 0, "k": 0, "br": 0, "sf": 0, "gp": 0, "avg": 0.0, "obp": 0.0, "slg": 0.0, "ops": 0.0}
                    ], "pitching": [], "defense": []},
                    "Indios Terepaima": {"equ_id": "202", "name": "Indios Terepaima", "is_ours": False, "batting": [], "pitching": [], "defense": []},
                },
                "relampago_player_details": {},
            },
            {
                "cam_id": "3095", "number": 89, "name": "Torneo 89 Lanz Lento", "squad": "A",
                "standings_blocks": [{"phase": "Eliminatoria", "rows": [
                    {"pos": 1, "equ_id": "101", "team": "Mets de Polar", "j": 5, "g": 5, "p": 0, "e": 0, "ca": 42, "cp": 5, "df": 37, "avg": 1.0, "pts": 15},
                    {"pos": 2, "equ_id": "102", "team": "Relampago del Caribe", "j": 7, "g": 4, "p": 2, "e": 1, "ca": 29, "cp": 24, "df": 5, "avg": 0.571, "pts": 13},
                    {"pos": 3, "equ_id": "103", "team": "Orientales 2.0", "j": 8, "g": 4, "p": 4, "e": 0, "ca": 36, "cp": 44, "df": -8, "avg": 0.500, "pts": 12},
                ]}],
                "games": [
                    {"jue_id": "901", "nj": "12", "date": "15-11-2026", "visitor": "Relampago del Caribe", "visitor_score": 8, "local": "Orientales 2.0", "local_score": 5},
                ],
                "teams": {
                    "Relampago del Caribe": {
                        "equ_id": "102", "name": "Relampago del Caribe", "is_ours": True,
                        "batting": [
                            {"jug_id": "374108", "name": "Leonardo Machin", "jj": 6, "vb": 16, "al": 18, "ca": 5, "h": 9, "h2": 2, "h3": 0, "hr": 0, "ci": 4, "bb": 2, "k": 0, "br": 1, "sf": 0, "gp": 0, "avg": 0.563, "obp": 0.611, "slg": 0.688, "ops": 1.299},
                            {"jug_id": "2", "name": "Carlos Perez", "jj": 7, "vb": 20, "al": 22, "ca": 7, "h": 11, "h2": 3, "h3": 1, "hr": 2, "ci": 9, "bb": 2, "k": 1, "br": 0, "sf": 0, "gp": 0, "avg": 0.550, "obp": 0.591, "slg": 1.100, "ops": 1.691},
                            {"jug_id": "3", "name": "Jose Ramirez", "jj": 7, "vb": 18, "al": 21, "ca": 6, "h": 8, "h2": 1, "h3": 0, "hr": 0, "ci": 3, "bb": 3, "k": 0, "br": 2, "sf": 0, "gp": 0, "avg": 0.444, "obp": 0.524, "slg": 0.500, "ops": 1.024},
                            {"jug_id": "4", "name": "Luis Gomez", "jj": 6, "vb": 15, "al": 16, "ca": 3, "h": 6, "h2": 2, "h3": 0, "hr": 1, "ci": 6, "bb": 1, "k": 2, "br": 0, "sf": 0, "gp": 0, "avg": 0.400, "obp": 0.438, "slg": 0.733, "ops": 1.171},
                            {"jug_id": "5", "name": "Andres Silva", "jj": 7, "vb": 17, "al": 19, "ca": 4, "h": 6, "h2": 0, "h3": 0, "hr": 0, "ci": 2, "bb": 2, "k": 1, "br": 0, "sf": 0, "gp": 0, "avg": 0.353, "obp": 0.421, "slg": 0.353, "ops": 0.774},
                            {"jug_id": "6", "name": "Pedro Rojas", "jj": 6, "vb": 14, "al": 15, "ca": 2, "h": 5, "h2": 1, "h3": 0, "hr": 0, "ci": 2, "bb": 1, "k": 1, "br": 0, "sf": 0, "gp": 0, "avg": 0.357, "obp": 0.400, "slg": 0.429, "ops": 0.829},
                            {"jug_id": "7", "name": "Diego Castro", "jj": 6, "vb": 14, "al": 16, "ca": 3, "h": 4, "h2": 0, "h3": 0, "hr": 0, "ci": 1, "bb": 2, "k": 2, "br": 0, "sf": 0, "gp": 0, "avg": 0.286, "obp": 0.375, "slg": 0.286, "ops": 0.661},
                            {"jug_id": "8", "name": "Rafael Mendez", "jj": 5, "vb": 12, "al": 13, "ca": 2, "h": 4, "h2": 1, "h3": 0, "hr": 0, "ci": 2, "bb": 1, "k": 1, "br": 0, "sf": 0, "gp": 0, "avg": 0.333, "obp": 0.385, "slg": 0.417, "ops": 0.802},
                            {"jug_id": "9", "name": "Miguel Torres", "jj": 6, "vb": 13, "al": 15, "ca": 3, "h": 4, "h2": 0, "h3": 0, "hr": 0, "ci": 1, "bb": 2, "k": 0, "br": 0, "sf": 0, "gp": 0, "avg": 0.308, "obp": 0.400, "slg": 0.308, "ops": 0.708},
                            {"jug_id": "10", "name": "Victor Diaz", "jj": 6, "vb": 12, "al": 13, "ca": 1, "h": 3, "h2": 0, "h3": 0, "hr": 0, "ci": 1, "bb": 1, "k": 2, "br": 0, "sf": 0, "gp": 0, "avg": 0.250, "obp": 0.308, "slg": 0.250, "ops": 0.558},
                        ],
                        "pitching": [
                            {"jug_id": "5", "name": "Andres Silva", "jj": 5, "ji": 4, "g": 3, "p": 1, "s": 0, "ip": 24.0, "ip_real": 24.0, "h": 26, "ca": 14, "cl": 11, "bb": 5, "k": 9, "hr": 1, "efe": 3.21, "whip": 1.29},
                            {"jug_id": "9", "name": "Miguel Torres", "jj": 3, "ji": 2, "g": 1, "p": 1, "s": 1, "ip": 12.0, "ip_real": 12.0, "h": 16, "ca": 10, "cl": 8, "bb": 4, "k": 4, "hr": 2, "efe": 4.67, "whip": 1.67},
                        ],
                        "defense": [
                            {"jug_id": "374108", "name": "Leonardo Machin", "jj": 6, "po": 5, "as": 12, "e": 1, "dp": 2, "ej": 36.0, "pdf": 0.944},
                        ],
                    },
                    "Mets de Polar": {
                        "equ_id": "101", "name": "Mets de Polar", "is_ours": False,
                        "batting": [
                            {"jug_id": "501", "name": "Hector Power", "jj": 5, "vb": 16, "al": 18, "ca": 9, "h": 10, "h2": 2, "h3": 0, "hr": 4, "ci": 12, "bb": 2, "k": 0, "br": 0, "sf": 0, "gp": 0, "avg": 0.625, "obp": 0.667, "slg": 1.500, "ops": 2.167},
                        ],
                        "pitching": [
                            {"jug_id": "502", "name": "Juan Ace", "jj": 5, "ji": 5, "g": 5, "p": 0, "s": 0, "ip": 28.0, "ip_real": 28.0, "h": 18, "ca": 5, "cl": 4, "bb": 3, "k": 14, "hr": 0, "efe": 1.00, "whip": 0.75},
                        ],
                        "defense": [
                            {"jug_id": "501", "name": "Hector Power", "jj": 5, "po": 12, "as": 2, "e": 0, "dp": 1, "ej": 28.0, "pdf": 1.000},
                        ],
                    },
                    "Orientales 2.0": {"equ_id": "103", "name": "Orientales 2.0", "is_ours": False, "batting": [], "pitching": [], "defense": []},
                },
                "relampago_player_details": {
                    "374108": {"jug_id": "374108", "name": "Leonardo Machin", "positions": [{"pos": "2B", "jj": 6, "po": 5, "as": 12, "e": 1, "dp": 2, "ej": 36.0, "pdf": 0.944}]},
                    "2": {"jug_id": "2", "name": "Carlos Perez", "positions": [{"pos": "1B", "jj": 7, "po": 32, "as": 1, "e": 1, "dp": 3, "ej": 42.0, "pdf": 0.971}]},
                    "3": {"jug_id": "3", "name": "Jose Ramirez", "positions": [{"pos": "SS", "jj": 7, "po": 8, "as": 18, "e": 2, "dp": 3, "ej": 42.0, "pdf": 0.929}]},
                    "4": {"jug_id": "4", "name": "Luis Gomez", "positions": [{"pos": "CF", "jj": 6, "po": 14, "as": 1, "e": 0, "dp": 0, "ej": 36.0, "pdf": 1.000}]},
                    "5": {"jug_id": "5", "name": "Andres Silva", "positions": [{"pos": "P", "jj": 5, "po": 2, "as": 9, "e": 0, "dp": 1, "ej": 24.0, "pdf": 1.000}]},
                    "6": {"jug_id": "6", "name": "Pedro Rojas", "positions": [{"pos": "3B", "jj": 6, "po": 4, "as": 11, "e": 2, "dp": 1, "ej": 36.0, "pdf": 0.882}]},
                    "7": {"jug_id": "7", "name": "Diego Castro", "positions": [{"pos": "C", "jj": 6, "po": 10, "as": 2, "e": 0, "dp": 0, "ej": 36.0, "pdf": 1.000}]},
                    "8": {"jug_id": "8", "name": "Rafael Mendez", "positions": [{"pos": "SF", "jj": 5, "po": 11, "as": 3, "e": 1, "dp": 0, "ej": 30.0, "pdf": 0.933}]},
                    "9": {"jug_id": "9", "name": "Miguel Torres", "positions": [{"pos": "LF", "jj": 4, "po": 6, "as": 0, "e": 1, "dp": 0, "ej": 24.0, "pdf": 0.857}]},
                    "10": {"jug_id": "10", "name": "Victor Diaz", "positions": [{"pos": "RF", "jj": 6, "po": 7, "as": 1, "e": 1, "dp": 0, "ej": 36.0, "pdf": 0.889}]},
                },
            },
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compila el portal de scouting Relámpago Softbol.")
    parser.add_argument("--config", default="config_softbol.json", type=Path)
    parser.add_argument("--snapshot", default="data/softbol_snapshot.json", type=Path)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    snapshot = build_demo_snapshot() if args.demo else json.loads(args.snapshot.read_text(encoding="utf-8"))
    manual_pos = load_manual_positions(Path(cfg.get("manual_positions_csv", "data/posiciones_manuales.csv")))

    out_dir = Path(cfg.get("output_dir", "docs"))
    teams_dir = out_dir / "equipos"
    teams_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    # Copiar logo oficial de Relámpago a docs/
    logo_src = Path(cfg.get("logo_file", "logo_relampago.png"))
    if logo_src.exists():
        shutil.copy2(logo_src, out_dir / "logo_relampago.png")

    tournaments = snapshot.get("tournaments", [])
    if not tournaments:
        print("[WARN] No hay torneos en el snapshot.")
        return

    # Detectar jugadores que participan tanto en Equipo A como en Equipo B
    players_in_a: set = set()
    players_in_b: set = set()
    our_kw = norm_text(cfg.get("our_team_keyword", "Relampago"))
    for t in tournaments:
        sq = t.get("squad", "A")
        for tname, tdata in t.get("teams", {}).items():
            if tdata.get("is_ours") or our_kw in norm_text(tname):
                for lst in (tdata.get("batting", []), tdata.get("pitching", []), tdata.get("defense", [])):
                    for p in lst:
                        (players_in_a if sq == "A" else players_in_b).add(norm_text(p["name"]))
    dual_squad_players = players_in_a & players_in_b

    # Construir vistas: 1 por cada torneo + consolidado Equipo A (si >1 torneo) + consolidado Global (A+B)
    views: Dict[str, Dict[str, Any]] = {}
    view_index: List[Dict[str, str]] = []

    for t in tournaments:
        vid = f"t{t['number']}_{t['cam_id']}"
        lbl = f"Torneo {t['number']} · Equipo {t['squad']}" if t.get("number") else f"{t['name']} (Eq. {t['squad']})"
        v_obj = build_view_for_tournaments(vid, lbl, t["squad"], [t], dual_squad_players, manual_pos, cfg)
        views[vid] = v_obj
        view_index.append({"id": vid, "label": lbl, "squad": t["squad"]})

    t_a = [t for t in tournaments if t.get("squad") == "A"]
    if len(t_a) > 1:
        vid = "hist_A"
        lbl = f"Histórico Equipo A ({len(t_a)} torneos)"
        views[vid] = build_view_for_tournaments(vid, lbl, "A", t_a, dual_squad_players, manual_pos, cfg)
        view_index.append({"id": vid, "label": lbl, "squad": "A"})

    t_b = [t for t in tournaments if t.get("squad") == "B"]
    if len(t_b) > 1:
        vid = "hist_B"
        lbl = f"Histórico Equipo B ({len(t_b)} torneos)"
        views[vid] = build_view_for_tournaments(vid, lbl, "B", t_b, dual_squad_players, manual_pos, cfg)
        view_index.append({"id": vid, "label": lbl, "squad": "B"})

    if len(tournaments) > 1:
        vid = "hist_ALL"
        lbl = f"Histórico Global A + B ({len(tournaments)} torneos)"
        views[vid] = build_view_for_tournaments(vid, lbl, "ALL", tournaments, dual_squad_players, manual_pos, cfg)
        view_index.append({"id": vid, "label": lbl, "squad": "ALL"})

    # Vista por defecto: torneo más reciente de Equipo A (que ya tiene estadísticas) o el primero disponible
    default_squad = "A" if any(v["squad"] == "A" for v in view_index) else view_index[0]["squad"]
    default_view_id = next((v["id"] for v in view_index if v["squad"] == default_squad), view_index[0]["id"])

    # Inyectar slug a standings_blocks para links desde la tabla
    for v_obj in views.values():
        for blk in v_obj.get("standings_blocks", []):
            for row in blk.get("rows", []):
                row["slug"] = slugify(row["team"])

    # Generar páginas individuales de cada equipo
    team_views_map: Dict[str, Dict[str, Any]] = defaultdict(dict)
    team_real_name: Dict[str, str] = {}
    for vid, v_obj in views.items():
        for t_obj in v_obj["teams"]:
            sl = t_obj["slug"]
            team_real_name[sl] = t_obj["name"]
            t_copy = dict(t_obj)
            t_copy["view_label"] = v_obj["label"]
            team_views_map[sl][vid] = t_copy

    for sl, by_v in team_views_map.items():
        t_payload = {
            "team_name": team_real_name[sl],
            "updated_at": snapshot["extracted_at"],
            "by_view": by_v,
        }
        (teams_dir / f"{sl}.html").write_text(render_team_report(t_payload), encoding="utf-8")

    # Generar portada principal (Quitando listas detalladas por equipo para que index.html sea liviano)
    views_for_index = {}
    for vid, v_obj in views.items():
        compact_teams = [
            {k: t[k] for k in ("name", "slug", "is_ours", "j", "g", "p", "e", "ca", "cp", "df", "pts", "team_bat", "team_pic", "profile")}
            for t in v_obj["teams"]
        ]
        views_for_index[vid] = {
            "id": v_obj["id"], "label": v_obj["label"], "squad": v_obj["squad"],
            "our_kpis": v_obj["our_kpis"],
            "standings_blocks": v_obj["standings_blocks"],
            "relampago_roster": v_obj["relampago_roster"],
            "rivals_profiles": v_obj["rivals_profiles"],
            "teams": compact_teams,
        }

    portal_payload = {
        "brand": cfg.get("our_team_display", "Relámpago del Caribe"),
        "slogan": cfg.get("slogan", "¡CACHAM!"),
        "league_name": snapshot.get("league_name", "Liga de Softbol VENEZUELA-UNIMET"),
        "updated_at": snapshot["extracted_at"],
        "default_squad": default_squad,
        "default_view_id": default_view_id,
        "view_index": view_index,
        "views": views_for_index,
    }
    (out_dir / "index.html").write_text(render_main_portal(portal_payload), encoding="utf-8")
    print(f"[OK] Portal Softbol Relámpago generado en {out_dir}/index.html ({len(team_views_map)} equipos, {len(views)} vistas).")


if __name__ == "__main__":
    main()
