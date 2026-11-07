"""
Actualiza data/rankings.json con los rankings oficiales de ufc.com/rankings.

Si la descarga falla o la página cambia de formato, NO toca el archivo: el juego sigue
con los rankings anteriores y el workflow deja un aviso en GitHub Actions.

Uso:
  python scripts/update_rankings.py                       # descarga de ufc.com
  python scripts/update_rankings.py --html pagina.html    # usa un HTML guardado (para probar)
"""

import argparse
import json
import pathlib
import re
import sys
from datetime import date

URL = "https://www.ufc.com/rankings"
EXPECTED = ["Flyweight", "Bantamweight", "Featherweight", "Lightweight", "Welterweight", "Middleweight",
            "Light Heavyweight", "Heavyweight", "Women's Strawweight", "Women's Flyweight", "Women's Bantamweight"]
ORDER = ["Heavyweight", "Light Heavyweight", "Middleweight", "Welterweight", "Lightweight", "Featherweight",
         "Bantamweight", "Flyweight", "Women's Strawweight", "Women's Flyweight", "Women's Bantamweight"]


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").replace("’", "'").strip()


def warn(msg: str) -> None:
    # Formato que GitHub Actions muestra como aviso amarillo en el resumen del workflow
    print(f"::warning::{msg}")


def download() -> str:
    import requests
    resp = requests.get(URL, timeout=60, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    resp.raise_for_status()
    return resp.text


def parse(html: str) -> dict[str, list[str]]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for group in soup.select("div.view-grouping"):
        header = group.select_one(".view-grouping-header")
        if not header:
            continue
        div = clean(header.get_text())
        if div not in EXPECTED:  # descarta pound-for-pound y cualquier otra tabla
            continue
        champ = group.select_one(".rankings--athlete--champion h5 a") or group.select_one(".rankings--athlete--champion h5")
        champ_name = clean(champ.get_text()) if champ else ""
        if champ_name.lower() in ("vacant", "vacante"):
            champ_name = ""
        ranked = [clean(a.get_text()) for a in group.select("tbody tr td.views-field-title a")]
        if not ranked:
            ranked = [clean(td.get_text()) for td in group.select("tbody tr td.views-field-title")]
        out[div] = [champ_name] + [n for n in ranked if n][:15]
    return out


def validate(parsed: dict[str, list[str]]) -> list[str]:
    problems = []
    for div in EXPECTED:
        names = parsed.get(div)
        if not names:
            problems.append(f"falta la división {div}")
        elif len(names) < 15:
            problems.append(f"{div} solo tiene {len(names) - 1} rankeados")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="data/rankings.json")
    ap.add_argument("--html", help="leer un HTML guardado en vez de descargar")
    args = ap.parse_args()
    path = pathlib.Path(args.file)
    current = json.loads(path.read_text("utf-8"))

    try:
        html = pathlib.Path(args.html).read_text("utf-8") if args.html else download()
    except Exception as exc:  # sin internet, bloqueo, error del servidor…
        warn(f"No se pudieron descargar los rankings ({exc}). Se mantienen los del {current.get('updated')}.")
        return

    parsed = parse(html)
    problems = validate(parsed)
    if problems:
        warn("La página de rankings no tiene el formato esperado (" + "; ".join(problems[:3]) +
             f"). Se mantienen los del {current.get('updated')}.")
        return

    new_divs = {div: parsed[div] for div in ORDER}
    old_divs = current.get("divisions", {})
    changes = []
    for div in ORDER:
        old, new = old_divs.get(div, []), new_divs[div]
        if old != new:
            entered = [n for n in new if n and n not in old]
            left = [n for n in old if n and n not in new]
            detail = []
            if old[:1] != new[:1]:
                detail.append(f"campeón: {new[0] or 'vacante'}")
            if entered:
                detail.append("entran " + ", ".join(entered))
            if left:
                detail.append("salen " + ", ".join(left))
            changes.append(f"  {div}: " + ("; ".join(detail) or "cambia el orden"))

    if not changes:
        print("Rankings sin cambios.")
        return

    current["divisions"] = new_divs
    current["updated"] = date.today().isoformat()
    current["source"] = "ufc.com/rankings (ranking oficial de medios de UFC)"
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print("Rankings actualizados:\n" + "\n".join(changes))


if __name__ == "__main__":
    sys.exit(main())
