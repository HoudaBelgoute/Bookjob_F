"""CLI du pipeline : collecte → Excel brut → nettoyage → Excel nettoyé (+ rapport, exclusions, dictionnaire).

Exemples (depuis ``backend``) :
  python -m app.pipeline.run --source excel                      # re-nettoie donnees_brutes_places.xlsx
  python -m app.pipeline.run --source places                     # collecte Google Places (GOOGLE_API_KEY)
  python -m app.pipeline.run --source places --queries "agence web Marrakech" "startup Marrakech"

Le fichier utilisé par l'application (``donnees_nettoyees.xlsx``) n'est jamais écrasé : la sortie va dans
``donnees_nettoyees_pipeline.xlsx`` pour être relue avant remplacement manuel.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .. import config as C
from .cleaning import clean, previous_ids_from
from .sources import ExcelSource, GooglePlacesSource, collect_all

RAW_DEFAULT = C.DATA_DIR / "donnees_brutes_places.xlsx"
OUT_DEFAULT = C.DATA_DIR / "donnees_nettoyees_pipeline.xlsx"
RUNS_FILE = C.DATA_DIR / "pipeline_runs.json"


def load_runs(path: Path = RUNS_FILE) -> list[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _record_run(run: dict, path: Path) -> None:
    runs = load_runs(path)[-49:] + [run]
    path.write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")


def run_pipeline(sources, out_path: Path, raw_out: Path | None = None, reference: Path | None = None,
                 runs_file: Path = RUNS_FILE) -> dict:
    started = datetime.now(timezone.utc)
    raw, log = collect_all(sources)
    if raw_out is not None and not raw.empty:
        raw.to_excel(raw_out, index=False, sheet_name="Données brutes")

    previous = {}
    if reference is not None and Path(reference).exists():
        previous = previous_ids_from(pd.read_excel(reference, sheet_name="Données nettoyées"))
    result = clean(raw, previous)

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        result.clean.to_excel(writer, index=False, sheet_name="Données nettoyées")
        result.excluded.to_excel(writer, index=False, sheet_name="Lignes exclues")
        result.report.to_excel(writer, index=False, sheet_name="Rapport nettoyage")
        result.dictionary().to_excel(writer, index=False, sheet_name="Dictionnaire")
        pd.DataFrame(log).to_excel(writer, index=False, sheet_name="Journal collecte")

    run = {
        "debut": started.isoformat(timespec="seconds"),
        "fin": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": log,
        "lignes_brutes": int(len(raw)),
        "lignes_nettoyees": int(len(result.clean)),
        "lignes_exclues": int(len(result.excluded)),
        "sortie": Path(out_path).name,
        "statut": "échec" if raw.empty else ("partiel" if any(s["erreurs"] for s in log) else "succès"),
    }
    _record_run(run, runs_file)
    return run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline de collecte et de nettoyage BookJob")
    parser.add_argument("--source", choices=["excel", "places"], action="append",
                        help="Source(s) à utiliser (répétable). Défaut : excel")
    parser.add_argument("--raw", type=Path, default=RAW_DEFAULT, help="Excel brut à importer (source excel)")
    parser.add_argument("--queries", nargs="*", help="Requêtes Google Places (source places)")
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT, help="Excel nettoyé produit")
    args = parser.parse_args(argv)

    sources, raw_out = [], None
    for name in args.source or ["excel"]:
        if name == "excel":
            sources.append(ExcelSource(args.raw))
        else:
            sources.append(GooglePlacesSource(C.GOOGLE_API_KEY, args.queries))
            raw_out = C.DATA_DIR / f"donnees_brutes_collecte_{datetime.now():%Y%m%d_%H%M}.xlsx"

    run = run_pipeline(sources, args.out, raw_out=raw_out, reference=C.XLSX)
    for s in run["sources"]:
        print(f"[{s['statut']}] {s['source']} : {s['lignes']} lignes {('— ' + s['erreurs']) if s['erreurs'] else ''}")
    print(f"Brutes : {run['lignes_brutes']} · nettoyées : {run['lignes_nettoyees']} · "
          f"exclues : {run['lignes_exclues']} → {args.out}")
    return 0 if run["statut"] != "échec" else 1


if __name__ == "__main__":
    sys.exit(main())
