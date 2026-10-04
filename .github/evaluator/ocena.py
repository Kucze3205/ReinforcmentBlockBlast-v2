#!/usr/bin/env python3
"""Ewaluator węzła: ocena symulatorem, zliczenie serii z emulatora, bramka celu, hash.

Biegnie z checkoutu gałęzi domyślnej, nigdy z gałęzi węzła. Kod węzła dostaje własną kopię,
na którą nakładamy z gałęzi domyślnej pliki z `tylko_do_odczytu` (config.json): zmiana
symulatora, punktacji czy mostu w węźle nic nie daje.

Kontrakt polityki węzła: `policies.build(weights)` zwraca obiekt z `reset(seed)` i
`act(game, actions)`; `weights` to ścieżka katalogu `weights/` węzła albo None.
Wyjątek w `build` daje wynik 0, wyjątek w trakcie partii kończy tę partię (przegrana).

Podpolecenia: nakladka, sym, zlicz, zapisz, bramka.
"""
import argparse
import hashlib
import json
import os
import random
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).with_name("config.json")
SERIA_YML = ".github/workflows/seria.yml"
OCENA_PY = ".github/evaluator/ocena.py"
VALID_END = ("przegrana", "cel")


def config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- rozdania i hash

def rozdania(drzewo, n, salt=None):
    """Rozdania drzewa: stałe w drzewie, inne w każdym, nie do odtworzenia bez soli (sekret repo)."""
    salt = salt if salt is not None else os.environ.get("DEALS_SALT")
    if not salt:
        raise SystemExit("brak DEALS_SALT: rozdania nie mogą mieć domyślnej wartości w publicznym repo")
    return random.Random("%s:%s" % (salt, drzewo)).sample(range(1, 2**31 - 1), n)


def _digest(paths, params):
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.encode() + b"\0" + (ROOT / p).read_bytes() + b"\0")
    h.update(json.dumps(params, sort_keys=True).encode())
    return h.hexdigest()[:16]


def hash_sym(deals_digest, cfg=None):
    """Semantyka symulatora: symulator, generator, punktacja, kod oceny, parametry, rozdania."""
    cfg = cfg or config()
    files = cfg["tylko_do_odczytu"]["sym"] + [OCENA_PY]
    params = {k: cfg[k] for k in ("rozdania", "cap", "tie")}
    return _digest(files, dict(params, rozdania_digest=deals_digest))


def hash_most(cfg=None):
    """Most i seria: naprawa mostu zmienia tylko tę część i niczego nie przelicza."""
    cfg = cfg or config()
    files = cfg["tylko_do_odczytu"]["most"] + [SERIA_YML]
    return _digest(files, {k: cfg[k] for k in ("partie", "cel")})


def deals_digest(seeds):
    return hashlib.sha256(json.dumps(seeds).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- węzeł

def nakladka(node):
    """Pliki ewaluatora z gałęzi domyślnej nadpisują te w kopii węzła."""
    for group in config()["tylko_do_odczytu"].values():
        for rel in group:
            dst = Path(node) / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, dst)


def build_policy(node):
    node = Path(node).resolve()
    os.chdir(node)
    sys.path.insert(0, str(node))
    import policies
    weights = node / "weights"
    has = weights.is_dir() and any(weights.iterdir())
    return policies.build(str(weights) if has else None)


def graj(policy, seed, cap, game_cls):
    """(ruchy, punkty, błąd). Dojście do capa to nie przegrana; wyjątek polityki kończy partię."""
    game = game_cls(seed=seed)
    try:
        policy.reset(seed)
        while not game.done:
            if game.placements >= cap:
                break
            actions = game.available_actions()
            if not actions:
                break
            game.step(policy.act(game, actions))
        return game.placements, game.score, None
    except Exception as exc:
        return game.placements, game.score, "%s: %s" % (type(exc).__name__, str(exc)[:200])


def sym(node, drzewo, shard, shardy, out):
    cfg = config()
    seeds = rozdania(drzewo, cfg["rozdania"])
    os.environ.pop("DEALS_SALT", None)   # kod węzła nie czyta soli
    mine = list(range(shard, len(seeds), shardy))
    rec = {"drzewo": drzewo, "hash_sym": hash_sym(deals_digest(seeds), cfg),
           "shard": shard, "gry": [], "blad": None}
    try:
        policy = build_policy(node)
        from game import Game
    except Exception as exc:
        rec["blad"] = "%s: %s" % (type(exc).__name__, str(exc)[:200])
        rec["gry"] = [{"i": i, "ruchy": 0, "punkty": 0} for i in mine]
    else:
        deadline = time.monotonic() + cfg["limit_shardu_s"]
        for i in mine:
            if time.monotonic() > deadline:
                break
            ruchy, punkty, blad = graj(policy, seeds[i], cfg["cap"], Game)
            rec["gry"].append({"i": i, "ruchy": ruchy, "punkty": punkty})
            rec["blad"] = rec["blad"] or blad
    Path(out).write_text(json.dumps(rec), encoding="utf-8")


# ---------------------------------------------------------------- zliczanie

def _json_files(root, name):
    return sorted(Path(root).rglob(name)) if root and Path(root).is_dir() else []


def zlicz_sym(shard_dir, cfg):
    shards = [json.loads(p.read_text(encoding="utf-8")) for p in _json_files(shard_dir, "sym-*.json")]
    if not shards:
        return None
    hashes = {s["hash_sym"] for s in shards}
    if len(hashes) != 1:
        raise SystemExit("shardy z różnych wersji ewaluatora: %s" % sorted(hashes))
    gry = {g["i"]: g for s in shards for g in s["gry"]}
    gry = [gry[i] for i in sorted(gry)]
    n = len(gry)
    mean_ruchy = sum(g["ruchy"] for g in gry) / n if n else 0.0
    mean_punkty = sum(g["punkty"] for g in gry) / n if n else 0.0
    return {
        "hash": hashes.pop(),
        "przezycie": [g["ruchy"] for g in gry],
        "punkty_srednie": round(mean_punkty, 2),
        "przegrane": sum(g["ruchy"] < cfg["cap"] for g in gry),
        "za_wolna": n < cfg["rozdania"],
        "blad": next((s["blad"] for s in shards if s["blad"]), None),
        "s_sym": min(1.0, mean_ruchy / cfg["cap"] + cfg["tie"] * mean_punkty),
    }


def zlicz_seria(seria_dir, cfg):
    """Partie z katalogów `...-partia-K/pomiar.json`: ważne (przegrana, cel) i unieważnione."""
    ok, niewazne = {}, []
    dirs = sorted(p for p in Path(seria_dir).iterdir() if p.is_dir()) if seria_dir and Path(seria_dir).is_dir() else []
    for d in dirs:
        m = re.search(r"-partia-(\d+)$", d.name)
        if not m:
            continue
        k = int(m.group(1))
        files = list(d.rglob("pomiar.json"))
        if not files:
            niewazne.append({"partia": k, "koniec": "awaria", "przyczyna": "brak pomiar.json"})
            continue
        p = json.loads(files[0].read_text(encoding="utf-8"))
        if p.get("koniec") in VALID_END:
            ok[k] = {f: p.get(f) for f in ("koniec", "licznik", "ruchy", "czas_s")}
            if p["koniec"] == "przegrana":
                ok[k].update({f: p.get(f) for f in ("plansza", "ostatnie_ruchy")})
        else:
            niewazne.append({"partia": k, "koniec": p.get("koniec", "awaria"), "przyczyna": p.get("przyczyna")})
    return ok, niewazne


def s_emu(partie, cfg):
    if not partie:
        return 0.0
    return sum(1.0 if p["koniec"] == "cel" else min(1.0, (p["licznik"] or 0) / cfg["cel"])
               for p in partie.values()) / len(partie)


def s_v(sym_ocena, emu, cfg=None):
    """1 + s_emu, gdy węzeł ma pełną serię; inaczej s_sym (nie więcej niż 1)."""
    cfg = cfg or config()
    if emu and len(emu["partie"]) >= cfg["partie"]:
        return 1.0 + s_emu(emu["partie"], cfg)
    return sym_ocena["s_sym"]


def zlicz(drzewo, sym_dir, seria_dir, poprzednia, wezel=None):
    cfg = config()
    prev = json.loads(Path(poprzednia).read_text(encoding="utf-8")) if poprzednia else {}
    sym_ocena = zlicz_sym(sym_dir, cfg) or prev.get("sym")
    if sym_ocena is None:
        raise SystemExit("brak oceny symulatorem")
    partie = {int(k): v for k, v in prev.get("emu", {}).get("partie", {}).items()}
    nowe, niewazne = zlicz_seria(seria_dir, cfg)
    for k, v in nowe.items():
        partie.setdefault(k, v)
    niewazne = [n for n in niewazne if n["partia"] not in partie]
    brakuje = [k for k in range(1, cfg["partie"] + 1) if k not in partie]
    prog = sym_ocena["przegrane"] == 0 and not sym_ocena["za_wolna"]
    return {
        "wezel": wezel or prev.get("wezel"),
        "drzewo": drzewo,
        "hash": {"sym": sym_ocena["hash"], "most": hash_most(cfg)},
        "sym": sym_ocena,
        "emu": {"partie": {str(k): partie[k] for k in sorted(partie)}, "niewazne": niewazne} if (partie or niewazne) else None,
        "potrzebna_seria": prog and bool(brakuje),
        "brakujace_partie": brakuje if prog else [],
        "status": "w_toku" if prog and brakuje else "gotowa",
    }


def bramka(ocena, cfg=None):
    """Cel: pełna seria, każda partia dotarła do 1 mln bez przegranej."""
    cfg = cfg or config()
    partie = (ocena.get("emu") or {}).get("partie", {})
    return len(partie) >= cfg["partie"] and all(p["koniec"] == "cel" for p in partie.values())


def zapisz(ocena, rekord, cel_path):
    """Wpisuje ocenę do rekordu węzła (`oceny`, `stan`); przy bramce celu zakłada znacznik `cel_path`."""
    rec = json.loads(Path(rekord).read_text(encoding="utf-8"))
    o = rec.get("oceny") or {}
    s = ocena["sym"]
    o.setdefault("s_sym", {})[s["hash"]] = s["s_sym"]
    o.setdefault("sym", {})[s["hash"]] = {k: s[k] for k in ("przezycie", "przegrane", "za_wolna", "blad", "punkty_srednie")}
    o["hash_most"] = ocena["hash"]["most"]
    emu = ocena.get("emu")
    if emu:
        o["emu"] = emu
        if len(emu["partie"]) >= config()["partie"]:
            o["s_emu"] = s_emu(emu["partie"], config())
            o["czas_serii_min"] = round(max(p["czas_s"] or 0 for p in emu["partie"].values()) / 60, 1)
    rec["oceny"] = o
    rec["stan"] = "oceniony" if ocena["status"] == "gotowa" else "ocena w toku"
    Path(rekord).write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    if bramka(ocena):
        Path(cel_path).write_text(json.dumps({"wezel": ocena.get("wezel"), "drzewo": ocena["drzewo"]}) + "\n", encoding="utf-8")


def podsumowanie(ocena):
    s = ocena["sym"]
    emu = ocena.get("emu") or {"partie": {}, "niewazne": []}
    return "\n".join([
        "### Ocena węzła `%s` (drzewo %s)" % ((ocena.get("wezel") or "?")[:12], ocena["drzewo"]),
        "",
        "- symulator: s_sym = %.6f, przegrane %d/%d, za wolna: %s%s" % (
            s["s_sym"], s["przegrane"], len(s["przezycie"]), s["za_wolna"],
            ", błąd: " + s["blad"] if s["blad"] else ""),
        "- emulator: ważne partie %d, unieważnione %d, s_emu = %.4f" % (
            len(emu["partie"]), len(emu["niewazne"]), s_emu(emu["partie"], config())),
        "- status: %s · s_v = %.6f · bramka celu: %s" % (
            ocena["status"], s_v(s, ocena["emu"]), "OSIĄGNIĘTA" if bramka(ocena) else "nie"),
    ]) + "\n"


# ---------------------------------------------------------------- main

def main(argv):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("nakladka").add_argument("node")
    p = sub.add_parser("sym")
    p.add_argument("node")
    p.add_argument("--drzewo", required=True)
    p.add_argument("--shard", required=True, help="I/N")
    p.add_argument("--out", required=True)
    p = sub.add_parser("zlicz")
    p.add_argument("--drzewo", required=True)
    p.add_argument("--wezel")
    p.add_argument("--sym")
    p.add_argument("--seria")
    p.add_argument("--poprzednia")
    p.add_argument("--out", required=True)
    p.add_argument("--podsumowanie")
    sub.add_parser("bramka").add_argument("ocena")
    p = sub.add_parser("zapisz")
    p.add_argument("ocena")
    p.add_argument("rekord")
    p.add_argument("--cel", default="trees/cel.json")
    a = ap.parse_args(argv[1:])

    if a.cmd == "nakladka":
        nakladka(a.node)
    elif a.cmd == "sym":
        i, n = (int(x) for x in a.shard.split("/"))
        sym(a.node, a.drzewo, i, n, a.out)
    elif a.cmd == "zlicz":
        o = zlicz(a.drzewo, a.sym, a.seria, a.poprzednia, a.wezel)
        Path(a.out).write_text(json.dumps(o, indent=1, ensure_ascii=False), encoding="utf-8")
        if a.podsumowanie:
            with open(a.podsumowanie, "a", encoding="utf-8") as fh:
                fh.write(podsumowanie(o))
    elif a.cmd == "zapisz":
        zapisz(json.loads(Path(a.ocena).read_text(encoding="utf-8")), a.rekord, a.cel)
    elif a.cmd == "bramka":
        ok = bramka(json.loads(Path(a.ocena).read_text(encoding="utf-8")))
        print("bramka celu: %s" % ("osiągnięta" if ok else "nie"))
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
