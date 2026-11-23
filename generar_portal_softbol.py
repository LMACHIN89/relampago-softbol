#!/usr/bin/env python3
"""
Compilador del Portal de Scouting v2 — Relámpago del Caribe (Softbol UNIMET)
============================================================================
Mejoras v2:
  1. Logo oficial de Relámpago embebido como respaldo automático: SIEMPRE genera
     `docs/logo_relampago.png` aunque no subas el archivo de imagen por separado.
  2. Tablas completas de Relámpago directo en la portada (`docs/index.html`):
     - 🏏 Bateo (Ofensiva)
     - ⚾ Pitcheo (con respaldo automático desde fichas individuales y CSV manual)
     - 🧤 Defensiva & Posiciones (combina `est=def`, `AL CAMPO` de `jugador.php` y posiciones fijas)
  3. Posiciones Fijas de Jugadores:
     - Lee `posiciones_relampago.csv` desde la raíz del repositorio (prioridad máxima al asignar
       defensa y pitchers).
     - Incluye Editor Visual en el navegador ("⚙️ Configurar Posiciones Fijas y Pitchers") con
       botón "💾 Descargar posiciones_relampago.csv" para subirlo directo a GitHub.
"""

import argparse
import base64
import csv
import json
import re
import shutil
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_LOGO_B64 = "iVBORw0KGgoAAAANSUhEUgAAANwAAAC/CAMAAACi5EJHAAAA/1BMVEUAAAATMFDs3VQXKi/13CdaXy329vf26pmcmDXjtg38/LCopUkySV5naWqvsbI4RSlOXWTq5tfw6Mrt5LbFu0pUYWzv6sxRYG2wus2OmqgrK3N8gjdlZ6EYbW6vt8v//3+FeyxtnqFecYZ4hZE4S1j8ubn//wAAAP9teIZpdoeRn654hpiws3u3xdV4hFONna+1yNJ1hpe9wl0A//9/f//o4bw7S1V/////f38zO01BOiOwuM644Li3yNj/AAA/TD8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAC8/3nIAAAAQHRSTlMA/v7+/v4N+f7+A/73Cg3+71mgr/1U5aBjXgP+EAMvAv4V7GKdBAEBZp6enwVe/+Mk6/4BAklkAgJR/6ASpwEUpJ1oGQAAFZ5JREFUeNrtXQtb27jSli1bdmLHdi4khQQC9EaBlm7b3e65//9/9WlmdLPkQNxzPuPDQU93SeTraDTvXKUw9tpe23+0zcQLpu0l841VV+yF8m42+7p5qbyTLGs27OxF0vaRsU1zwXYvlLa7qBHnL5JxO/Y2ik5f5qyUtJW8fJm6QCqBMopuXqiiE5K2csq+v0QlIJooijbPrWZnVVUxVlG7Ipy7qp5uV2x3eMqdsU+StvIr+/nyTMczdhI9P+PErFr/4/Mbxk4/v5Ht85t/4SvLD/i9o5n+avamuu8G+jN2WgLjTp8VTmZiU0KDNyn1J/vl0SbPisq3XdTt2Bu8TyOeF07O2IbI4aq1vz3aImLOeZcSwIO3z68HbuUo8yb9pcY7qPshgRJo49fiuZ2dn0y8lYxqsli2JImxqT+PNziZqDv7e9WS4w2HKRt9Es/OODm4t3KYU/myyVFEufRJ6jjAhnAnpZzo/IukuhqBdSJf7KQk6vK0TuHfsS1JkHcSVURLCfBCTsyNGIXldSZN3IjXkhU5wIRGlScbDAhSd+PwTXoCPI/lLaqRmJUzdtoAdUlcHEsYNaCuAd4J4t0VKAFJ8yWPGvZhNIbGZ0kdL+KkH3WGd7fqNtMSKI5r2SNG44GfA35L6pJkxXlf3hFm7tiP87lkI8cRKsWIgl4zMOO5lBYY9l/gXXMBIobsTyZpFJ2MypFD6gAL8F17Uiev/AtYO5JveTLJgXFiVNHKiolr+a7b/tQlsVRrNzN2Q4MzSUEPjM59ESf4rj2pS8FSKT+DJwBsBMZFu9GFF0Cdq3nWgziQ05pfz3eKNmBcM8LQiThHYyX3FYL1FiLeQRyMxW8ClUAiiZOnvB2pby2JA0ulLVVOC7CUrxJ5+gOgEdCWIJyMNB6H49+SOTnZYsdd8OWxxtPBbyqQcfLLp1FGYmdyWgKi1N68s/4CoE0AltgDFgAxTnrg1Shn5R9KhtrETVxPYMVDkSMlIPmWpBAXGmckVrwL8USKkmSHCi2EpBdILfAbiJuMxJHrDKVKPEmS3Bc5iRZl0zQlMir3SZdjQc7uBCXuWuxm3e1ZTekfENoBPAmFqlzP5/O1NK5XHnGgwhFVkDbQA6eP2efPiSc3QFzbdJbzTk7E67k8vmh4HUJpKqdrrIi7BAdB88lj225XjQBPPMRYwbyTIFGJG5yjbeIKmJS5os3wXAU224HQqHnWbB24PYmHJzXIYHlT7c7ZXYgnEXhwRUxogjNWhzQ59+OfGOZ8LuoqIM5nTSRhMIUQlyT9N8VGzzZLFW2T5NKaMbwrzMmfL8IOYfBw3knilH8mSa9jD09MVBDhRNIHf1cpmd9JQoe0CdAZxB0sc3DXqcLRWrwQVVWGfPVooyZhhX8LQrsqEPjmWXgnwFuV2OjpMZSkjQq8p771hdayR9sExKtWTc1T+EdB3OZ5qEMV7s+7GkQu+gMUgXTUAzxBi7JNm4JMfijcIrVK9QwiByo8CfAEVPhciH9giMU3zfIkIC7nTwSTJHVfn8EliALi0M+OyoeH30oIjnlhW1Jwijb9N30iVBY9g9vw8awTTwqj0xE6VnUnmFj+JZf8iVBZjcnyYeXuh9RjPMCTGhMI2CAulrshW02bbgpNngwEcj501ZQAFc4DPSa13CQv8qLIJ6ioHqFNTcrHY0u8oZD9yZCmipD/Hqxb3SJAKeO4SHmHEmjTlvMng2WYO7kZkLgdE58bDMl6xH0xmdaVR5pSAh5xNX86Qg2QdTWY0AHbbiERAgHZIKrH28UAHlD2mpQWfsVQxEkHuWoiSmHFOT8yFJt0MC438c1HpyWP3g0FKOdM3JXKuD82kB6AicM43qqN4GGYs4AY7iAZrivNttxH+t60KaCtC0QgZTgXQZhTPqW8Hcg3ECelfttj8x+8jpNOxhlr0/EEPHuN0iZDuHXyCafAtrrowTacWl2Mo7EBVWlnZR7oFjRRhrG+PpUqXj45Pm0VKAFXxRFrTAM/3sOTFSYTPv7/ZwawkKmIe6XkAiXQMpg58YoK3/BbHeLJuwHcgLMKy9rqLbxtcSxQbuNHGAfRIogESr+9WjyAHzHxbFWKpQ1in5xiGBmZEedHkQdlYhgXaRNnqiAKgJBrgbG0IIar7JPZECpcPkKcbsiYAiuraJ4mrrQpkRBNdGSvrM5n3y8wfL0NiAOPZxBEgYe82ZQKJgLc7ko4kiHGL2NfxXGbg5VGf9UZS8Pw9WDJye/S1WFXm5KCeEHWkVrthypdn4AkTvOTeF+JmdTSSEs7dEkJvCF9uXNSd4G/k2vZ8oQxaxzbUoeFVIQSiSvROrij2eDUZ8K9MJY2nB+OFvpJd8iShMuL9snJW8dJGBoyQYZ3OO82kF7vKNGUk3ZQPxxKQIPQVp3Id+U8SI20nII2bZClLDG3irm+KCwvBnSeDZox0FnHtCP1FnWEmaM0PkjblwZKNXY7VkU86q77/jpo0VtFIUs/64huZQh5BxkHszfNUqxyq9hJc6Bof+CcOaxOAZM2SPRLZLsOs1q8LXGGxhpkEaH+7Ltg1deLqroI29eLgetMRYfIkXWxeehEGk2cy78UU3Vgn4wp0f9dZR39kCV0nJyGMbH0oMdDN/lEaHhoidPg8VhK9Id4Up7eA9S0TJfOuBcpAbIDbsa0CHcmTgk2/EgOhKmwNMUlrjMYS1ynVEP5eVwVRLedgrXCUqcTDMfxw4EvII6Ix5vwUdU3Y0JYzjUPTzDMt2HMS6h2Mm71V033MK7o8e0nel5hloAspY+YkrTz0g+guMFYuslmTMSdsxkVIkZ+FUNU7uRRUBNxK5F1KNCsB2REeHKGWcc4iOQkNXleJ5GDNh3pD5uSaxBPRlbYhio88bOOeoYpoaP+L3F8KIiuXNGGjas1HfYJ2lx/IOC4pcGljkeGtClQ2ohR1ckKpOVLiCcYGT6jIkwTxeLO5Gxn5AhPTtiI9pq4okLEoHAI7JMKPdlT32VwE/1pyxFK+TOvMQ4cVV9NQ0Od3ggk7sKvwqwd2rgPsCPEk3jVgScq0wQ6fuLIpIrL+rRBfk9+xdTbR3GgDS5yXYVD2KHX1H5qW2e2JOrSi9sVI1PhH1lXwZqODO9QKNt2NRVrJyYh1y53/oMGbBycm8GmLIFLQC6csLandLE1m7imzas5sXgiRHOoDc27DjwxLoFyiRrX7THFo97yiQaduQqyU1WYGFfBITE8nkgoqOua6zpCToWI70wIjuhP8f3Icg5LF8gBBIClpXR1bcsS6U8dmfEaVoW3V8BTZPhOgXqlNF0CywDdJQRRWCaGywLFCaay/HrSwh2vYUSuUnVCrbgwipyuhPmoADWBWB/5qpOgHFjFTyj1ttGxeLsdAiU43w6qBEGFR+WXNN3KVhT5dis/5ducVgzP7NSNGnlEvp5a1wK0lUGlN0STZ3osdHKkkf8azI7zcuglke+69whx5YOEiCSu0LTxpgnLTiWeCFjbq+w5tQCImxCvGJi4JqIUdpBltJHhK/a5dHxVKjyE2HJQGlTiUOw6/EM0X8rBNcGhNnPjPDPZAUtuaZUcMCXUHgAYAubljXLtWiHeeGwRCMeOke2UAulEWxHnHSvRNtLfOZMzvbsqtRzcHZodai2VNDsjVQ60XXIdbPftk2gtfO+2lQw/ZVej5B2CCjIut7HloE7h4e4vJ3cPJeT2mrByaFQRzbayb8jXIY505JhjbmwuUPlNYM/xsW4IOWNXarE01R0GpUGFXfyJ2dikK2U0TrZR+HJLNWLNb7wr4ZXkhWp53rFQDSOas3HStiPGwVxcXyvLOij1tvZbl38o8WSca6wB3uX7A1CeSDT0l3cCdYXbvHLvrbJPxthgqa7Sw9GDuOpaaxZ1bOjWKtseX7hWw4mApDnSBkmtkl8Ga82eKmNE82WMtP2kJNeKU7RvE3XVpjzW0D4ZdhlIP6jERdO4nde7iHf4c0+vlJix81HOSjCZacnp7JzwpBdx6Mw1o7RPYLONqAHFdSfO9soV7VM4TJvjNGMUOdr9FjzTDVIKS1vTHtSBuYLbZ43T8vobuarX6EcL8bcSw0TxF34U21ZxssINB8Uot1EnG9jGCCraTOmYhT94XgFq760Yoe21A5MZaKu08US7ax9FnVpFgzsXjHNWYoF+ecsunHhgQ1XCxeN7RmKpLMhmMx2nGkA2RdGtcFxzpA4UQpw/ur0n7EwI6wU/iXH+bMEMN9P2F4XR1nz1RG29kBxsIG7lWzZOD7zCcl6IkguPZlB3tBzhkbZV4jZOf2CHEtexbP2KfYUdH+tH96AtgW/zsf4gA0mcBMpdxyHRuYCEW/8HcOgTExcjjS6cga/jAmWLqZq68kCmETYgH/Ov8oiSS/e0+0efJO+qGbuv7sW8u4mR/1jUyWP7hB9hcsxG/FMTogHangrrzEZRzdyzXbHTqAn2ZsGShOPnm/i3Twgu2E+D9n6KbyXavRUcoOZcrnuaBsNx+jveYA63YPiA1r3Evn2xc0t50PQKfZZ6bMU+sP9MCcdxN3lvWFfeoT/n+naPcA4PTD0uCyH+DM7at77vj7EmZsasWCzmvwNe/Y7/LajNYRMG4fYslgv5dak+qTeGF5K90NkUAruFugDpxK9rvKG5j7o9EiZs7xzLbRibO6fCWYJ9FNCHbb3ARz7BlEoJx5TNM/gBAvwRAvkpM20txML97rY4I+mC19d9K/jfAm6nGkxJtjh8AyG+to4uxHtJSqtrDdTN1+51y7nY/zg+LpBBymJVkIG3WhUr+BPD4zMwdFfG+MOiEvyexAuYjxU8GC+C0+D/mZhndE6SreXN55mz3G+1whOhJUjdMlPXyotlzwKHCk7GE+VTgDqRqRdb0btkYiqOFSh6gSCHnwJ1WXzp9dGi9RReBAJ3AmhL3ROWS/ClZQPipkIfzuPWeneIJ2RyXqhzsRWyZ97uylVX3u7qgZkwMeNwSZ98UfnmqZehQG8SiEPhB9q+8dYCEDm/C7W16hLHTWWxYu8ReKa3MkYyKuzKbCGZ7lLyejx1RbhgEZ7eLiOMY70nLBIHM6ZQS4edizQ5S308wjWbXqbnMoiJpXEc1OAGXRHOmuOJ66bORAZM3RkQR1zB0ZNTf575WQDNXOLuWr9ZHUb3guWtyF6/qwi7JnK+91lU94Et1GuUUKlGE20Lo03r+zhWnhlquRw8UTGAQrWDBFxFqwXMYmpJnJy0ZocJvclxrbe0bFSiHG+t2KtGALt0nWq8VU9Qj5APXx+l7Ayo/F0JB848IzRUWIks1MlCfHgKUDfFWUkLqr7pX9UwMxdnIgKV5kmsjyff9O1TOxmdH2ugoaB11mZQUvfhwloOx2gDmGCGosS+Z62SgRnowMzDEyBOPS+2E9ZM5SK2S0P07MJOdWZin2gJ0Dl0rCni/DLxz6KH/9nL1FoadmWaHbECOESxNVgZmYMne5JU9VbyIizuqq38Q42TWdRjSJKqy9zePNHc1ulKpCiksEFJeFbWz7q8NxNshfiv2aFHG40xxizKZ2wvncu1YXeW2cHXxDkJVUeHxPb2msjMcj1XI5TFEyjdc0c6s2/TByyZmWDwgztrxf6tfiHok2yTzLNPQpFziVXDuo2t9kgNAJP2V3NKfyI84alDQGLoRtNIHlEjTYOiKJfy/r4HcXtHekCPGumw4p2h1BmRk8TtjRar4YgvctCdOhgf+7OLih2IOPXsxAEwpC3L7KBkjsj1qXMATCfsSFsiR31NDKYg2H6uSEtVMLcj4lxkVwaaEksrTYVDnB5D+9qJgyfGoLWDotAt65eXnIqlg1P0xrXGk8jamplrn1QaT7gL0xRaDbPcdubRCXrlBeke7qpwKCBSbZIkdlAm6tOyH54IIz1mE0DXPokMaGgRk84JeAQAaWrSfdOi0VW44Iic3j4x1cQBuUUbLEEatZVMQ1FbPMl/CU9oA7UiddSuQxyZ0RrMyHJdavwq1E5yB36HyOJJUxg9YfAkT+uWhebsI1M7GlCJQJ1kfYkzNqL9rcO4xQRg3NrFE2HtE+cqY1krceNN6ZktPGqbY/YHUwyeXJq6WbXxKgqaVanz/njib0hpJBiWMSBBCxev/rT2iVsAa4CDDqQhhkaR+qWpmIfs5bqkj0ctk6Vog1k/4pbexr2EYSsr8WCsLixyMfFh+iF0CWoLLNxsc+9hKGyxmBvF7SQMjMhBtV/T8hJQha8MmPXaZ2OvpUfPmjJGN1k/CxTOei2WxohZfpii8bXSc43XLdmSxOk/vG22ROiDO/6C3fje2id6ZypaNdPGk1W27CdyQk8wrna2gpsxa1CtIfgkhDURFhCHtI5omhffak9Xo3SutPLU4svRbcoy4wjKjpwKHVz7xFEc1nbdGvtkynq6qgapjTOKfZzgA8fAivRCfTeayuoshddYCZs6E5sAMccJvhDaaIjwZ3zSFngYCy2yWr2NJ72Jq5Xnr5UJTJw6wh+GyChmuHDuD+GThWNgJ8Y+0UO+4mqrPGSgNc6yNdjge831wthBqfIhHGOkiQOXoOhL3J5BlKc1rbZgYhbaZtEhQxr+3H5Pyfe2NqdjjdagyrReNLiwButC7F0nxPd3Jol1tdRZieOg9DS+9q594tiptk9V6xIEOBuPBcZhbK3ENHV9UOvA7wVsca1VMgxi7vk7xmRZWbfEdGXLn/esVwDFNYBTFSTJVPzE7g1HHWZ7romZi2tcONzCkzgGBhi5sjpqv8e6gMwZxLxljOD967CrjDSeVL+CJ651z1z7BNdGta1G+AWapGX2cSc4toqzlkXvKEiEogutMhm68HoE6tAiDRR9f3/HjHym3zMwEn2T2Kyc6vB3wLtFoXQnHEea0aCXRkNW2Cld66hZe2EFzEpceeb0fQP7QfRSc9bglhJAsrz1av3N8Ld3CXHdyJZsCVSe25a/U6toKh4qjOVhBjYw0TKvCyP8H6peEkfEwUTLlqB/YBZixNRtcStgj7NyorwSqTT+6mcSBOlFvxth3Hi5PCU8gTahCdBKVawXQdfifS9f7p/wFhN0DUGBydthS4zDmMMe/TnoMqcHTkjwQAJ4Ahv5wz7+1DWBAYZsD51qLlUwDnZ6QjcBiujZCRjmziMgC4S6Hk5Tl6M3wnoTp1om7Ge/HT6wCE7LFmKqk1fudQuV7ZzbJ7rPXjrnZpKQD+0uvG3PsgAByc0lNml5/E6fVIdti7nfoT/M2Vx91reRXRBz+n1puhd0Be1IIP8/1zeVhg7dawEBbOepc0BFSLOap6nw4sBt3yXI/34KftrR9QvkufUE00OtOnTgfXgNApoIrrjXwyB0SUQlpvf2GtMNdxXtM+/vp/fjrjB6ba/ttb221/baXttre22v7bW9ttf22v7XWvXiXHWssyeqquoFMqz6X5iWrwGk/+r2f8c/ZWyz3FQ6AAAAAElFTkSuQmCC"


def norm_text(s: str) -> str:
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(s))
    asc = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", asc).strip().lower()


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm_text(s)).strip("-") or "equipo"


DEFAULT_PLAYER_ALIASES: Dict[str, str] = {
    "radames larez": "Radames Lares",
    "radames lares": "Radames Lares",
    "pedro branacaccio": "Pedro Brancaccio",
    "pedro brancaccio": "Pedro Brancaccio",
    "andres vahamonde": "Andres Vaamonde",
    "andres vaamonde": "Andres Vaamonde",
}


def build_alias_map(cfg: Dict[str, Any]) -> Dict[str, str]:
    amap = dict(DEFAULT_PLAYER_ALIASES)
    for k, v in (cfg.get("player_aliases") or {}).items():
        if k and v:
            amap[norm_text(k)] = str(v).strip()
    return amap


def canonical_player_key_and_name(raw_name: str, alias_map: Dict[str, str]) -> Tuple[str, str]:
    clean = re.sub(r"\s+", " ", str(raw_name or "")).strip()
    n = norm_text(clean)
    if n in alias_map:
        canon = alias_map[n]
        return norm_text(canon), canon
    # Si viene todo en mayúsculas (ej. "MARIO VEROCHI"), dejar en formato título limpio
    disp = clean.title() if clean.isupper() else clean
    return n, disp


def normalize_manual_pos(raw: str) -> str:
    s = norm_text(raw)
    if not s:
        return ""
    if s in ("p", "pitcher", "lanzador", "1"): return "P"
    if s in ("c", "catcher", "receptor", "2"): return "C"
    if s in ("1b", "1ra", "primera", "primera base", "3"): return "1B"
    if s in ("2b", "2da", "segunda", "segunda base", "4"): return "2B"
    if s in ("3b", "3ra", "tercera", "tercera base", "5"): return "3B"
    if s in ("ss", "short", "shortstop", "short stop", "campo corto", "campocorto", "6"): return "SS"
    if s in ("lf", "left", "left field", "jardin izquierdo", "izquierdo", "7"): return "LF"
    if s in ("cf", "center", "center field", "jardin central", "central", "8"): return "CF"
    if s in ("rf", "right", "right field", "jardin derecho", "derecho", "9"): return "RF"
    if s in ("sfe", "short field externo", "shortfield externo", "sf externo", "externo", "4to", "4to field", "cuarto", "11"): return "SFE"
    if s in ("sfi", "short field interno", "shortfield interno", "sf interno", "interno", "sf", "short field", "shortfield", "10"): return "SFI"
    if s in ("bd", "dh", "ep", "designado", "bateador designado", "extra"): return "BD"
    return raw.strip().upper()


def load_manual_positions(cfg: Dict[str, Any], alias_map: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """
    Lee `posiciones_relampago.csv` tolerando:
      - Codificación UTF-8, UTF-8-BOM o Windows-1252/Latin-1 (Excel en español con ñ y acentos)
      - Separador por coma (,) o punto y coma (;) típico de Excel en español
    """
    import io

    candidates = [
        Path(cfg.get("manual_positions_csv", "posiciones_relampago.csv")),
        Path("posiciones_relampago.csv"),
        Path("data/posiciones_relampago.csv"),
        Path("data/posiciones_manuales.csv"),
    ]
    out: Dict[str, Dict[str, Any]] = {}
    for csv_path in candidates:
        if not csv_path.exists():
            continue
        raw_bytes = csv_path.read_bytes()
        text = None
        used_enc = ""
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = raw_bytes.decode(enc)
                used_enc = enc
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            text = raw_bytes.decode("latin-1", errors="replace")
            used_enc = "latin-1-fallback"

        # Detectar delimitador (Excel en español suele guardar con ';')
        first_line = next((ln for ln in text.splitlines() if ln.strip()), "")
        delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
        if first_line.count("\t") > max(first_line.count(","), first_line.count(";")):
            delimiter = "\t"

        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        for raw_row in reader:
            # Normalizar nombres de columnas (sin espacios ni acentos)
            r = {norm_text(k): (v or "").strip() for k, v in raw_row.items() if k is not None}
            name = (r.get("jugador") or r.get("name") or r.get("nombre") or "").strip()
            if not name:
                continue
            k, name = canonical_player_key_and_name(name, alias_map)
            if k in out:
                continue
            pos1 = normalize_manual_pos(r.get("pos_primaria") or r.get("posicion_primaria") or r.get("pos1") or r.get("posicion") or "")
            pos2 = normalize_manual_pos(r.get("pos_secundaria") or r.get("posicion_secundaria") or r.get("pos2") or "")
            pos3 = normalize_manual_pos(r.get("pos_terciaria") or r.get("posicion_terciaria") or r.get("pos3") or "")
            is_p_raw = norm_text(r.get("es_pitcher") or r.get("pitcher") or "")
            is_pitcher = is_p_raw in ("si", "yes", "1", "true", "x") or pos1 == "P" or pos2 == "P"
            out[k] = {
                "name": name,
                "squad": r.get("equipo") or "",
                "pos1": pos1,
                "pos2": pos2,
                "pos3": pos3,
                "is_pitcher": is_pitcher,
                "pitcher_role": r.get("rol_pitcher") or r.get("rol") or "",
            }
        if out:
            print(f"[INFO] Posiciones fijas cargadas desde '{csv_path}' ({len(out)} jugadores, enc={used_enc}, sep='{delimiter}').")
            break
    return out


def ensure_logo_in_docs(cfg: Dict[str, Any], out_dir: Path) -> None:
    """Garantiza que `docs/logo_relampago.png` exista siempre (archivo externo o embebido)."""
    target = out_dir / "logo_relampago.png"
    candidates = [
        Path(cfg.get("logo_file", "logo_relampago.png")),
        Path("logo_relampago.png"),
        Path("assets/logo_relampago.png"),
    ]
    for c in candidates:
        if c.exists() and c.stat().st_size > 500:
            shutil.copy2(c, target)
            return
    # Respaldo automático: escribir el logo transparente embebido
    target.write_bytes(base64.b64decode(DEFAULT_LOGO_B64))
    print(f"[INFO] Logo oficial de Relámpago generado automáticamente en {target}.")


def aggregate_batting(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
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
    alias_map: Dict[str, str],
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    our_kw = norm_text(cfg.get("our_team_keyword", "Relampago"))
    standings_blocks = selected_tournaments[0].get("standings_blocks", []) if len(selected_tournaments) == 1 else []

    all_games = []
    for t in selected_tournaments:
        for g in t.get("games", []):
            gc = dict(g)
            gc["tournament"] = t["name"]
            gc["squad"] = t["squad"]
            all_games.append(gc)

    teams_bat_raw: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    teams_pic_raw: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    teams_def_raw: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    team_records: Dict[str, Dict[str, int]] = defaultdict(lambda: {"j": 0, "g": 0, "p": 0, "e": 0, "ca": 0, "cp": 0, "pts": 0})
    team_is_ours: Dict[str, bool] = {}

    our_bat_by_p: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    our_pic_by_p: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    our_pic_backup_by_p: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    our_def_by_p: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    our_pos_by_p: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    our_display_names: Dict[str, str] = {}

    for t in selected_tournaments:
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

        # Detalle individual de jugador.php (AL CAMPO + backup de pitcheo)
        for _, det in t.get("relampago_player_details", {}).items():
            pn, cname = canonical_player_key_and_name(det.get("name", ""), alias_map)
            if not pn:
                continue
            our_display_names[pn] = cname
            for pos_row in det.get("positions", []):
                pcode = normalize_manual_pos(pos_row.get("pos") or pos_row.get("pos_raw") or "")
                if pcode:
                    pr_copy = dict(pos_row)
                    pr_copy["pos"] = pcode
                    our_pos_by_p[pn][pcode].append(pr_copy)
            if det.get("pitching_backup"):
                pb = dict(det["pitching_backup"])
                pb["name"] = cname
                our_pic_backup_by_p[pn].append(pb)

        for tname, tdata in t.get("teams", {}).items():
            is_ours = bool(tdata.get("is_ours")) or (our_kw in norm_text(tname))
            team_is_ours[tname] = is_ours
            teams_bat_raw[tname].extend(tdata.get("batting", []))
            teams_pic_raw[tname].extend(tdata.get("pitching", []))
            teams_def_raw[tname].extend(tdata.get("defense", []))

            if is_ours:
                for r_p in tdata.get("roster", []):
                    k, cname = canonical_player_key_and_name(r_p["name"], alias_map)
                    if k:
                        our_display_names[k] = cname
                for b in tdata.get("batting", []):
                    k, cname = canonical_player_key_and_name(b["name"], alias_map)
                    if k:
                        our_display_names[k] = cname; our_bat_by_p[k].append(b)
                for pc in tdata.get("pitching", []):
                    k, cname = canonical_player_key_and_name(pc["name"], alias_map)
                    if k:
                        our_display_names[k] = cname; our_pic_by_p[k].append(pc)
                for df in tdata.get("defense", []):
                    k, cname = canonical_player_key_and_name(df["name"], alias_map)
                    if k:
                        our_display_names[k] = cname; our_def_by_p[k].append(df)
                        if df.get("pos"):
                            pcode = normalize_manual_pos(df["pos"])
                            if pcode:
                                df_c = dict(df); df_c["pos"] = pcode
                                our_pos_by_p[k][pcode].append(df_c)

    # Incluir también jugadores definidos en `posiciones_relampago.csv` si coinciden con el equipo (A/B)
    for mk, mv in manual_pos.items():
        sq_str = norm_text(mv.get("squad", ""))
        matches_sq = (squad_tag == "ALL") or (not sq_str) or (norm_text(squad_tag) in sq_str)
        if matches_sq and mk not in our_display_names:
            our_display_names[mk] = mv["name"]

    # Construir roster consolidado de Relámpago
    all_our_keys = set(our_display_names.keys()) | set(our_bat_by_p.keys()) | set(our_pic_by_p.keys()) | set(our_def_by_p.keys())
    relampago_roster: List[Dict[str, Any]] = []

    for pk in sorted(all_our_keys):
        disp_name = our_display_names.get(pk, pk.title())
        bat = aggregate_batting(our_bat_by_p.get(pk, []))

        # Pitcheo: usar tabla est=pic; si viene vacía, usar respaldo de jugador.php
        pic_rows = our_pic_by_p.get(pk, []) or our_pic_backup_by_p.get(pk, [])
        pic = aggregate_pitching(pic_rows)

        # Posiciones defensivas reales (`AL CAMPO`)
        real_pos_list = []
        for pos_code, plist in our_pos_by_p.get(pk, {}).items():
            agg_p = aggregate_defense(plist)
            agg_p["pos"] = pos_code
            real_pos_list.append(agg_p)
        real_pos_list.sort(key=lambda x: (-x["ej"], -x["jj"], -x["pdf"]))

        # Defensiva global: priorizar est=def (que trae IJ/PO/A/E/DP/PDF aunque no traiga columna JJ);
        # si viene vacía, usar los totales de AL CAMPO (jugador.php) y conservar JJ de AL CAMPO si está disponible.
        dfn_raw = aggregate_defense(our_def_by_p.get(pk, []))
        dfn_from_pos = aggregate_defense(real_pos_list) if real_pos_list else {"jj": 0, "po": 0, "as": 0, "e": 0, "dp": 0, "ej": 0.0, "pdf": 0.0}
        raw_has_data = (dfn_raw["ej"] > 0) or (dfn_raw["po"] + dfn_raw["as"] + dfn_raw["e"] > 0)
        pos_has_more = (dfn_from_pos["ej"] > dfn_raw["ej"] + 0.5) and (dfn_from_pos["po"] + dfn_from_pos["as"] + dfn_from_pos["e"] > dfn_raw["po"] + dfn_raw["as"] + dfn_raw["e"])
        if raw_has_data and not pos_has_more:
            dfn = dict(dfn_raw)
            if dfn["jj"] == 0 and dfn_from_pos["jj"] > 0:
                dfn["jj"] = dfn_from_pos["jj"]
        else:
            dfn = dfn_from_pos

        mp = manual_pos.get(pk, {})
        fixed_pos1 = mp.get("pos1", "")
        fixed_pos2 = mp.get("pos2", "")
        fixed_pos3 = mp.get("pos3", "")
        is_pitcher = (pic["ip"] > 0) or bool(mp.get("is_pitcher")) or (fixed_pos1 == "P") or (fixed_pos2 == "P")

        if pic["ip"] > 0 and not any(x["pos"] == "P" for x in real_pos_list):
            real_pos_list.append({"pos": "P", "jj": pic["jj"], "po": 0, "as": 0, "e": 0, "dp": 0, "ej": pic["ip"], "pdf": dfn["pdf"] or 0.900})

        primary_pos = fixed_pos1 or (real_pos_list[0]["pos"] if real_pos_list else ("P" if is_pitcher else "UTIL"))
        secondary_pos = fixed_pos2 or (real_pos_list[1]["pos"] if len(real_pos_list) > 1 else "")

        relampago_roster.append({
            "name": disp_name,
            "dual_squad": pk in dual_squad_players,
            "batting": bat,
            "pitching": pic,
            "defense": dfn,
            "positions": real_pos_list,
            "fixed_pos1": fixed_pos1,
            "fixed_pos2": fixed_pos2,
            "fixed_pos3": fixed_pos3,
            "primary_pos": primary_pos,
            "secondary_pos": secondary_pos,
            "is_pitcher": is_pitcher,
            "pitcher_role": mp.get("pitcher_role", ""),
        })

    relampago_roster.sort(key=lambda x: (-x["batting"]["ops"], -x["batting"]["vb"], x["name"]))

    # Consolidar perfiles de TODOS los equipos
    teams_summary: List[Dict[str, Any]] = []
    rivals_profiles: List[Dict[str, Any]] = []
    our_kpis = {"j": 0, "g": 0, "p": 0, "e": 0, "ca": 0, "cp": 0, "df": 0, "avg": 0.0, "ops": 0.0, "efe": 0.0, "whip": 0.0}

    all_team_names = sorted(set(team_records.keys()) | set(teams_bat_raw.keys()))
    for tname in all_team_names:
        is_ours = team_is_ours.get(tname, our_kw in norm_text(tname))
        rec = team_records[tname]

        if is_ours:
            bat_players = [{"name": p["name"], **p["batting"]} for p in relampago_roster]
            pic_players = [{"name": p["name"], **p["pitching"]} for p in relampago_roster if p["pitching"]["ip"] > 0 or p["is_pitcher"]]
            def_players = [{"name": p["name"], "pos": p["primary_pos"], **p["defense"]} for p in relampago_roster if p["defense"]["jj"] > 0 or p["defense"]["ej"] > 0 or (p["defense"]["po"] + p["defense"]["as"] + p["defense"]["e"]) > 0 or p["fixed_pos1"]]
        else:
            p_bat_grp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            p_pic_grp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            p_def_grp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            p_names: Dict[str, str] = {}
            for b in teams_bat_raw.get(tname, []):
                k, cname = canonical_player_key_and_name(b["name"], alias_map); p_names[k] = cname; p_bat_grp[k].append(b)
            for pc in teams_pic_raw.get(tname, []):
                k, cname = canonical_player_key_and_name(pc["name"], alias_map); p_names[k] = cname; p_pic_grp[k].append(pc)
            for df in teams_def_raw.get(tname, []):
                k, cname = canonical_player_key_and_name(df["name"], alias_map); p_names[k] = cname; p_def_grp[k].append(df)
            bat_players = [{"name": p_names[k], **aggregate_batting(v)} for k, v in p_bat_grp.items()]
            pic_players = [{"name": p_names[k], **aggregate_pitching(v)} for k, v in p_pic_grp.items()]
            def_players = [{"name": p_names[k], **aggregate_defense(v)} for k, v in p_def_grp.items()]

        bat_players.sort(key=lambda x: (-x["ops"], -x["vb"]))
        pic_players.sort(key=lambda x: (x["efe"] if x["ip"] > 0 else 99, x["whip"]))
        def_players.sort(key=lambda x: (-x["ej"], -x["jj"], -x["pdf"]))

        t_bat = aggregate_batting(bat_players)
        t_pic = aggregate_pitching([p for p in pic_players if p["ip"] > 0])
        t_def = aggregate_defense(def_players)
        profile = classify_opponent_offense(t_bat, rec["j"])

        t_games, h2h_games = [], []
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
            item = {"date": gm["date"], "tournament": gm["tournament"], "venue": "Visita" if is_v else "Local", "opponent": opp, "score_for": sc_for, "score_against": sc_ag, "result": res}
            t_games.append(item)
            if not is_ours and our_kw in norm_text(opp):
                h2h_games.append(item)

        t_obj = {
            "name": tname, "slug": slugify(tname), "is_ours": is_ours,
            "j": rec["j"], "g": rec["g"], "p": rec["p"], "e": rec["e"],
            "ca": rec["ca"], "cp": rec["cp"], "df": rec["ca"] - rec["cp"], "pts": rec["pts"],
            "ca_pg": round(rec["ca"] / rec["j"], 1) if rec["j"] else 0.0,
            "cp_pg": round(rec["cp"] / rec["j"], 1) if rec["j"] else 0.0,
            "team_bat": t_bat, "team_pic": t_pic, "team_def": t_def, "profile": profile,
            "batting": bat_players, "pitching": pic_players, "defense": def_players,
            "games": t_games, "h2h_vs_relampago": h2h_games,
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
                "name": tname, "slug": slugify(tname), "j": rec["j"], "g": rec["g"], "p": rec["p"],
                "ca_pg": t_obj["ca_pg"], "cp_pg": t_obj["cp_pg"],
                "avg": t_bat["avg"], "obp": t_bat["obp"], "slg": t_bat["slg"], "ops": t_bat["ops"],
                "hr": t_bat["hr"], "bb": t_bat["bb"], "efe": t_pic["efe"], "profile": profile,
                "top_batters": [{"name": b["name"], "avg": b["avg"], "ops": b["ops"], "hr": b["hr"]} for b in bat_players[:3]],
            })

    teams_summary.sort(key=lambda x: (0 if x["is_ours"] else 1, -x["pts"], -x["g"], -x["df"], x["name"]))
    rivals_profiles.sort(key=lambda x: (-x["ops"], -x["g"], x["name"]))

    return {
        "id": view_id, "label": view_label, "squad": squad_tag,
        "our_kpis": our_kpis, "standings_blocks": standings_blocks,
        "relampago_roster": relampago_roster, "rivals_profiles": rivals_profiles,
        "teams": teams_summary, "games": all_games,
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
      --navy:#0e2644; --navy-mid:#133150; --navy-soft:#e6eef7;
      --gold:#f0d72b; --gold-dark:#b48a04; --gold-soft:#fef9c3;
      --bg:#f3f5f8; --surface:#ffffff; --surface-alt:#f8fafc;
      --border:#e2e8f0; --border-strong:#cbd5e1;
      --text:#0f172a; --muted:#475569; --light:#64748b;
      --green:#15803d; --green-soft:#dcfce7; --red:#dc2626; --red-soft:#fee2e2;
      --shadow:0 2px 6px rgba(14,38,68,0.06), 0 6px 18px rgba(14,38,68,0.05);
      --font:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      --mono:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ font-family:var(--font); background:var(--bg); color:var(--text); line-height:1.5; }}
    .wrap {{ max-width:1180px; margin:0 auto; padding:18px 16px 64px; }}

    .hero {{ background:linear-gradient(135deg,#091a30 0%,#133150 65%,#1a426b 100%); color:#fff; border-radius:18px; padding:24px 26px; margin-bottom:16px; border-bottom:4px solid var(--gold); box-shadow:0 12px 30px rgba(9,26,48,0.22); }}
    .hero-top {{ display:flex; align-items:center; gap:20px; flex-wrap:wrap; margin-bottom:18px; }}
    .logo-wrap {{ background:rgba(255,255,255,0.96); border-radius:16px; padding:8px 12px; border:2px solid var(--gold); box-shadow:0 4px 14px rgba(0,0,0,0.25); flex-shrink:0; display:flex; align-items:center; justify-content:center; }}
    .logo-wrap img {{ height:72px; width:auto; display:block; }}
    .slogan-pill {{ display:inline-block; background:var(--gold); color:var(--navy); font-size:11px; font-weight:900; letter-spacing:1px; padding:2px 10px; border-radius:999px; margin-bottom:6px; }}
    .hero h1 {{ font-size:clamp(22px,3vw,30px); font-weight:900; line-height:1.15; margin-bottom:4px; }}
    .hero-sub {{ color:#cbd5e1; font-size:13.5px; }}
    .kpi-grid {{ display:grid; grid-template-columns:repeat(5,1fr); gap:10px; }}
    .kpi {{ background:rgba(255,255,255,0.09); border:1px solid rgba(240,215,43,0.28); border-radius:10px; padding:12px 14px; }}
    .kpi-v {{ font-size:22px; font-weight:800; color:#fff; font-variant-numeric:tabular-nums; }}
    .kpi-v.gold {{ color:var(--gold); }}
    .kpi-l {{ font-size:11.5px; color:#cbd5e1; }}

    .filter-bar {{ position:sticky; top:8px; z-index:60; background:rgba(255,255,255,0.97); backdrop-filter:blur(10px); border:1px solid var(--border-strong); border-radius:14px; padding:12px 16px; margin-bottom:20px; box-shadow:0 6px 20px rgba(14,38,68,0.1); display:flex; flex-direction:column; gap:10px; }}
    .filter-row {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
    .f-label {{ font-size:11.5px; font-weight:800; text-transform:uppercase; letter-spacing:0.6px; color:var(--navy); min-width:80px; }}
    .pills {{ display:inline-flex; flex-wrap:wrap; gap:6px; }}
    .pill-btn {{ border:1px solid var(--border-strong); background:var(--surface-alt); color:var(--muted); padding:6px 13px; border-radius:999px; font-size:12.5px; font-weight:700; cursor:pointer; transition:all .15s; }}
    .pill-btn:hover {{ border-color:var(--navy); color:var(--navy); background:var(--navy-soft); }}
    .pill-btn.active {{ background:var(--navy); border-color:var(--navy); color:#fff; }}
    .pill-btn.gold-active {{ background:var(--gold); border-color:var(--gold-dark); color:var(--navy); font-weight:900; }}

    .section {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:22px; margin-bottom:20px; box-shadow:var(--shadow); }}
    .sec-head {{ display:flex; justify-content:space-between; align-items:flex-end; flex-wrap:wrap; gap:10px; margin-bottom:16px; }}
    h2 {{ font-size:19px; font-weight:900; color:var(--navy); }}
    .sub {{ font-size:13px; color:var(--light); margin-top:2px; }}

    .strat-controls {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; background:var(--navy-soft); border:1px solid #c5d7ee; border-radius:12px; padding:14px; margin-bottom:16px; }}
    .sel {{ padding:8px 12px; border:1px solid var(--border-strong); border-radius:8px; font-size:13.5px; font-weight:700; background:#fff; color:var(--navy); min-width:220px; }}
    .btn {{ border:1px solid var(--border-strong); background:#fff; color:var(--navy); padding:8px 13px; border-radius:8px; font-size:12.5px; font-weight:800; cursor:pointer; }}
    .btn:hover {{ background:var(--navy-soft); border-color:var(--navy); }}
    .btn-gold {{ background:var(--gold); border-color:var(--gold-dark); color:var(--navy); }}
    .btn-gold:hover {{ background:#e5c914; }}
    .btn-green {{ background:var(--green); border-color:var(--green); color:#fff; }}
    .btn-green:hover {{ background:#166534; }}

    .editor-panel {{ background:#fffef5; border:2px solid var(--gold-dark); border-radius:12px; padding:16px; margin-bottom:16px; }}
    .editor-panel h3 {{ font-size:15px; font-weight:900; color:var(--navy); margin-bottom:6px; }}
    .ed-sel {{ padding:4px 6px; border:1px solid var(--border-strong); border-radius:6px; font-size:12px; background:#fff; }}

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
    .pitcher-top {{ display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:4px; flex-wrap:wrap; }}
    .rival-alert {{ background:var(--gold-soft); border:1px solid #eab308; color:#713f12; border-radius:10px; padding:10px 14px; font-size:13px; margin-bottom:12px; }}

    .lineup-row {{ display:grid; grid-template-columns:30px 1.2fr 96px 1fr; gap:8px; align-items:center; background:#fff; border:1px solid var(--border); border-radius:8px; padding:8px 10px; margin-bottom:6px; font-size:12.5px; }}
    .ord-num {{ width:26px; height:26px; border-radius:7px; background:var(--navy); color:var(--gold); font-weight:900; display:flex; align-items:center; justify-content:center; font-size:12px; }}
    .role-tag {{ font-size:10.5px; font-weight:800; padding:2px 7px; border-radius:999px; background:var(--navy-soft); color:var(--navy); text-align:center; white-space:nowrap; }}
    .role-tag.power {{ background:var(--gold-soft); color:#854d0e; }}
    .role-tag.lead {{ background:var(--green-soft); color:var(--green); }}
    .stat-mono {{ font-family:var(--mono); font-size:11.5px; color:var(--muted); text-align:right; }}

    .diamond-wrap {{ background:linear-gradient(180deg,#166534 0%,#15803d 100%); border-radius:12px; padding:10px; margin-bottom:12px; }}
    .diamond-svg {{ width:100%; height:auto; display:block; max-height:310px; }}
    .def-list {{ display:grid; grid-template-columns:repeat(2,1fr); gap:6px; }}
    .def-slot {{ display:flex; align-items:center; gap:6px; background:#fff; border:1px solid var(--border); border-radius:8px; padding:6px 8px; font-size:12px; }}
    .pos-b {{ font-family:var(--mono); font-weight:900; font-size:11px; background:var(--navy); color:var(--gold); padding:2px 6px; border-radius:5px; min-width:30px; text-align:center; }}
    .def-sel {{ flex:1; border:1px solid var(--border); border-radius:6px; padding:4px 6px; font-size:12px; font-family:var(--font); }}

    /* Stats Tabs */
    .stats-tabs {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; }}
    .stab {{ border:1px solid var(--border-strong); background:var(--surface-alt); color:var(--muted); padding:8px 16px; border-radius:10px; font-size:13px; font-weight:800; cursor:pointer; }}
    .stab.active {{ background:var(--navy); color:var(--gold); border-color:var(--navy); }}
    .search-in {{ padding:8px 12px; border:1px solid var(--border-strong); border-radius:8px; font-size:13px; min-width:220px; }}

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
    .badge.gold {{ background:var(--gold); color:var(--navy); }}
    .footer {{ text-align:center; font-size:12px; color:var(--light); margin-top:28px; }}

    @media (max-width:920px) {{ .kpi-grid {{ grid-template-columns:repeat(2,1fr); }} .three-col {{ grid-template-columns:1fr; }} }}
    @media (max-width:600px) {{ .def-list {{ grid-template-columns:1fr; }} .lineup-row {{ grid-template-columns:28px 1fr; }} .stat-mono {{ text-align:left; }} }}
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
      const ALL_POS = ["", "P", "C", "1B", "2B", "3B", "SS", "SFI", "SFE", "LF", "CF", "RF", "BD"];

      let activeSquad = data.default_squad || "A";
      let activeViewId = data.default_view_id;
      let selectedRivalName = "";
      let activeStatsTab = "bat"; // bat | pic | def
      let statsSearch = "";
      let showPosEditor = false;
      let unavailableSet = new Set();
      let customDefMap = {{}};

      // Overrides locales de posiciones fijas y pitchers (se combinan con posiciones_relampago.csv)
      const STORAGE_KEY = "relampago_pos_overrides_v1";
      let localPosOverrides = {{}};
      try {{ localPosOverrides = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{{}}"); }} catch(e) {{}}
      function saveLocalOverrides() {{
        try {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(localPosOverrides)); }} catch(e) {{}}
      }}

      function enrichRosterWithLocal(roster) {{
        return roster.map(p => {{
          const ov = localPosOverrides[p.name] || {{}};
          const f1 = (ov.pos1 !== undefined) ? ov.pos1 : (p.fixed_pos1 || "");
          const f2 = (ov.pos2 !== undefined) ? ov.pos2 : (p.fixed_pos2 || "");
          const isP = (ov.is_pitcher !== undefined) ? ov.is_pitcher : (p.is_pitcher || f1 === "P" || f2 === "P");
          const pRole = (ov.pitcher_role !== undefined) ? ov.pitcher_role : (p.pitcher_role || "");
          const prim = f1 || p.primary_pos || (isP ? "P" : "UTIL");
          const sec = f2 || p.secondary_pos || "";
          return {{ ...p, fixed_pos1: f1, fixed_pos2: f2, primary_pos: prim, secondary_pos: sec, is_pitcher: isP, pitcher_role: pRole }};
        }});
      }}

      function getViewsForSquad(sq) {{
        return data.view_index.filter(v => sq === "ALL" ? true : (v.squad === sq));
      }}

      function recommendPitchers(roster, rival) {{
        const pitchers = roster.filter(p => p.is_pitcher || (p.pitching && p.pitching.ip > 0));
        const focus = rival && rival.profile ? rival.profile.pitcher_focus : "balanced";
        return pitchers.map(p => {{
          const pc = p.pitching;
          const ip = pc.ip || 0;
          let score = 40;
          if (p.pitcher_role && p.pitcher_role.toLowerCase().includes("abrid")) score += 12;
          if (ip > 0) {{
            const efeScore = Math.max(0, 12 - pc.efe) * 4;
            const whipScore = Math.max(0, 3.0 - pc.whip) * 18;
            const bbScore = Math.max(0, 6 - pc.bb7) * 5;
            const hrScore = Math.max(0, 2 - pc.hr7) * 10;
            const kScore = Math.min(pc.k7, 7) * 2.5;
            const expBonus = Math.min(ip, 25) * 0.4;
            if (focus === "anti_power") score += efeScore * 1.2 + hrScore * 1.5 + whipScore + expBonus;
            else if (focus === "command") score += bbScore * 1.6 + whipScore * 1.3 + efeScore * 0.8 + expBonus;
            else if (focus === "whip_def") score += whipScore * 1.4 + efeScore + kScore + expBonus;
            else score += efeScore + whipScore + bbScore * 0.8 + expBonus;
          }}
          let reason = "Rotación disponible";
          if (ip === 0) reason = `Habilitado como pitcher${{p.pitcher_role ? " (" + p.pitcher_role + ")" : ""}} — aún sin innings registrados en este torneo.`;
          else if (focus === "anti_power") reason = `EFE ${{pc.efe.toFixed(2)}} y ${{pc.hr7.toFixed(1)}} HR/7 — mejor perfil para contener poder.`;
          else if (focus === "command") reason = `Solo ${{pc.bb7.toFixed(1)}} BB/7 y WHIP ${{pc.whip.toFixed(2)}} — ideal ante rival que toma boletos.`;
          else reason = `EFE ${{pc.efe.toFixed(2)}} · WHIP ${{pc.whip.toFixed(2)}} en ${{pc.ip.toFixed(1)}} IP (${{pc.g}}–${{pc.p}}).`;
          return {{ player: p, score, reason }};
        }}).sort((a, b) => b.score - a.score);
      }}

      function buildOffensiveLineup(availPlayers) {{
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
        const slots = new Array(Math.min(11, scored.length)).fill(null);
        const roles = [
          {{ lbl: "1° Leadoff", cls: "lead" }}, {{ lbl: "2° Contacto", cls: "lead" }},
          {{ lbl: "3° Mejor Bate", cls: "power" }}, {{ lbl: "4° Cleanup", cls: "power" }},
          {{ lbl: "5° Poder", cls: "power" }}, {{ lbl: "6° Producción", cls: "" }},
          {{ lbl: "7° Contacto", cls: "" }}, {{ lbl: "8° Soporte", cls: "" }},
          {{ lbl: "9° Puente", cls: "" }}, {{ lbl: "10° Contacto", cls: "" }},
          {{ lbl: "11° 2do Leadoff", cls: "lead" }},
        ];
        if (slots.length >= 1) slots[0] = takeBest(x => x.adjObp * 1.4 + (x.p.batting.ca * 0.02));
        if (slots.length >= 4) slots[3] = takeBest(x => x.adjSlg * 1.3 + x.adjOps * 0.5 + x.p.batting.hr * 0.08 + x.p.batting.ci * 0.015);
        if (slots.length >= 3) slots[2] = takeBest(x => x.adjOps * 1.3 + x.adjAvg * 0.4);
        if (slots.length >= 2) slots[1] = takeBest(x => x.adjObp * 0.9 + x.adjAvg * 0.9);
        if (slots.length >= 5) slots[4] = takeBest(x => x.adjSlg + x.adjOps);
        if (slots.length >= 10) slots[slots.length - 1] = takeBest(x => x.adjObp * 1.2 + x.adjAvg * 0.4);
        for (let i = 0; i < slots.length; i++) if (!slots[i]) slots[i] = takeBest(x => x.adjOps);
        const extras = pool.map((x, idx) => ({{ ...x, order: slots.length + idx + 1, role: {{ lbl: "BE / Banca", cls: "" }} }}));
        return slots.filter(Boolean).map((x, idx) => ({{ ...x, order: idx + 1, role: roles[idx] || {{ lbl: "Bate", cls: "" }} }})).concat(extras);
      }}

      function buildDefensiveAlignment(availPlayers, topPitcherName) {{
        const POS_ORDER = ["P", "C", "SS", "2B", "SFI", "CF", "SFE", "1B", "3B", "LF", "RF"];
        const assigned = {{}};
        const used = new Set();
        const availNames = new Set(availPlayers.map(p => p.name));

        // 1. Overrides directos del selector del diamante
        for (const pos of POS_ORDER) {{
          if (customDefMap[pos] && availNames.has(customDefMap[pos]) && !used.has(customDefMap[pos])) {{
            assigned[pos] = customDefMap[pos];
            used.add(customDefMap[pos]);
          }}
        }}
        // 2. Pitcher recomendado
        if (!assigned["P"] && topPitcherName && availNames.has(topPitcherName) && !used.has(topPitcherName)) {{
          assigned["P"] = topPitcherName;
          used.add(topPitcherName);
        }}

        // 3. Puntaje priorizando POSICIONES FIJAS definidas por el coach (pos1 = +500, pos2 = +300) + experiencia real AL CAMPO
        const posScore = (p, pos) => {{
          let s = 10 + (p.defense.pdf || 0) * 10;
          if (p.fixed_pos1 === pos) s += 500;
          else if (p.fixed_pos2 === pos) s += 300;
          else if (p.fixed_pos3 === pos) s += 180;
          const hit = (p.positions || []).find(x => x.pos === pos);
          if (hit) s += 120 + (hit.ej || 0) * 3 + (hit.pdf || 0.85) * 40 + (hit.jj || 0) * 4;
          const prim = p.primary_pos;
          if (["LF","CF","RF","SFE"].includes(pos) && ["LF","CF","RF","SFE"].includes(prim)) s += 25;
          if (["2B","SS","3B","SFI"].includes(pos) && ["2B","SS","3B","SFI"].includes(prim)) s += 25;
          if (pos === "1B" && ["3B","C"].includes(prim)) s += 20;
          return s;
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
          CF:[210,26], LF:[66,70], SFE:[210,74], RF:[354,70],
          SFI:[210,122], SS:[122,158], "2B":[298,158],
          "3B":[96,214], P:[210,210], "1B":[324,214], C:[210,290]
        }};
        const nodes = Object.entries(coords).map(([pos, [x, y]]) => `
          <g transform="translate(${{x}},${{y}})">
            <rect x="-42" y="-14" width="84" height="28" rx="7" fill="#0e2644" stroke="#f0d72b" stroke-width="1.6" />
            <text x="0" y="-2" text-anchor="middle" fill="#f0d72b" font-size="9.5" font-weight="900" font-family="monospace">${{pos}}</text>
            <text x="0" y="10" text-anchor="middle" fill="#ffffff" font-size="10" font-weight="700" font-family="sans-serif">${{esc(shortName(defMap[pos]))}}</text>
          </g>
        `).join("");
        return `
          <svg class="diamond-svg" viewBox="0 0 420 315" xmlns="http://www.w3.org/2000/svg">
            <path d="M 20 190 Q 210 -25 400 190 L 210 305 Z" fill="#1e7e45" stroke="rgba(255,255,255,0.35)" stroke-width="2" />
            <polygon points="210,128 310,208 210,290 110,208" fill="#c28d57" opacity="0.92" stroke="#f8fafc" stroke-width="2" />
            <polygon points="210,152 280,208 210,264 140,208" fill="#166534" />
            <rect x="205" y="124" width="10" height="10" transform="rotate(45 210 129)" fill="#fff" />
            <rect x="305" y="203" width="10" height="10" transform="rotate(45 310 208)" fill="#fff" />
            <rect x="105" y="203" width="10" height="10" transform="rotate(45 110 208)" fill="#fff" />
            <polygon points="204,284 216,284 216,291 210,296 204,291" fill="#fff" />
            <circle cx="210" cy="210" r="14" fill="#c28d57" stroke="#fff" stroke-width="1" />
            ${{nodes}}
          </svg>
        `;
      }}

      function downloadPositionsCSV(roster, squadLabel) {{
        const header = "jugador,equipo,pos_primaria,pos_secundaria,pos_terciaria,es_pitcher,rol_pitcher";
        const lines = roster.map(p => {{
          const eq = p.dual_squad ? "A y B" : (squadLabel === "ALL" ? "A y B" : squadLabel);
          const p1 = p.fixed_pos1 || (p.primary_pos !== "UTIL" ? p.primary_pos : "");
          const p2 = p.fixed_pos2 || p.secondary_pos || "";
          const p3 = p.fixed_pos3 || "";
          const isP = p.is_pitcher ? "SI" : "NO";
          const rol = p.pitcher_role || "";
          return `"${{p.name.replace(/"/g, '""')}}","${{eq}}","${{p1}}","${{p2}}","${{p3}}","${{isP}}","${{rol}}"`;
        }});
        const csv = [header, ...lines].join("\\n");
        const blob = new Blob([csv], {{ type: "text/csv;charset=utf-8;" }});
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "posiciones_relampago.csv";
        a.click();
      }}

      function render() {{
        const squadViews = getViewsForSquad(activeSquad);
        if (!squadViews.some(v => v.id === activeViewId)) activeViewId = squadViews[0]?.id || data.view_index[0].id;
        const view = data.views[activeViewId];
        const k = view.our_kpis;
        const roster = enrichRosterWithLocal(view.relampago_roster || []);
        const rivals = view.rivals_profiles || [];
        if (!rivals.some(r => r.name === selectedRivalName)) selectedRivalName = rivals[0]?.name || "";
        const curRival = rivals.find(r => r.name === selectedRivalName) || null;
        const availPlayers = roster.filter(p => !unavailableSet.has(p.name));

        const pitcherRecs = recommendPitchers(availPlayers, curRival);
        const topPitcherName = pitcherRecs[0]?.player?.name || "";
        const lineup = buildOffensiveLineup(availPlayers);
        const defense = buildDefensiveAlignment(availPlayers, topPitcherName);
        const qSuffix = `?view=${{encodeURIComponent(activeViewId)}}`;

        // Filtrado de tablas completas de Relámpago
        const q = statsSearch.trim().toLowerCase();
        const filteredRoster = q ? roster.filter(p => [p.name, p.primary_pos, p.secondary_pos, p.pitcher_role].join(" ").toLowerCase().includes(q)) : roster;
        const pitchersTableList = filteredRoster.filter(p => p.is_pitcher || p.pitching.ip > 0).sort((a,b) => (a.pitching.ip > 0 ? a.pitching.efe : 99) - (b.pitching.ip > 0 ? b.pitching.efe : 99));
        const defTableList = [...filteredRoster].sort((a,b) => (b.defense.ej - a.defense.ej) || (b.defense.jj - a.defense.jj) || (b.defense.pdf - a.defense.pdf));

        let statsTableHtml = "";
        if (activeStatsTab === "bat") {{
          statsTableHtml = `
            <div class="tw"><table>
              <thead><tr><th>Jugador</th><th>Pos</th><th class="num">JJ</th><th class="num">VB</th><th class="num">H</th><th class="num">2B</th><th class="num">3B</th><th class="num">HR</th><th class="num">CI</th><th class="num">CA</th><th class="num">BB</th><th class="num">K</th><th class="num">AVG</th><th class="num">OBP</th><th class="num">SLG</th><th class="num">OPS</th></tr></thead>
              <tbody>
                ${{filteredRoster.map(p => {{
                  const b = p.batting;
                  return `<tr>
                    <td><strong>${{esc(p.name)}}</strong>${{p.dual_squad ? ' <span class="badge gold">A+B</span>' : ""}}</td>
                    <td><span class="pos-b">${{esc(p.primary_pos)}}</span></td>
                    <td class="num">${{b.jj}}</td><td class="num">${{b.vb}}</td><td class="num">${{b.h}}</td>
                    <td class="num">${{b.h2}}</td><td class="num">${{b.h3}}</td><td class="num"><strong>${{b.hr}}</strong></td>
                    <td class="num">${{b.ci}}</td><td class="num">${{b.ca}}</td><td class="num">${{b.bb}}</td><td class="num">${{b.k}}</td>
                    <td class="num"><strong>${{fmtRate(b.avg)}}</strong></td><td class="num">${{fmtRate(b.obp)}}</td>
                    <td class="num">${{fmtRate(b.slg)}}</td><td class="num"><strong>${{fmtRate(b.ops)}}</strong></td>
                  </tr>`;
                }}).join("") || `<tr><td colspan="16" class="center" style="color:var(--light)">Sin estadísticas de bateo aún.</td></tr>`}}
              </tbody>
            </table></div>`;
        }} else if (activeStatsTab === "pic") {{
          statsTableHtml = `
            <div class="tw"><table>
              <thead><tr><th>Pitcher</th><th>Rol</th><th class="num">JJ</th><th class="num">G–P</th><th class="num">S</th><th class="num">IP</th><th class="num">H</th><th class="num">CA</th><th class="num">CL</th><th class="num">BB</th><th class="num">K</th><th class="num">HR</th><th class="num">EFE</th><th class="num">WHIP</th></tr></thead>
              <tbody>
                ${{pitchersTableList.map(p => {{
                  const pc = p.pitching;
                  return `<tr>
                    <td><strong>${{esc(p.name)}}</strong>${{p.dual_squad ? ' <span class="badge gold">A+B</span>' : ""}}</td>
                    <td>${{esc(p.pitcher_role || (pc.ji > 0 ? "Abridor" : "Rotación"))}}</td>
                    <td class="num">${{pc.jj}}</td><td class="num"><strong>${{pc.g}}–${{pc.p}}</strong></td><td class="num">${{pc.s}}</td>
                    <td class="num">${{pc.ip.toFixed(1)}}</td><td class="num">${{pc.h}}</td><td class="num">${{pc.ca}}</td>
                    <td class="num">${{pc.cl}}</td><td class="num">${{pc.bb}}</td><td class="num">${{pc.k}}</td>
                    <td class="num">${{pc.hr}}</td><td class="num"><strong>${{pc.ip > 0 ? pc.efe.toFixed(2) : "—"}}</strong></td>
                    <td class="num"><strong>${{pc.ip > 0 ? pc.whip.toFixed(2) : "—"}}</strong></td>
                  </tr>`;
                }}).join("") || `<tr><td colspan="14" class="center" style="color:var(--light)">No hay pitchers registrados en esta vista. Usa "⚙️ Configurar Posiciones Fijas y Pitchers" arriba para marcar quiénes pichean.</td></tr>`}}
              </tbody>
            </table></div>`;
        }} else {{
          statsTableHtml = `
            <div class="tw"><table>
              <thead><tr><th>Jugador</th><th>Posición Fija</th><th>Posiciones Jugadas (AL CAMPO)</th><th class="num">JJ</th><th class="num">IJ/EJ</th><th class="num">PO</th><th class="num">AS</th><th class="num">E</th><th class="num">DP</th><th class="num">PDF</th></tr></thead>
              <tbody>
                ${{defTableList.map(p => {{
                  const d = p.defense;
                  const fixedTxt = p.fixed_pos1 ? `<span class="pos-b">${{esc(p.fixed_pos1)}}</span>${{p.fixed_pos2 ? ` <span class="badge">${{esc(p.fixed_pos2)}}</span>` : ""}}` : `<span style="color:var(--light);font-size:12px">Auto (${{esc(p.primary_pos)}})</span>`;
                  const playedTxt = (p.positions || []).map(x => `${{esc(x.pos)}} (${{x.ej}} EJ · ${{fmtRate(x.pdf)}})`).join(" · ") || "—";
                  return `<tr>
                    <td><strong>${{esc(p.name)}}</strong>${{p.dual_squad ? ' <span class="badge gold">A+B</span>' : ""}}</td>
                    <td>${{fixedTxt}}</td>
                    <td style="font-size:12px;color:var(--muted)">${{playedTxt}}</td>
                    <td class="num">${{d.jj}}</td><td class="num">${{d.ej.toFixed(1)}}</td>
                    <td class="num">${{d.po}}</td><td class="num">${{d.as}}</td>
                    <td class="num" style="color:${{d.e>=2?'var(--red)':'inherit'}}"><strong>${{d.e}}</strong></td>
                    <td class="num">${{d.dp}}</td><td class="num"><strong>${{(d.po + d.as + d.e) > 0 ? fmtRate(d.pdf) : "—"}}</strong></td>
                  </tr>`;
                }}).join("") || `<tr><td colspan="10" class="center" style="color:var(--light)">Sin datos defensivos aún.</td></tr>`}}
              </tbody>
            </table></div>`;
        }}

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

          <!-- ESTRATEGIA DE JUEGO -->
          <section class="section" id="sec-estrategia">
            <div class="sec-head">
              <div>
                <h2>🧠 Estrategia de Juego — Lineup Ofensivo, Defensivo y Pitcher</h2>
                <div class="sub">Define posiciones fijas, marca quién asiste hoy y elige al rival para armar tu alineación al instante</div>
              </div>
            </div>

            <div class="strat-controls">
              <label style="font-size:13px;font-weight:800;color:var(--navy)">🆚 Rival:</label>
              <select class="sel" id="rival-select">
                ${{rivals.map(r => `<option value="${{esc(r.name)}}" ${{r.name === selectedRivalName ? "selected" : ""}}>${{esc(r.name)}} (${{r.g}}–${{r.p}} · OPS ${{fmtRate(r.ops)}})</option>`).join("") || `<option value="">Sin rivales cargados</option>`}}
              </select>
              <button class="btn btn-gold" id="btn-toggle-editor">⚙️ ${{showPosEditor ? "Cerrar Editor de Posiciones" : "Configurar Posiciones Fijas y Pitchers"}}</button>
              <button class="btn" id="btn-reset-def">🔄 Resetear Campo</button>
              <button class="btn btn-green" id="btn-copy-wa" style="margin-left:auto">📋 Copiar para WhatsApp</button>
            </div>

            ${{showPosEditor ? `
              <div class="editor-panel">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px">
                  <div>
                    <h3>⚙️ Editor de Posiciones Fijas y Pitchers de Relámpago</h3>
                    <div style="font-size:12px;color:var(--muted)">Los cambios se aplican en vivo aquí. Cuando termines, haz clic en <strong>Descargar CSV</strong> y sube <code>posiciones_relampago.csv</code> a tu repositorio en GitHub para que quede guardado permanentemente para todo el equipo.</div>
                  </div>
                  <button class="btn btn-green" id="btn-dl-csv">💾 Descargar posiciones_relampago.csv</button>
                </div>
                <div class="tw"><table>
                  <thead><tr><th>Jugador</th><th>Posición Fija #1</th><th>Posición #2</th><th>¿Es Pitcher?</th><th>Rol de Pitcheo</th></tr></thead>
                  <tbody>
                    ${{roster.map(p => `
                      <tr>
                        <td><strong>${{esc(p.name)}}</strong></td>
                        <td><select class="ed-sel" data-ed-p1="${{esc(p.name)}}">${{ALL_POS.map(pos => `<option value="${{pos}}" ${{p.fixed_pos1 === pos ? "selected" : ""}}>${{pos || "Auto (" + p.primary_pos + ")"}}</option>`).join("")}}</select></td>
                        <td><select class="ed-sel" data-ed-p2="${{esc(p.name)}}">${{ALL_POS.map(pos => `<option value="${{pos}}" ${{p.fixed_pos2 === pos ? "selected" : ""}}>${{pos || "—"}}</option>`).join("")}}</select></td>
                        <td><input type="checkbox" data-ed-pic="${{esc(p.name)}}" ${{p.is_pitcher ? "checked" : ""}} /> Sí</td>
                        <td><select class="ed-sel" data-ed-role="${{esc(p.name)}}"><option value="">—</option><option value="Abridor" ${{p.pitcher_role==="Abridor"?"selected":""}}>Abridor</option><option value="Relevo" ${{p.pitcher_role==="Relevo"?"selected":""}}>Relevo</option><option value="Cerrador" ${{p.pitcher_role==="Cerrador"?"selected":""}}>Cerrador</option></select></td>
                      </tr>
                    `).join("")}}
                  </tbody>
                </table></div>
              </div>
            ` : ""}}

            <div class="avail-box">
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                <strong style="font-size:13px;color:var(--navy)">✅ Jugadores disponibles hoy (${{availPlayers.length}} de ${{roster.length}}) — clic para activar/desactivar:</strong>
                <button class="btn" id="btn-all-on" style="padding:4px 9px;font-size:11.5px">Marcar todos</button>
              </div>
              <div class="avail-grid" id="avail-grid">
                ${{roster.map(p => {{
                  const on = !unavailableSet.has(p.name);
                  return `<span class="avail-chip ${{on ? "on" : ""}}" data-pname="${{esc(p.name)}}">${{on ? "✓" : "✕"}} ${{esc(p.name)}} <span style="opacity:.78;font-size:11px">(${{esc(p.primary_pos)}})</span>${{p.dual_squad ? ' <span class="dual">A+B</span>' : ""}}</span>`;
                }}).join("") || `<span style="color:var(--light);font-size:12.5px">Aún no hay jugadores registrados en este torneo.</span>`}}
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

            <div class="subcard" style="margin-bottom:18px">
              <h3>⚾ Recomendación de Pitcheo vs ${{esc(curRival ? curRival.name : "Rival")}}</h3>
              ${{pitcherRecs.length ? pitcherRecs.slice(0, 3).map((rec, idx) => {{
                const pc = rec.player.pitching;
                const label = idx === 0 ? "⭐ Abridor Recomendado" : (idx === 1 ? "🔁 Relevo Principal" : "🛡️ Opción #3");
                return `
                  <div class="pitcher-card ${{idx === 0 ? "best" : ""}}">
                    <div class="pitcher-top">
                      <div><strong>${{esc(rec.player.name)}}</strong> <span class="badge ${{idx === 0 ? "ok" : ""}}">${{label}}</span></div>
                      <div style="font-family:var(--mono);font-size:12.5px;font-weight:800;color:var(--navy)">${{pc.ip > 0 ? `EFE ${{pc.efe.toFixed(2)}} · WHIP ${{pc.whip.toFixed(2)}} · ${{pc.ip.toFixed(1)}} IP (${{pc.g}}–${{pc.p}})` : "Sin innings en este torneo"}}</div>
                    </div>
                    <div style="font-size:12.5px;color:var(--muted)">${{esc(rec.reason)}}${{pc.ip > 0 ? ` · K: ${{pc.k}} · BB: ${{pc.bb}} · HR: ${{pc.hr}}` : ""}}</div>
                  </div>
                `;
              }}).join("") : `<p style="font-size:13px;color:var(--light)">No hay pitchers marcados ni con innings en esta vista. Haz clic arriba en <strong>⚙️ Configurar Posiciones Fijas y Pitchers</strong> para indicar quiénes lanzan.</p>`}}
            </div>

            <div class="three-col">
              <div class="subcard">
                <h3>🏏 Lineup Ofensivo Sugerido (1° al 11°) <span style="font-size:11.5px;color:var(--light);font-weight:600">OBP / SLG / OPS</span></h3>
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
                }}).join("") || `<p style="font-size:13px;color:var(--light)">Activa jugadores disponibles arriba.</p>`}}
              </div>

              <div class="subcard">
                <h3>🧤 Alineación Defensiva Sugerida (Campo) <span style="font-size:11.5px;color:var(--light);font-weight:600">Respeta posiciones fijas</span></h3>
                <div class="diamond-wrap">${{renderDiamondSVG(defense.map)}}</div>
                <div class="def-list">
                  ${{defense.order.map(pos => `
                    <div class="def-slot">
                      <span class="pos-b">${{pos}}</span>
                      <select class="def-sel" data-def-pos="${{pos}}">
                        <option value="Por definir">— Por definir —</option>
                        ${{availPlayers.map(p => {{
                          const hit = (p.positions || []).find(x => x.pos === pos);
                          const tag = p.fixed_pos1 === pos ? " ★Fija" : (hit ? ` (${{hit.ej}} EJ · ${{fmtRate(hit.pdf)}})` : ` (${{p.primary_pos}})`);
                          return `<option value="${{esc(p.name)}}" ${{defense.map[pos] === p.name ? "selected" : ""}}>${{esc(p.name)}}${{tag}}</option>`;
                        }}).join("")}}
                      </select>
                    </div>
                  `).join("")}}
                </div>
              </div>
            </div>
          </section>

          <!-- ESTADÍSTICAS COMPLETAS DE RELÁMPAGO (BATEO, PITCHEO Y DEFENSIVA) -->
          <section class="section" id="sec-stats-relampago">
            <div class="sec-head">
              <div>
                <h2>📊 Estadísticas Completas de Relámpago — ${{esc(view.label)}}</h2>
                <div class="sub">Consulta Bateo, Pitcheo y Defensiva / Posiciones directamente aquí</div>
              </div>
              <input class="search-in" id="stats-search" type="text" value="${{esc(statsSearch)}}" placeholder="Buscar jugador o posición..." />
            </div>
            <div class="stats-tabs" id="stats-tabs">
              <button class="stab ${{activeStatsTab==="bat"?"active":""}}" data-st="bat">🏏 Bateo (${{roster.length}})</button>
              <button class="stab ${{activeStatsTab==="pic"?"active":""}}" data-st="pic">⚾ Pitcheo (${{pitchersTableList.length}})</button>
              <button class="stab ${{activeStatsTab==="def"?"active":""}}" data-st="def">🧤 Defensiva &amp; Posiciones (${{defTableList.length}})</button>
            </div>
            ${{statsTableHtml}}
          </section>

          <!-- TABLAS DE POSICIONES -->
          ${{view.standings_blocks.length ? `
            <section class="section" id="sec-tablas">
              <div class="sec-head"><div><h2>🏆 Tabla de Posiciones — ${{esc(view.label)}}</h2><div class="sub">Haz clic en cualquier rival para ver su reporte completo</div></div></div>
              ${{view.standings_blocks.map(blk => `
                <h3 style="font-size:14.5px;color:var(--navy);margin:12px 0 8px">${{esc(blk.phase)}}</h3>
                <div class="tw" style="margin-bottom:14px">
                  <table>
                    <thead><tr><th class="center">Pos</th><th>Equipo</th><th class="num">J</th><th class="num">G</th><th class="num">P</th><th class="num">E</th><th class="num">CA</th><th class="num">CP</th><th class="num">DF</th><th class="num">AVG</th><th class="num">Pts</th></tr></thead>
                    <tbody>
                      ${{blk.rows.map(r => {{
                        const isOurs = r.team.toLowerCase().includes("relampago") || r.team.toLowerCase().includes("relámpago");
                        return `<tr class="${{isOurs ? "own" : ""}}"><td class="center">${{r.pos}}</td><td><a href="equipos/${{r.slug}}.html${{qSuffix}}">${{esc(r.team)}}</a>${{isOurs ? ' <span class="badge gold">Nosotros</span>' : ""}}</td><td class="num">${{r.j}}</td><td class="num"><strong>${{r.g}}</strong></td><td class="num">${{r.p}}</td><td class="num">${{r.e}}</td><td class="num">${{r.ca}}</td><td class="num">${{r.cp}}</td><td class="num">${{r.df >= 0 ? "+" : ""}}${{r.df}}</td><td class="num">${{fmtRate(r.avg)}}</td><td class="num"><strong>${{r.pts}}</strong></td></tr>`;
                      }}).join("")}}
                    </tbody>
                  </table>
                </div>
              `).join("")}}
            </section>
          ` : ""}}

          <!-- SCOUTING DE EQUIPOS -->
          <section class="section" id="sec-rivales">
            <div class="sec-head"><div><h2>🎯 Scouting de Equipos — ${{esc(view.label)}}</h2><div class="sub">Abre cualquier equipo para ver sus bates peligrosos, pitcheo y defensa</div></div></div>
            <div class="cards-grid">
              ${{view.teams.map(t => `
                <a class="t-card ${{t.is_ours ? "own" : ""}}" href="equipos/${{t.slug}}.html${{qSuffix}}">
                  <div class="tc-top">
                    <div class="tc-name">${{esc(t.name)}}</div>
                    <span class="badge ${{t.is_ours ? "" : (t.team_bat.ops >= 0.900 ? "danger" : "ok")}}">${{t.g}}–${{t.p}}${{t.e ? "–" + t.e : ""}}</span>
                  </div>
                  <div style="font-size:12px;color:var(--muted);margin-bottom:6px">${{t.is_ours ? "⚡ Nuestro equipo" : `Perfil: <strong>${{esc(t.profile.style)}}</strong>`}}</div>
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

        // Wire Listeners
        document.querySelectorAll("#squad-pills .pill-btn").forEach(b => b.addEventListener("click", () => {{
          activeSquad = b.dataset.sq; activeViewId = getViewsForSquad(activeSquad)[0]?.id || activeViewId; customDefMap = {{}}; render();
        }}));
        document.querySelectorAll("#view-pills .pill-btn").forEach(b => b.addEventListener("click", () => {{
          activeViewId = b.dataset.vid; customDefMap = {{}}; render();
        }}));
        document.getElementById("rival-select").addEventListener("change", (e) => {{ selectedRivalName = e.target.value; render(); }});
        document.getElementById("btn-toggle-editor").addEventListener("click", () => {{ showPosEditor = !showPosEditor; render(); }});
        document.getElementById("btn-reset-def").addEventListener("click", () => {{ customDefMap = {{}}; render(); }});
        document.getElementById("btn-all-on").addEventListener("click", () => {{ unavailableSet.clear(); render(); }});
        document.querySelectorAll("#avail-grid .avail-chip").forEach(ch => ch.addEventListener("click", () => {{
          const pn = ch.dataset.pname; if (unavailableSet.has(pn)) unavailableSet.delete(pn); else unavailableSet.add(pn); render();
        }}));
        document.querySelectorAll("[data-def-pos]").forEach(sel => sel.addEventListener("change", (e) => {{
          customDefMap[e.target.dataset.defPos] = e.target.value; render();
        }}));
        document.querySelectorAll("#stats-tabs .stab").forEach(b => b.addEventListener("click", () => {{
          activeStatsTab = b.dataset.st; render();
        }}));
        document.getElementById("stats-search").addEventListener("input", (e) => {{ statsSearch = e.target.value; render(); }});

        // Position Editor Listeners
        if (showPosEditor) {{
          const ensureOv = (nm) => {{ if (!localPosOverrides[nm]) localPosOverrides[nm] = {{}}; return localPosOverrides[nm]; }};
          document.querySelectorAll("[data-ed-p1]").forEach(s => s.addEventListener("change", (e) => {{
            ensureOv(e.target.dataset.edP1).pos1 = e.target.value; saveLocalOverrides(); render();
          }}));
          document.querySelectorAll("[data-ed-p2]").forEach(s => s.addEventListener("change", (e) => {{
            ensureOv(e.target.dataset.edP2).pos2 = e.target.value; saveLocalOverrides(); render();
          }}));
          document.querySelectorAll("[data-ed-pic]").forEach(c => c.addEventListener("change", (e) => {{
            ensureOv(e.target.dataset.edPic).is_pitcher = e.target.checked; saveLocalOverrides(); render();
          }}));
          document.querySelectorAll("[data-ed-role]").forEach(s => s.addEventListener("change", (e) => {{
            ensureOv(e.target.dataset.edRole).pitcher_role = e.target.value; saveLocalOverrides(); render();
          }}));
          document.getElementById("btn-dl-csv").addEventListener("click", () => downloadPositionsCSV(roster, view.squad));
        }}

        document.getElementById("btn-copy-wa").addEventListener("click", () => {{
          const lines = [
            `⚡ *RELÁMPAGO DEL CARIBE (${{view.label}})* — ¡CACHAM!`,
            `🆚 *Rival:* ${{curRival ? curRival.name : "Por definir"}}`,
            `⚾ *Pitcher sugerido:* ${{topPitcherName || "Por definir"}}`,
            "",
            "*🏏 LINEUP OFENSIVO:*",
            ...lineup.slice(0, 11).map(s => `${{s.order}}. ${{s.p.name}} (${{s.role.lbl}} · AVG ${{fmtRate(s.p.batting.avg)}})`),
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

          ${{keys.length > 1 ? `<div class="pills" id="vpills">${{keys.map(k => `<button class="pbtn ${{k===activeV?"active":""}}" data-vk="${{esc(k)}}">${{esc(data.by_view[k].view_label)}}</button>`).join("")}}</div>` : ""}}

          <section class="sec">
            <h2>⚡ Lo esencial en 30 segundos</h2>
            <div class="ins-grid">
              <div class="ins gold"><div class="ins-k">Perfil ofensivo</div><div class="ins-h">${{esc(v.profile.style)}}</div><div class="ins-b">${{esc(v.profile.desc)}}</div></div>
              <div class="ins danger"><div class="ins-k">Bate #1 a cuidar</div><div class="ins-h">${{bestBat ? esc(bestBat.name) : "Sin datos"}}</div><div class="ins-b">${{bestBat ? `AVG ${{fmtRate(bestBat.avg)}} · OPS ${{fmtRate(bestBat.ops)}} · ${{bestBat.hr}} HR · ${{bestBat.ci}} CI en ${{bestBat.vb}} VB.` : "Sin turnos registrados."}}</div></div>
              <div class="ins"><div class="ins-k">Pitcheo y Defensa</div><div class="ins-h">${{bestPic ? `Abridor: ${{esc(bestPic.name)}}` : "Sin pitchers"}}</div><div class="ins-b">${{bestPic ? `EFE ${{bestPic.efe.toFixed(2)}} · WHIP ${{bestPic.whip.toFixed(2)}} (${{bestPic.ip}} IP).` : ""}} ${{mostErr && mostErr.e > 0 ? `Defensa: ${{td.e}} errores (${{esc(mostErr.name)}} acumula ${{mostErr.e}} E).` : `PDF colectivo: ${{fmtRate(td.pdf)}}.`}}</div></div>
            </div>
          </section>

          <section class="sec">
            <h2>🏏 Estadísticas de Bateo (${{v.batting.length}} jugadores)</h2>
            <div class="tw"><table>
              <thead><tr><th>Jugador</th><th class="num">JJ</th><th class="num">VB</th><th class="num">H</th><th class="num">2B</th><th class="num">3B</th><th class="num">HR</th><th class="num">CI</th><th class="num">CA</th><th class="num">BB</th><th class="num">K</th><th class="num">AVG</th><th class="num">OBP</th><th class="num">SLG</th><th class="num">OPS</th></tr></thead>
              <tbody>
                ${{v.batting.map(b => `<tr><td><strong>${{esc(b.name)}}</strong>${{b.ops >= 1.000 && b.vb >= 5 ? ' <span class="tag tag-r">Peligro</span>' : ""}}</td><td class="num">${{b.jj}}</td><td class="num">${{b.vb}}</td><td class="num">${{b.h}}</td><td class="num">${{b.h2}}</td><td class="num">${{b.h3}}</td><td class="num"><strong>${{b.hr}}</strong></td><td class="num">${{b.ci}}</td><td class="num">${{b.ca}}</td><td class="num">${{b.bb}}</td><td class="num">${{b.k}}</td><td class="num"><strong>${{fmtRate(b.avg)}}</strong></td><td class="num">${{fmtRate(b.obp)}}</td><td class="num">${{fmtRate(b.slg)}}</td><td class="num"><strong>${{fmtRate(b.ops)}}</strong></td></tr>`).join("") || `<tr><td colspan="15" style="text-align:center;color:var(--light)">Sin bateo registrado aún.</td></tr>`}}
              </tbody>
            </table></div>
          </section>

          <section class="sec">
            <h2>⚾ Pitcheo (${{v.pitching.length}}) &amp; 🧤 Defensiva (${{v.defense.length}})</h2>
            <div class="tw" style="margin-bottom:16px"><table>
              <thead><tr><th>Pitcher</th><th class="num">JJ</th><th class="num">G–P</th><th class="num">IP</th><th class="num">H</th><th class="num">CL</th><th class="num">BB</th><th class="num">K</th><th class="num">HR</th><th class="num">EFE</th><th class="num">WHIP</th></tr></thead>
              <tbody>
                ${{v.pitching.map(p => `<tr><td><strong>${{esc(p.name)}}</strong></td><td class="num">${{p.jj}}</td><td class="num">${{p.g}}–${{p.p}}</td><td class="num">${{p.ip.toFixed(1)}}</td><td class="num">${{p.h}}</td><td class="num">${{p.cl}}</td><td class="num">${{p.bb}}</td><td class="num">${{p.k}}</td><td class="num">${{p.hr}}</td><td class="num"><strong>${{p.efe.toFixed(2)}}</strong></td><td class="num"><strong>${{p.whip.toFixed(2)}}</strong></td></tr>`).join("") || `<tr><td colspan="11" style="text-align:center;color:var(--light)">Sin pitcheo registrado aún.</td></tr>`}}
              </tbody>
            </table></div>
            <div class="tw"><table>
              <thead><tr><th>Defensor</th><th class="num">JJ</th><th class="num">IJ/EJ</th><th class="num">PO</th><th class="num">AS</th><th class="num">E</th><th class="num">DP</th><th class="num">PDF</th></tr></thead>
              <tbody>
                ${{v.defense.map(d => `<tr><td><strong>${{esc(d.name)}}</strong>${{d.e >= 3 ? ' <span class="tag tag-y">Atacar</span>' : ""}}</td><td class="num">${{d.jj}}</td><td class="num">${{d.ej.toFixed(1)}}</td><td class="num">${{d.po}}</td><td class="num">${{d.as}}</td><td class="num" style="color:${{d.e>=2?'var(--red)':'inherit'}}"><strong>${{d.e}}</strong></td><td class="num">${{d.dp}}</td><td class="num"><strong>${{fmtRate(d.pdf)}}</strong></td></tr>`).join("") || `<tr><td colspan="8" style="text-align:center;color:var(--light)">Sin defensiva registrada aún.</td></tr>`}}
              </tbody>
            </table></div>
          </section>

          <section class="sec">
            <h2>📅 Historial de Juegos (${{v.games.length}})</h2>
            <div class="tw"><table>
              <thead><tr><th>Res</th><th>Fecha</th><th>Torneo</th><th>Condición</th><th>Rival</th><th class="num">Marcador</th></tr></thead>
              <tbody>
                ${{v.games.map(g => `<tr><td><span class="res-b ${{g.result}}">${{g.result}}</span></td><td>${{esc(g.date)}}</td><td>${{esc(g.tournament)}}</td><td>${{esc(g.venue)}}</td><td><strong>${{esc(g.opponent)}}</strong></td><td class="num"><strong>${{g.score_for}} – ${{g.score_against}}</strong></td></tr>`).join("") || `<tr><td colspan="6" style="text-align:center;color:var(--light)">Sin juegos registrados en esta vista.</td></tr>`}}
              </tbody>
            </table></div>
          </section>
        `;
        document.querySelectorAll("#vpills .pbtn").forEach(b => b.addEventListener("click", () => {{ activeV = b.dataset.vk; render(); }}));
      }}
      render();
    }})(TDATA);
  </script>
</body>
</html>"""


def build_demo_snapshot() -> Dict[str, Any]:
    return {
        "extracted_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "league_id": 174,
        "league_name": "Liga de Softbol VENEZUELA-UNIMET",
        "tournaments": [
            {
                "cam_id": "3095", "number": 89, "name": "Torneo 89 Lanz Lento", "squad": "A",
                "standings_blocks": [{"phase": "Eliminatoria", "rows": [
                    {"pos": 1, "equ_id": "101", "team": "Mets de Polar", "j": 5, "g": 5, "p": 0, "e": 0, "ca": 42, "cp": 5, "df": 37, "avg": 1.0, "pts": 15},
                    {"pos": 2, "equ_id": "102", "team": "Relampago del Caribe", "j": 7, "g": 4, "p": 2, "e": 1, "ca": 29, "cp": 24, "df": 5, "avg": 0.571, "pts": 13},
                ]}],
                "games": [],
                "teams": {
                    "Relampago del Caribe": {
                        "equ_id": "102", "name": "Relampago del Caribe", "is_ours": True, "roster": [],
                        "batting": [
                            {"jug_id": "374108", "name": "Leonardo Machin", "jj": 6, "vb": 16, "al": 18, "ca": 5, "h": 9, "h2": 2, "h3": 0, "hr": 0, "ci": 4, "bb": 2, "k": 0, "br": 1, "sf": 0, "gp": 0, "avg": 0.563, "obp": 0.611, "slg": 0.688, "ops": 1.299},
                            {"jug_id": "5", "name": "Andres Silva", "jj": 7, "vb": 17, "al": 19, "ca": 4, "h": 6, "h2": 0, "h3": 0, "hr": 0, "ci": 2, "bb": 2, "k": 1, "br": 0, "sf": 0, "gp": 0, "avg": 0.353, "obp": 0.421, "slg": 0.353, "ops": 0.774},
                        ],
                        # Probar con est=pic y est=def VACÍOS para verificar el respaldo desde relampago_player_details!
                        "pitching": [],
                        "defense": [],
                    },
                    "Mets de Polar": {"equ_id": "101", "name": "Mets de Polar", "is_ours": False, "batting": [], "pitching": [], "defense": []},
                },
                "relampago_player_details": {
                    "374108": {"jug_id": "374108", "name": "Leonardo Machin", "positions": [{"pos": "2B", "jj": 6, "po": 5, "as": 12, "e": 1, "dp": 2, "ej": 36.0, "pdf": 0.944}], "pitching_backup": None},
                    "5": {"jug_id": "5", "name": "Andres Silva", "positions": [{"pos": "P", "jj": 5, "po": 2, "as": 9, "e": 0, "dp": 1, "ej": 24.0, "pdf": 1.000}], "pitching_backup": {"jj": 5, "ji": 4, "g": 3, "p": 1, "s": 0, "ip": 24.0, "ip_real": 24.0, "h": 26, "ca": 14, "cl": 11, "bb": 5, "k": 9, "hr": 1, "efe": 3.21, "whip": 1.29}},
                },
            }
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compila el portal de scouting Relámpago Softbol v2.")
    parser.add_argument("--config", default="config_softbol.json", type=Path)
    parser.add_argument("--snapshot", default="data/softbol_snapshot.json", type=Path)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    snapshot = build_demo_snapshot() if args.demo else json.loads(args.snapshot.read_text(encoding="utf-8"))
    alias_map = build_alias_map(cfg)
    manual_pos = load_manual_positions(cfg, alias_map)

    out_dir = Path(cfg.get("output_dir", "docs"))
    teams_dir = out_dir / "equipos"
    teams_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    # Garantizar logo siempre presente en docs/logo_relampago.png
    ensure_logo_in_docs(cfg, out_dir)

    tournaments = snapshot.get("tournaments", [])
    if not tournaments:
        print("[WARN] No hay torneos en el snapshot.")
        return

    players_in_a, players_in_b = set(), set()
    our_kw = norm_text(cfg.get("our_team_keyword", "Relampago"))
    for t in tournaments:
        sq = t.get("squad", "A")
        for tname, tdata in t.get("teams", {}).items():
            if tdata.get("is_ours") or our_kw in norm_text(tname):
                for lst in (tdata.get("roster", []), tdata.get("batting", []), tdata.get("pitching", []), tdata.get("defense", [])):
                    for p in lst:
                        ck, _ = canonical_player_key_and_name(p["name"], alias_map)
                        if ck:
                            (players_in_a if sq == "A" else players_in_b).add(ck)
    dual_squad_players = players_in_a & players_in_b

    views: Dict[str, Dict[str, Any]] = {}
    view_index: List[Dict[str, str]] = []

    for t in tournaments:
        vid = f"t{t['number']}_{t['cam_id']}"
        lbl = f"Torneo {t['number']} · Equipo {t['squad']}" if t.get("number") else f"{t['name']} (Eq. {t['squad']})"
        views[vid] = build_view_for_tournaments(vid, lbl, t["squad"], [t], dual_squad_players, manual_pos, alias_map, cfg)
        view_index.append({"id": vid, "label": lbl, "squad": t["squad"]})

    t_a = [t for t in tournaments if t.get("squad") == "A"]
    if len(t_a) > 1:
        views["hist_A"] = build_view_for_tournaments("hist_A", f"Histórico Equipo A ({len(t_a)} torneos)", "A", t_a, dual_squad_players, manual_pos, alias_map, cfg)
        view_index.append({"id": "hist_A", "label": f"Histórico Equipo A ({len(t_a)} torneos)", "squad": "A"})

    t_b = [t for t in tournaments if t.get("squad") == "B"]
    if len(t_b) > 1:
        views["hist_B"] = build_view_for_tournaments("hist_B", f"Histórico Equipo B ({len(t_b)} torneos)", "B", t_b, dual_squad_players, manual_pos, alias_map, cfg)
        view_index.append({"id": "hist_B", "label": f"Histórico Equipo B ({len(t_b)} torneos)", "squad": "B"})

    if len(tournaments) > 1:
        views["hist_ALL"] = build_view_for_tournaments("hist_ALL", f"Histórico Global A + B ({len(tournaments)} torneos)", "ALL", tournaments, dual_squad_players, manual_pos, alias_map, cfg)
        view_index.append({"id": "hist_ALL", "label": f"Histórico Global A + B ({len(tournaments)} torneos)", "squad": "ALL"})

    default_squad = "A" if any(v["squad"] == "A" for v in view_index) else view_index[0]["squad"]
    default_view_id = next((v["id"] for v in view_index if v["squad"] == default_squad), view_index[0]["id"])

    for v_obj in views.values():
        for blk in v_obj.get("standings_blocks", []):
            for row in blk.get("rows", []):
                row["slug"] = slugify(row["team"])

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
        (teams_dir / f"{sl}.html").write_text(render_team_report({"team_name": team_real_name[sl], "updated_at": snapshot["extracted_at"], "by_view": by_v}), encoding="utf-8")

    views_for_index = {}
    for vid, v_obj in views.items():
        compact_teams = [{k: t[k] for k in ("name", "slug", "is_ours", "j", "g", "p", "e", "ca", "cp", "df", "pts", "team_bat", "team_pic", "profile")} for t in v_obj["teams"]]
        views_for_index[vid] = {
            "id": v_obj["id"], "label": v_obj["label"], "squad": v_obj["squad"],
            "our_kpis": v_obj["our_kpis"], "standings_blocks": v_obj["standings_blocks"],
            "relampago_roster": v_obj["relampago_roster"], "rivals_profiles": v_obj["rivals_profiles"],
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
    print(f"[OK] Portal Softbol v2 generado en {out_dir}/index.html ({len(team_views_map)} equipos, {len(views)} vistas).")


if __name__ == "__main__":
    main()
