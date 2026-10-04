#!/usr/bin/env python3
"""Harmonogram drzewa na żywo: paczki wybierane przez politykę, czas T i zamknięcie drzewa.

Zero agenta. `krok` czyta stan z `trees/`, pyta politykę o następną paczkę i drukuje polecenia dla
workflow (`WEZEL <drzewo> <węzeł> <kolejność>`, `OFFLINE <drzewo>`). Jest idempotentny: bez zmian
w drzewie powtórzone wywołanie niczego nie robi. Uruchamiany z checkoutu gałęzi domyślnej.

Funkcje `obserwacje`, `Pytanie`, `paczka`, `czas_h` i `wartosc` są wspólne dla drzewa na żywo
i odtwarzania nagranego drzewa. Kontrakt: docs/loop-config.md.
"""
import hashlib
import importlib.util
import json
import os
import sys

import loop

POLICY = os.path.join(".github", "policy", "policy.py")
CONFIG = os.path.join(".github", "policy", "config.json")


def config(base):
    return loop.read_json(os.path.join(base, CONFIG))


def load_policy(base):
    """Moduł polityki i skrót jego treści (polityka jest przypięta na całe drzewo)."""
    return load_file(os.path.join(base, POLICY))


def load_file(path):
    with open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location("policy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, digest


# ---------------------------------------------------------------- widok dla polityki

def key(name):
    return tuple(int(x) for x in name.split("."))


def obserwacje(recs, baseline):
    """Ocenione węzły dla polityki, po łańcuchu i głębokości; `delta` względem rodzica (dla korzenia: baseline)."""
    out = []
    for name in sorted(recs, key=key):
        r = recs[name]
        if r.get("stan") != "oceniony":
            continue
        sv = loop.s_v(r) or 0.0
        base = baseline if r["rodzic"] == loop.ROOT else (loop.s_v(recs[r["rodzic"]]) or 0.0)
        chain, depth = key(name)
        out.append({"wezel": name, "lancuch": chain, "glebokosc": depth,
                    "rodzic": None if r["rodzic"] == loop.ROOT else r["rodzic"],
                    "s_v": sv, "delta": sv - base})
    return out


class Pytanie:
    """Widok drzewa dla polityki: tylko ujawniony prefiks, nic o trybie."""

    def __init__(self, obs, W, K, runda, baseline, zamkniete=()):
        self.max_parallelism, self.max_rounds, self.round, self.baseline_score = W, K, runda, baseline
        self._obs = obs
        self._closed = set(zamkniete)   # łańcuchy bez dalszego ciągu (tylko odtwarzanie): bez akcji, obserwacje zostają

    def observed(self):
        return [dict(o) for o in self._obs]

    def legal_actions(self):
        """`None` (nowy łańcuch od korzenia) i czubki łańcuchów."""
        tips = {o["lancuch"]: o["wezel"] for o in self._obs if o["lancuch"] not in self._closed}
        return [None] + list(tips.values())


def paczka(wyjscie, pytanie):
    """Legalna paczka z tego, co zwróciła polityka: tylko dozwolone akcje, liść najwyżej raz, nie więcej niż W."""
    liscie = set(pytanie.legal_actions()) - {None}
    out = []
    for a in wyjscie or []:
        if len(out) >= pytanie.max_parallelism:
            break
        if a is None or (isinstance(a, str) and a in liscie and a not in out):
            out.append(a)
    return out


def nazwij(akcje, paczki):
    """Akcje -> nazwy węzłów: `None` to nowy łańcuch (kolejny numer), liść `c.d` daje `c.(d+1)`."""
    chain = max([key(n)[0] for p in paczki for n in p] or [0])
    out = []
    for a in akcje:
        if a is None:
            chain += 1
            out.append("%d.1" % chain)
        else:
            c, d = key(a)
            out.append("%d.%d" % (c, d + 1))
    return out


# ---------------------------------------------------------------- czas T i wartość V

def koszt_h(rec):
    """Czas węzła w godzinach: sesja + symulator + seria. Oczekiwanie zostaje poza kosztem.
    Węzeł bez zmian w kodzie dziedziczy oceny rodzica, więc nie płaci drugi raz za ocenę."""
    o = rec.get("oceny") or {}
    min_ = rec["koszt"]["minuty"]
    if not (rec["sha"] == rec["rodzic_sha"] and rec["rodzic"] != loop.ROOT):
        min_ += o.get("czas_sym_min", 0) + o.get("czas_serii_min", 0)
    return min_ / 60


def czas_h(paczki, recs):
    """T: paczka kosztuje najdłuższy węzeł, T to suma po paczkach. Węzły spoza `recs` się nie liczą."""
    return sum(max((koszt_h(recs[n]) for n in p if n in recs), default=0) for p in paczki)


def wartosc(paczki, recs, beta):
    """V = max s_v - beta * T po ocenionych węzłach (bez węzłów: 0)."""
    svs = [loop.s_v(r) or 0.0 for r in recs.values() if r.get("stan") == "oceniony"]
    return max(svs, default=0.0) - beta * czas_h(paczki, recs)


# ---------------------------------------------------------------- stan drzewa

def state_path(base, tree):
    return os.path.join(base, loop.TREES, "%s.json" % tree)


def read_state(base, tree):
    p = state_path(base, tree)
    return loop.read_json(p) if os.path.exists(p) else None


def next_tree(base):
    """Bieżące otwarte drzewo albo następne po zamkniętym."""
    d = os.path.join(base, loop.TREES)
    nums = {int(f.split(".")[0]) for f in os.listdir(d) if f.split(".")[0].isdigit()} if os.path.isdir(d) else set()
    if not nums:
        return 1
    n = max(nums)
    st = read_state(base, n)
    return n + 1 if st and st["koniec"] else n


def baseline(base):
    """`trees/baseline.json` (`{"s_v": x}`) to opcjonalny zapis ręczny; bez niego baseline to 0."""
    p = os.path.join(base, loop.TREES, "baseline.json")
    return loop.read_json(p)["s_v"] if os.path.exists(p) else 0.0


def zamknij(base, tree, st, powod, recs, cfg):
    st["koniec"] = {"powod": powod, "T_h": round(czas_h(st["paczki"], recs), 2),
                    "V": round(wartosc(st["paczki"], recs, cfg["beta"]), 6)}
    loop.write_json(state_path(base, tree), st)
    # po celu pętla się kończy: offline nie ma już czego poprawiać
    return [] if powod == "cel" else [("OFFLINE", tree)]


def krok(base, tree, policy, digest, cfg, cel):
    """Jeden krok harmonogramu: czeka na paczkę, otwiera następną albo zamyka drzewo. Zwraca polecenia."""
    st = read_state(base, tree)
    if cel and (st is None or st["koniec"]):
        return []
    if st is None:
        st = {"polityka": digest, "paczki": [], "koniec": None}
    if st["koniec"]:
        return []
    if st["polityka"] != digest:
        raise SystemExit("polityka zmieniona w trakcie drzewa %s (%s -> %s)" % (tree, st["polityka"], digest))
    recs = loop.load_tree(base, tree)
    if cel:
        return zamknij(base, tree, st, "cel", recs, cfg)
    if st["paczki"] and any(recs.get(n, {}).get("stan") != "oceniony" for n in st["paczki"][-1]):
        return []
    if len(st["paczki"]) >= cfg["K"]:
        return zamknij(base, tree, st, "K", recs, cfg)
    q = Pytanie(obserwacje(recs, baseline(base)), cfg["W"], cfg["K"], len(st["paczki"]), baseline(base))
    nodes = nazwij(paczka(policy.solve(q), q), st["paczki"])
    if not nodes:
        return zamknij(base, tree, st, "pusta paczka", recs, cfg)
    order = sum(len(p) for p in st["paczki"])
    st["paczki"].append(nodes)
    loop.write_json(state_path(base, tree), st)
    return [("WEZEL", tree, n, order + i + 1) for i, n in enumerate(nodes)]


# ---------------------------------------------------------------- main

def main(argv):
    cmd, args = argv[1], argv[2:]
    base = os.getcwd()
    if cmd == "numer":
        print(args[0] if args and args[0] else next_tree(base))
        return 0
    if cmd == "krok":
        policy, digest = load_policy(base)
        cel = os.path.exists(os.path.join(base, loop.TREES, "cel.json"))
        for line in krok(base, args[0], policy, digest, config(base), cel):
            print(*line)
        return 0
    raise SystemExit("nieznane polecenie: " + cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
