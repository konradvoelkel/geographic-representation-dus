"""Weg 3 von Vorhaben 19: ein CAP-Klassifikator, nachgebaut nach dem Muster der Babel Machine.

Läuft **nicht** im Venv des Pakets, sondern in einem eigenen außerhalb (torch und transformers
kommen nie in `pyproject.toml` oder `uv.lock`), unter der GPU-Sperre und in Blöcken:

    V=/media/konrad/xtraspace/venvs/cap-train
    flock /media/konrad/xtraspace/georep/gpu-queue/gpu.lock \\
        $V/bin/python -I docs/plans/19-politikfelder-training.py --variante 3a --block-minuten 25

`-I` hält das Arbeitsverzeichnis aus dem Suchpfad. Ein Block endet nach `--block-minuten` mit
einem Prüfpunkt; derselbe Aufruf setzt dort fort. Gelesen wird nur, was das Messskript unter
`$GEOREP_MESSDATEN/19-politikfelder/` schreibt: `cap_de.parquet` (deutsche CAP-Daten mit Spalte
`zurueck`), `ratsdokumente.parquet` (Eingabe je Ratsdokument) und für 3b die Antworten von Weg 1
(`weg1_entwicklung_*.parquet`, `weg1_silber_*.parquet`). Geschrieben wird dorthin: `weg3<v>_test`,
`weg3<v>_entwicklung`, `weg3<v>_cap_zurueck` (Parquet) und `weg3<v>_lauf.json`.

Vorab festgelegt (Messdokument § 8.3): `xlm-roberta-large`, Länge 256, Lernrate 1e-5, Stapel 16,
zwei Epochen, 10 % Aufwärmen, Seed 0; der Prüfpunkt mit dem höchsten Makro-F1 auf den
zurückgehaltenen 10 % der CAP-Daten (nie auf Ratsdokumenten). Die Testmenge sieht das Training
nie: ihre Zeilen in `ratsdokumente.parquet` werden nur vorhergesagt.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import time
from pathlib import Path

import polars as pl
import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

# xlm-roberta-large, MIT-Lizenz, Stand des Repos auf dem Hub; nur safetensors, kein Fremdcode
REVISION = "c23d21b0620b635a76227c604d44e43a9f0ee389"
MESSDATEN = Path(os.environ.get("GEOREP_MESSDATEN", "/media/konrad/xtraspace/georep/messdaten"))
AUSGABE = MESSDATEN / "19-politikfelder"
CODES = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "13", "14", "15", "16", "17")
CODES += ("18", "19", "20", "21", "23", "99")
SILBER_ANTEIL = 0.25  # 3b: Silberlabels stellen rund ein Viertel der Beispiele je Epoche
SILBER_HOECHSTENS = 20  # ... höchstens 20-fach wiederholt


def makro_f1(gold: list[str], vorhersage: list[str]) -> float:
    """Wie F4: ungewichtetes Mittel der F1 über die Klassen mit Gold oder Vorhersage."""
    werte = []
    for k in sorted(set(gold) | set(vorhersage)):
        tp = sum(g == k and v == k for g, v in zip(gold, vorhersage, strict=True))
        fp = sum(g != k and v == k for g, v in zip(gold, vorhersage, strict=True))
        fn = sum(g == k and v != k for g, v in zip(gold, vorhersage, strict=True))
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        werte.append(2 * p * r / (p + r) if p + r else 0.0)
    return sum(werte) / len(werte)


def silberlabels() -> pl.DataFrame:
    """Antworten von Weg 1 auf Ratsdokumenten außerhalb der Testmenge (Entwicklung und Silber)."""
    teile = [
        pl.read_parquet(p).select("id", "label")
        for name in ("weg1_entwicklung_*.parquet", "weg1_silber_*.parquet")
        for p in sorted(AUSGABE.glob(name))
        if "qwen3.6-27b" in p.name
    ]
    if not teile:
        return pl.DataFrame(schema={"id": pl.String, "label": pl.String})
    return pl.concat(teile).filter(pl.col("label").is_in(list(CODES))).unique("id").sort("id")


def trainingsdaten(variante: str, seed: int) -> tuple[pl.DataFrame, int]:
    cap = pl.read_parquet(AUSGABE / "cap_de.parquet")
    train = cap.filter(~pl.col("zurueck")).select("text", "label")
    silber = 0
    if variante == "3b":
        rats = pl.read_parquet(AUSGABE / "ratsdokumente.parquet").filter(pl.col("menge") != "test")
        s = silberlabels().join(rats.select("id", "text"), on="id", how="inner")
        silber = s.height
        if silber:
            wiederholt = min(
                SILBER_HOECHSTENS,
                max(1, round(SILBER_ANTEIL * train.height / ((1 - SILBER_ANTEIL) * silber))),
            )
            train = pl.concat([train, *[s.select("text", "label")] * wiederholt])
    return train.sample(fraction=1.0, shuffle=True, seed=seed), silber


def kodiere(tok: object, texte: list[str], laenge: int) -> dict[str, torch.Tensor]:
    return tok(texte, truncation=True, max_length=laenge, padding=True, return_tensors="pt")  # type: ignore[operator]


@torch.no_grad()
def vorhersage(
    model: torch.nn.Module, tok: object, texte: list[str], laenge: int, stapel: int = 64
) -> tuple[list[str], list[float]]:
    model.eval()
    labels: list[str] = []
    wahrsch: list[float] = []
    ordnung = sorted(range(len(texte)), key=lambda i: len(texte[i]))
    ergebnis: dict[int, tuple[str, float]] = {}
    for a in range(0, len(ordnung), stapel):
        idx = ordnung[a : a + stapel]
        batch = {k: v.cuda() for k, v in kodiere(tok, [texte[i] for i in idx], laenge).items()}
        with torch.autocast("cuda", dtype=torch.bfloat16):
            logits = model(**batch).logits.float()
        p = torch.softmax(logits, dim=-1)
        best = p.argmax(dim=-1).tolist()
        conf = p.max(dim=-1).values.tolist()
        for i, b, c in zip(idx, best, conf, strict=True):
            ergebnis[i] = (CODES[b], float(c))
    for i in range(len(texte)):
        labels.append(ergebnis[i][0])
        wahrsch.append(ergebnis[i][1])
    model.train()
    return labels, wahrsch


def trocken(args: argparse.Namespace, tok: object, train: pl.DataFrame, silber: int) -> None:
    """Ohne GPU: Zahl der Beispiele und Schritte, Länge in Token, ein Schritt auf der CPU."""
    texte = train.get_column("text").to_list()
    probe = random.Random(args.seed).sample(texte, min(2000, len(texte)))
    laengen = [len(ids) for ids in tok(probe)["input_ids"]]  # type: ignore[operator]
    print(
        f"{len(texte)} Beispiele ({silber} Silberdokumente), "
        f"{(len(texte) + args.stapel - 1) // args.stapel * args.epochen} Schritte; Token je Beispiel "
        f"Median {sorted(laengen)[len(laengen) // 2]}, über {args.laenge}: "
        f"{sum(n > args.laenge for n in laengen)} von {len(laengen)}"
    )
    print(train.group_by("label").len().sort("len", descending=True).head(25))
    model = AutoModelForSequenceClassification.from_pretrained(
        args.modell, num_labels=len(CODES), use_safetensors=True, revision=REVISION
    )
    batch = kodiere(tok, texte[:2], args.laenge)
    y = torch.tensor([CODES.index(lbl) for lbl in train.get_column("label").to_list()[:2]])
    out = model(**batch, labels=y)
    out.loss.backward()
    print(f"ein Schritt auf der CPU: Verlust {out.loss.item():.3f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variante", choices=["3a", "3b"], required=True)
    ap.add_argument("--modell", default="FacebookAI/xlm-roberta-large")
    ap.add_argument("--laenge", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--stapel", type=int, default=16)
    ap.add_argument("--epochen", type=int, default=2)
    ap.add_argument("--aufwaermen", type=float, default=0.10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--trocken", action="store_true", help="Daten, ein Schritt auf der CPU, Ende")
    ap.add_argument("--block-minuten", type=float, default=25.0)
    args = ap.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    ordner = AUSGABE / f"training-{args.variante}"
    ordner.mkdir(parents=True, exist_ok=True)
    pruefpunkt = ordner / "pruefpunkt.pt"
    beste = ordner / "beste"
    zustand_datei = ordner / "zustand.json"

    train, silber = trainingsdaten(args.variante, args.seed)
    cap = pl.read_parquet(AUSGABE / "cap_de.parquet")
    zurueck = cap.filter(pl.col("zurueck"))
    tok = AutoTokenizer.from_pretrained(args.modell, revision=REVISION)
    if args.trocken:
        trocken(args, tok, train, silber)
        return
    model = AutoModelForSequenceClassification.from_pretrained(
        args.modell, num_labels=len(CODES), use_safetensors=True, revision=REVISION
    ).cuda()
    texte = train.get_column("text").to_list()
    ziele = [CODES.index(lbl) for lbl in train.get_column("label").to_list()]
    schritte_je_epoche = (len(texte) + args.stapel - 1) // args.stapel
    gesamt = schritte_je_epoche * args.epochen
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    plan = get_linear_schedule_with_warmup(opt, int(args.aufwaermen * gesamt), gesamt)
    zustand = {"schritt": 0, "bestes_f1": -1.0, "epochen": [], "sekunden": 0.0, "bloecke": 0}
    if pruefpunkt.is_file():
        stand = torch.load(pruefpunkt, map_location="cuda", weights_only=True)
        model.load_state_dict(stand["model"])
        opt.load_state_dict(stand["opt"])
        plan.load_state_dict(stand["plan"])
        zustand = json.loads(zustand_datei.read_text())
        print(f"fortgesetzt bei Schritt {zustand['schritt']} von {gesamt}")
    zustand["bloecke"] += 1
    start = time.time()
    ende_block = start + 60 * args.block_minuten
    model.train()
    loader_ordnung = list(range(len(texte)))
    while zustand["schritt"] < gesamt:
        epoche, pos = divmod(zustand["schritt"], schritte_je_epoche)
        rng = random.Random(args.seed + epoche)
        ordnung = loader_ordnung[:]
        rng.shuffle(ordnung)
        idx = ordnung[pos * args.stapel : (pos + 1) * args.stapel]
        batch = {k: v.cuda() for k, v in kodiere(tok, [texte[i] for i in idx], args.laenge).items()}
        y = torch.tensor([ziele[i] for i in idx], device="cuda")
        with torch.autocast("cuda", dtype=torch.bfloat16):
            out = model(**batch, labels=y)
        out.loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        plan.step()
        opt.zero_grad(set_to_none=True)
        zustand["schritt"] += 1
        if zustand["schritt"] % 200 == 0:
            print(
                f"Schritt {zustand['schritt']}/{gesamt}, Verlust {out.loss.item():.3f}", flush=True
            )
        if zustand["schritt"] % schritte_je_epoche == 0:
            gold = zurueck.get_column("label").to_list()
            v, _ = vorhersage(model, tok, zurueck.get_column("text").to_list(), args.laenge)
            f1 = makro_f1(gold, v)
            zustand["epochen"].append({"schritt": zustand["schritt"], "makro_f1_zurueck": f1})
            print(f"Epoche {zustand['schritt'] // schritte_je_epoche}: Makro-F1 zurück {f1:.3f}")
            if f1 > zustand["bestes_f1"]:
                zustand["bestes_f1"] = f1
                model.save_pretrained(beste, safe_serialization=True)
                tok.save_pretrained(beste)
        if time.time() > ende_block and zustand["schritt"] < gesamt:
            break
    zustand["sekunden"] += time.time() - start
    if zustand["schritt"] < gesamt:
        torch.save(
            {"model": model.state_dict(), "opt": opt.state_dict(), "plan": plan.state_dict()},
            pruefpunkt,
        )
        zustand_datei.write_text(json.dumps(zustand, indent=1))
        print(f"Block zu Ende bei Schritt {zustand['schritt']} von {gesamt}; erneut aufrufen")
        return
    # fertig: mit dem besten Prüfpunkt vorhersagen
    del model, opt
    torch.cuda.empty_cache()
    model = AutoModelForSequenceClassification.from_pretrained(beste, use_safetensors=True).cuda()
    rats = pl.read_parquet(AUSGABE / "ratsdokumente.parquet")
    for menge in ("test", "entwicklung"):
        teil = rats.filter(pl.col("menge") == menge)
        v, w = vorhersage(model, tok, teil.get_column("text").to_list(), args.laenge)
        teil.select("id").with_columns(
            pl.Series("label", v), pl.Series("wahrscheinlichkeit", w)
        ).write_parquet(AUSGABE / f"weg{args.variante}_{menge}.parquet")
    v, w = vorhersage(model, tok, zurueck.get_column("text").to_list(), args.laenge)
    zurueck.select("id", "quelle", "label").with_columns(
        pl.Series("vorhersage", v), pl.Series("wahrscheinlichkeit", w)
    ).write_parquet(AUSGABE / f"weg{args.variante}_cap_zurueck.parquet")
    lauf = {
        **vars(args),
        "training_beispiele": len(texte),
        "silber_dokumente": silber,
        "schritte": gesamt,
        "epochen": zustand["epochen"],
        "bestes_f1_zurueck": zustand["bestes_f1"],
        "sekunden_training": round(zustand["sekunden"], 1),
        "bloecke": zustand["bloecke"],
        "torch": torch.__version__,
        "gpu": torch.cuda.get_device_name(0),
        "uptime": subprocess.run(["uptime"], capture_output=True, text=True).stdout.strip(),
        "zeit": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (AUSGABE / f"weg{args.variante}_lauf.json").write_text(json.dumps(lauf, indent=1))
    if pruefpunkt.is_file():
        pruefpunkt.unlink()
    print(json.dumps(lauf, indent=1))


if __name__ == "__main__":
    main()
