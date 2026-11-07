"""
Construye game_data.json para "Seis Grados del Octágono".

Fuente: el dataset público github.com/Greco1899/scrape_ufc_stats, que publica en CSV
los datos de UFCStats.com y se actualiza después de cada evento. Así no hace falta
descargar UFCStats directamente (el sitio bloquea a los clientes automatizados).

Uso:
  pip install requests
  python scripts/build_game_data.py                  # descarga los CSV más recientes y genera data/game_data.json
  python scripts/build_game_data.py --local carpeta  # usa CSV que ya tengas descargados en esa carpeta
  python scripts/build_game_data.py --check "Darren Till" "Tyron Woodley"

  python scripts/build_game_data.py --rankings data/rankings.json --out web/data/game_data.json

En GitHub, el workflow .github/workflows/actualizar.yml corre esto automáticamente.
"""

import argparse
import csv
import io
import json
import pathlib
import re
import sys
import unicodedata
from collections import Counter, defaultdict, deque
from datetime import date, datetime

RAW = "https://raw.githubusercontent.com/Greco1899/scrape_ufc_stats/main/"
FILES = ["ufc_event_details.csv", "ufc_fight_results.csv", "ufc_fighter_details.csv"]

METHODS = {  # método original -> código corto que usa el juego
    "KO/TKO": "KO", "TKO - Doctor's Stoppage": "TKO-M", "Submission": "SUB",
    "Decision - Unanimous": "DEC-U", "Decision - Split": "DEC-D", "Decision - Majority": "DEC-M",
    "DQ": "DQ", "Overturned": "NC", "Could Not Continue": "CNC", "Other": "OTRO",
}


def load_csvs(local: str | None) -> dict[str, list[dict]]:
    data = {}
    for name in FILES:
        if local:
            text = (pathlib.Path(local) / name).read_text("utf-8")
        else:
            import requests
            resp = requests.get(RAW + name, timeout=60)
            resp.raise_for_status()
            text = resp.content.decode("utf-8")
        data[name] = list(csv.DictReader(io.StringIO(text)))
        print(f"  {name}: {len(data[name])} filas")
    return data


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def load_rankings(path: str, fighters: list[str]) -> dict | None:
    """Une rankings.json con los peleadores de la base. Devuelve índices por división."""
    p = pathlib.Path(path)
    if not p.exists():
        print(f"(Sin {path}: el modo Rankeados quedará desactivado)")
        return None
    r = json.loads(p.read_text("utf-8"))
    aliases = r.get("aliases", {})
    exact = {norm(n): i for i, n in enumerate(fighters)}
    by_tokens = defaultdict(list)  # "Weili Zhang" == "Zhang Weili"
    for i, n in enumerate(fighters):
        by_tokens[" ".join(sorted(norm(n).split()))].append(i)

    divisions, missing = [], []
    for div, names in r["divisions"].items():
        ids = []
        for name in names:
            target = aliases.get(name, name)
            key = norm(target)
            i = exact.get(key)
            if i is None:
                i = exact.get(norm(f"{target} ({div})"))  # nombre repetido separado por división
            if i is None:
                cands = by_tokens.get(" ".join(sorted(key.split())), [])
                i = cands[0] if len(cands) == 1 else None
            if i is None:
                missing.append(f"{name} ({div})")
                ids.append(-1)
            else:
                ids.append(i)
        divisions.append([div, ids])

    ranked = sum(1 for _, ids in divisions for i in ids if i >= 0)
    print(f"Rankings ({r.get('updated', 'sin fecha')}): {ranked} peleadores encontrados")
    if missing:
        print("  Sin coincidencia (agrégalos en 'aliases' de rankings.json): " + ", ".join(missing))
    return {"updated": r.get("updated", ""), "divisions": divisions}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="carpeta con los CSV ya descargados")
    ap.add_argument("--out", default="data/game_data.json")
    ap.add_argument("--rankings", default="rankings.json", help="archivo con los rankings actuales")
    ap.add_argument("--check", nargs=2, metavar=("A", "B"))
    ap.add_argument("--min-fights", type=int, default=8000,
                    help="aborta si hay menos peleas que esto (evita publicar datos incompletos)")
    args = ap.parse_args()

    print("Leyendo datos…")
    d = load_csvs(args.local)

    events = {}
    for e in d["ufc_event_details.csv"]:
        try:
            dt = datetime.strptime(clean(e["DATE"]), "%B %d, %Y").date()
        except ValueError:
            continue
        events[clean(e["EVENT"])] = dt
    today = date.today()

    # Nombres que pertenecen a más de un peleador: se separan por división
    full = Counter(clean(f"{r['FIRST']} {r['LAST']}") for r in d["ufc_fighter_details.csv"])
    dup_names = {n for n, c in full.items() if c > 1}

    def division(wc: str) -> str:
        wc = clean(wc).replace(" Bout", "")
        wc = re.sub(r"^(UFC|Ultimate Fighter.*?|TUF.*?)\s+", "", wc)
        wc = re.sub(r"\s*(Title|Tournament|Interim|Championship).*$", "", wc, flags=re.I)
        return wc or "Catch Weight"

    rows, skipped = [], 0
    for r in d["ufc_fight_results.csv"]:
        ev = clean(r["EVENT"])
        bout = clean(r["BOUT"]).split(" vs. ")
        if len(bout) != 2 or ev not in events or events[ev] > today:
            skipped += 1
            continue
        a, b = bout
        div = division(r["WEIGHTCLASS"])
        if a in dup_names:
            a = f"{a} ({div})"
        if b in dup_names:
            b = f"{b} ({div})"
        out = clean(r["OUTCOME"])
        winner = 0 if out == "W/L" else 1 if out == "L/W" else -1
        rd = clean(r["ROUND"])
        rows.append((events[ev], ev, a, b, winner, METHODS.get(clean(r["METHOD"]), "OTRO"),
                     int(rd) if rd.isdigit() else 0))

    if len(rows) < args.min_fights:
        sys.exit(f"Error: solo se leyeron {len(rows)} peleas (mínimo {args.min_fights}). "
                 "Los datos de origen parecen incompletos; no se genera el archivo.")
    rows.sort(key=lambda x: x[0])
    fight_count = Counter()
    for _, _, a, b, *_ in rows:
        fight_count[a] += 1
        fight_count[b] += 1

    fighters = sorted(fight_count, key=lambda n: n.lower())
    fidx = {n: i for i, n in enumerate(fighters)}
    ev_order = sorted({(dt, ev) for dt, ev, *_ in rows})
    eidx = {ev: i for i, (_, ev) in enumerate(ev_order)}

    rankings = load_rankings(args.rankings, fighters)

    game = {
        "v": 3,
        "rankings": rankings,
        "source": "UFCStats.com vía github.com/Greco1899/scrape_ufc_stats",
        "updated": ev_order[-1][0].isoformat() if ev_order else "",
        "fighters": [[n, fight_count[n]] for n in fighters],
        "events": [[ev, dt.isoformat()] for dt, ev in ev_order],
        # [peleador A, peleador B, evento, ganador (0=A, 1=B, -1=empate/sin resultado), método, round]
        "fights": [[fidx[a], fidx[b], eidx[ev], w, m, rd] for _, ev, a, b, w, m, rd in rows],
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(game, ensure_ascii=False, separators=(",", ":")), "utf-8")

    # Reporte
    adj = defaultdict(set)
    for _, _, a, b, *_ in rows:
        adj[a].add(b)
        adj[b].add(a)
    seen, biggest = set(), 0
    for s in adj:
        if s in seen:
            continue
        size, q = 0, deque([s])
        seen.add(s)
        while q:
            u = q.popleft()
            size += 1
            for v in adj[u] - seen:
                seen.add(v)
                q.append(v)
        biggest = max(biggest, size)

    kb = out.stat().st_size / 1024
    print(f"\nListo: {len(fighters)} peleadores, {len(rows)} peleas, {len(ev_order)} eventos "
          f"(último: {game['updated']}) → {out} ({kb:.0f} KB)")
    print(f"Conectados entre sí: {biggest} de {len(fighters)} peleadores")
    if skipped:
        print(f"Omitidas: {skipped} filas sin evento con fecha o con formato inesperado")
    if dup_names:
        print(f"Nombres repetidos separados por división: {', '.join(sorted(dup_names))}")

    if args.check:
        a, b = args.check
        hits = [x for x in rows if {x[2], x[3]} == {a, b}]
        print(f"\nChequeo {a} vs {b}: " + ("; ".join(f"{x[1]} ({x[0]})" for x in hits) if hits else "sin peleas en UFC"))


if __name__ == "__main__":
    main()
