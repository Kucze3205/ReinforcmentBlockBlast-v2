#!/usr/bin/env python3
"""Faza offline: odtwarzanie nagranych drzew, kolejne wersje polityki i wybór najlepszej.

Zero agenta. Sesję piszącą wersję polityki uruchamia `offline.sh`; ten plik robi resztę: liczy V
(odtworzenie polityki na każdym zamkniętym drzewie), układa sesji katalog z tym, co wolno jej
zobaczyć, wybiera argmax razem z bieżącą polityką i wdraża zwycięzcę. Uruchamiany z checkoutu
gałęzi domyślnej. Kontrakt: docs/loop-config.md.

Podpolecenia: init, meta, wynik, wybierz (oraz `ile`, `odtworz` — wewnętrzne).
"""
import json
import math
import os
import shutil
import subprocess
import sys

import drzewo
import loop

POLICY_DIR = os.path.join(".github", "policy")
HISTORIA = os.path.join(POLICY_DIR, "history")
OPIS = os.path.join(POLICY_DIR, "meta.md")
LIMIT_S = 600   # czas odtworzenia jednej wersji na wszystkich drzewach; dłużej = polityka niedopuszczona


# ---------------------------------------------------------------- odtwarzanie jednego drzewa

def odkryty(rec, rodzic):
    """Nagrany rekord pod nazwą z odtwarzanego drzewa: rodzic wskazuje nazwę tutaj, nie w nagraniu."""
    return dict(rec, rodzic=rodzic)


def odtworz(policy, recs, cfg, baseline):
    """Ta sama `solve` co na żywo, `question` ujawnia zapisane węzły zamiast uruchamiać sesje.

    Nowy łańcuch dostaje najwcześniej utworzony nieużyty korzeń nagrania, kontynuacja węzeł tego
    samego łańcucha nagrania. Węzła spoza nagrania nie ma: łańcuch się kończy, bez kary w T.
    Runda, w której nic się nie ujawniło ani nie zamknęło, kończy odtwarzanie (polityka jest
    deterministyczna, więc powtórzyłaby to samo). Zwraca słownik z V, T_h, rundami i śladem."""
    W, K, beta = cfg["W"], cfg["K"], cfg["beta"]
    nagrane = {n: r for n, r in recs.items() if r.get("stan") == "oceniony"}
    korzenie = sorted((n for n, r in nagrane.items() if r["rodzic"] == loop.ROOT),
                      key=lambda n: nagrane[n]["kolejnosc"])
    mapa, ujawnione, zamkniete, paczki, slad = {}, {}, set(), [], []
    powod = "pusta paczka"
    while True:
        if len(paczki) >= K:
            powod = "K"
            break
        q = drzewo.Pytanie(drzewo.obserwacje(ujawnione, baseline), W, K, len(paczki), baseline, zamkniete)
        akcje = drzewo.paczka(policy.solve(q), q)
        wezly = drzewo.nazwij(akcje, paczki)
        if not wezly:
            break
        zmiana, linie = False, []
        for nazwa in wezly:
            c, d = drzewo.key(nazwa)
            if d == 1:
                wolny = next((n for n in korzenie if drzewo.key(n)[0] not in mapa.values()), None)
                if wolny is None:
                    linie.append("%s: brak nowego korzenia w nagraniu" % nazwa)
                    continue
                mapa[c] = drzewo.key(wolny)[0]
            r = nagrane.get("%d.%d" % (mapa[c], d)) if c in mapa else None
            if r is None:
                zamkniete.add(c)
                zmiana = True
                linie.append("%s: poza nagraniem, łańcuch kończy się" % nazwa)
                continue
            ujawnione[nazwa] = odkryty(r, loop.ROOT if d == 1 else "%d.%d" % (c, d - 1))
            zmiana = True
            sv = loop.s_v(r) or 0.0
            przed = baseline if d == 1 else (loop.s_v(ujawnione["%d.%d" % (c, d - 1)]) or 0.0)
            linie.append("%s: s_v=%.4f delta=%+.4f koszt=%.2fh" % (nazwa, sv, sv - przed, drzewo.koszt_h(r)))
        if not zmiana:
            break
        paczki.append(wezly)
        slad.append("runda %d: %s" % (len(paczki), " | ".join(linie)))
    V = drzewo.wartosc(paczki, ujawnione, beta)
    T = drzewo.czas_h(paczki, ujawnione)
    najlepszy = max((loop.s_v(r) or 0.0 for r in ujawnione.values()), default=0.0)
    slad.append("koniec (%s): rund=%d ujawnionych=%d/%d najlepszy s_v=%.4f T=%.2fh V=%.4f" %
                (powod, len(paczki), len(ujawnione), len(nagrane), najlepszy, T, V))
    return {"V": V, "T_h": T, "rundy": len(paczki), "ujawnione": len(ujawnione), "najlepszy": najlepszy,
            "powod": powod, "slad": slad}


def zamkniete_drzewa(base):
    """Numery drzew z zamknięciem (`koniec`), rosnąco."""
    d = os.path.join(base, loop.TREES)
    nums = sorted(int(f[:-5]) for f in os.listdir(d) if f.endswith(".json") and f[:-5].isdigit()) \
        if os.path.isdir(d) else []
    return [n for n in nums if (drzewo.read_state(base, n) or {}).get("koniec")]


def odtworz_wszystkie(base, sciezka):
    """Wszystkie zamknięte drzewa pod polityką z pliku `sciezka`. Zwraca {"V": średnia, "drzewa": {t: wynik}}."""
    policy, digest = drzewo.load_file(sciezka)
    cfg, baseline = drzewo.config(base), drzewo.baseline(base)
    drzewa = {t: odtworz(policy, loop.load_tree(base, t), cfg, baseline) for t in zamkniete_drzewa(base)}
    V = sum(w["V"] for w in drzewa.values()) / len(drzewa) if drzewa else 0.0
    return {"skrot": digest, "V": V, "drzewa": {str(t): w for t, w in drzewa.items()}}


def odtworz_bezpiecznie(base, sciezka):
    """Odtworzenie w osobnym procesie, bez środowiska (sekrety) i z limitem czasu. Kod polityki pisał model,
    więc nie ma wejść w procesy ze zmiennymi. Dwa przebiegi muszą dać to samo (polityka deterministyczna).
    Zwraca wynik albo {"blad": opis}."""
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT") if k in os.environ}
    wyniki = []
    for _ in range(2):
        try:
            p = subprocess.run([sys.executable, os.path.abspath(__file__), "odtworz", sciezka], cwd=base, env=env,
                               capture_output=True, text=True, timeout=LIMIT_S)
        except subprocess.TimeoutExpired:
            return {"blad": "odtworzenie trwa dłużej niż %d s" % LIMIT_S}
        if p.returncode != 0:
            return {"blad": (p.stderr.strip().splitlines() or ["kod wyjścia %d" % p.returncode])[-1][:300]}
        wyniki.append(json.loads(p.stdout))
    if wyniki[0] != wyniki[1]:
        return {"blad": "dwa odtworzenia dały różne wyniki: polityka nie jest deterministyczna"}
    return wyniki[0]


# ---------------------------------------------------------------- wersje w archiwum przebiegu

def rev_dir(run, m):
    return os.path.join(run, "history", "r%04d" % m)


def zapisz_rewizje(run, m, plik, wynik):
    """Wersja `m` w archiwum przebiegu: kod, wynik i ślady odtworzenia (jeden plik na drzewo)."""
    d = rev_dir(run, m)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(d, "slady"))
    if os.path.exists(plik):
        shutil.copy(plik, os.path.join(d, "policy.py"))
    else:
        with open(os.path.join(d, "policy.py"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# sesja nie zostawiła policy.py\n")
        wynik = {"blad": "brak policy.py po sesji"}
    drzewa = wynik.get("drzewa", {})
    loop.write_json(os.path.join(d, "wynik.json"), {
        "rewizja": m, "V": wynik.get("V"), "skrot": wynik.get("skrot"), "blad": wynik.get("blad"),
        "V_drzewa": {t: round(w["V"], 6) for t, w in drzewa.items()},
        "T_h_drzewa": {t: round(w["T_h"], 2) for t, w in drzewa.items()}})
    for t, w in drzewa.items():
        with open(os.path.join(d, "slady", "%s.txt" % t), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(w["slad"]) + "\n")


def wczytaj_wyniki(run):
    out = {}
    base = os.path.join(run, "history")
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        out[int(name[1:])] = loop.read_json(os.path.join(base, name, "wynik.json"))
    return out


def najlepsza(wyniki):
    """Indeks wersji z największym V; remis zostawia wcześniejszą, a więc bieżącą (V^{m*} >= V^0)."""
    best = 0
    for m, w in sorted(wyniki.items()):
        if w.get("V") is not None and w["V"] > wyniki[best]["V"]:
            best = m
    return best


# ---------------------------------------------------------------- co widzi sesja meta

def manifest(base, t):
    """Struktura i wyniki drzewa bez kodu i bez notatek węzłów."""
    st, recs = drzewo.read_state(base, t), loop.load_tree(base, t)
    wezly = [{"wezel": n, "rodzic": None if r["rodzic"] == loop.ROOT else r["rodzic"],
              "kolejnosc": r["kolejnosc"], "s_v": loop.s_v(r) or 0.0, "koszt_h": round(drzewo.koszt_h(r), 3)}
             for n, r in sorted(recs.items(), key=lambda kv: kv[1]["kolejnosc"]) if r.get("stan") == "oceniony"]
    return {"drzewo": t, "paczki": st["paczki"], "koniec": st["koniec"], "wezly": wezly}


def przygotuj_meta(base, run, meta):
    """Katalog sesji `m`: kandydat do edycji (najlepsza dotąd wersja), archiwum wersji z V i śladami,
    baseline, manifesty drzew i opis zadania. Nic więcej."""
    shutil.rmtree(meta, ignore_errors=True)
    os.makedirs(os.path.join(meta, "drzewa"))
    wyniki = wczytaj_wyniki(run)
    shutil.copy(os.path.join(rev_dir(run, najlepsza(wyniki)), "policy.py"), os.path.join(meta, "policy.py"))
    shutil.copy(os.path.join(base, OPIS), os.path.join(meta, "ZADANIE.md"))
    cfg = drzewo.config(base)
    loop.write_json(os.path.join(meta, "konfiguracja.json"), {k: cfg[k] for k in ("W", "K", "beta")})
    loop.write_json(os.path.join(meta, "baseline.json"), {"s_v": drzewo.baseline(base)})
    for t in zamkniete_drzewa(base):
        loop.write_json(os.path.join(meta, "drzewa", str(t), "manifest.json"), manifest(base, t))
    arch = os.path.join(base, HISTORIA)
    for faza in sorted(os.listdir(arch)) if os.path.isdir(arch) else []:
        shutil.copytree(os.path.join(arch, faza), os.path.join(meta, "history", faza))
    shutil.copytree(os.path.join(run, "history"), os.path.join(meta, "history", "biezaca"))


# ---------------------------------------------------------------- wybór, wdrożenie, podsumowanie

def tabela_wezlow(recs):
    lines = ["| węzeł | rodzic | s_v | sesja min | oczekiwanie min | sesji (po turach / po limicie) | tury | sym min | seria min |",
             "|---|---|---|---|---|---|---|---|---|"]
    for n, r in sorted(recs.items(), key=lambda kv: kv[1]["kolejnosc"]):
        o = r.get("oceny") or {}
        wznow = len(r.get("sesje", [])) - 1
        tury = r.get("kontynuacje_tur", 0)
        lines.append("| %s | %s | %s | %.1f | %.1f | %d (%d / %d) | %d | %s | %s |" % (
            n, r["rodzic"], loop.fmt(loop.s_v(r)), r["koszt"]["minuty"], r["oczekiwanie_min"], len(r.get("sesje", [])),
            tury, max(0, wznow - tury), r["koszt"]["tury"], o.get("czas_sym_min", "—"), o.get("czas_serii_min", "—")))
    return lines


def tabela_postepu(base, t):
    """Po rundzie: najlepszy dotąd s_v, narastające T i V (tak jak liczy je harmonogram)."""
    st, recs = drzewo.read_state(base, t), loop.load_tree(base, t)
    beta = drzewo.config(base)["beta"]
    lines = ["| runda | węzły | najlepszy s_v | T h | V |", "|---|---|---|---|---|"]
    for i in range(1, len(st["paczki"]) + 1):
        p = st["paczki"][:i]
        ocenione = {n: recs[n] for b in p for n in b if n in recs and recs[n].get("stan") == "oceniony"}
        best = max((loop.s_v(r) or 0.0 for r in ocenione.values()), default=0.0)
        lines.append("| %d | %s | %.4f | %.2f | %.4f |" % (i, " ".join(st["paczki"][i - 1]), best,
                                                           drzewo.czas_h(p, recs), drzewo.wartosc(p, ocenione, beta)))
    return lines


def podsumowanie(base, t, wyniki, wybrana):
    st, recs = drzewo.read_state(base, t), loop.load_tree(base, t)
    k = st["koniec"]
    out = ["## Faza offline po drzewie %s" % t, "",
           "Zamknięcie: %s, T = %s h, V = %s." % (k["powod"], k["T_h"], k["V"]), "",
           "### Wersje polityki", "", "| wersja | V | skrót | V per drzewo | błąd |", "|---|---|---|---|---|"]
    for m, w in sorted(wyniki.items()):
        out.append("| r%04d%s | %s | %s | %s | %s |" % (
            m, " (wybrana)" if m == wybrana else "", "—" if w["V"] is None else "%.4f" % w["V"], w.get("skrot") or "—",
            ", ".join("%s: %.3f" % kv for kv in w["V_drzewa"].items()) or "—", w.get("blad") or ""))
    out += ["", "Zmiana polityki: **%s**." % ("tak" if wybrana else "nie (zostaje bieżąca)"), "",
            "### Odtworzenie = żywe drzewo", ""]
    digest, tw0 = wyniki[0]["skrot"], wyniki[0]["V_drzewa"]   # polityka sprzed wdrożenia
    for n in zamkniete_drzewa(base):
        s = drzewo.read_state(base, n)
        if s["polityka"] != digest:
            out.append("- drzewo %d: prowadzone inną polityką (%s), pominięte" % (n, s["polityka"]))
        else:
            v = tw0.get(str(n))
            ok = v is not None and math.isclose(v, s["koniec"]["V"], abs_tol=1e-5)
            out.append("- drzewo %d: żywe V = %s, odtworzone V = %s: **%s**" % (n, s["koniec"]["V"], v, "zgodne" if ok else "ROZBIEŻNE"))
    out += ["", "### Drzewo %s: postęp" % t, ""] + tabela_postepu(base, t)
    out += ["", "### Drzewo %s: czasy węzłów i parkowania" % t, ""] + tabela_wezlow(recs)
    return "\n".join(out) + "\n"


def wdroz(base, run, t, wybrana):
    """Archiwum fazy zawsze, `policy.py` tylko gdy wygrała wersja inna niż bieżąca. Commituje workflow."""
    cel = os.path.join(base, HISTORIA, "faza-%s" % t)
    shutil.rmtree(cel, ignore_errors=True)
    for name in sorted(os.listdir(os.path.join(run, "history"))):
        src = os.path.join(run, "history", name)
        os.makedirs(os.path.join(cel, name))
        for f in ("policy.py", "wynik.json"):
            shutil.copy(os.path.join(src, f), os.path.join(cel, name, f))
    if wybrana:
        shutil.copy(os.path.join(rev_dir(run, wybrana), "policy.py"), os.path.join(base, drzewo.POLICY))


# ---------------------------------------------------------------- main

def main(argv):
    cmd, args = argv[1], argv[2:]
    base = os.getcwd()
    if cmd == "ile":
        print(drzewo.config(base)["M"])
        return 0
    if cmd == "odtworz":   # wewnętrzne: proces potomny, wynik na stdout
        try:
            print(json.dumps(odtworz_wszystkie(base, args[0]), sort_keys=True))
        except Exception as e:   # noqa: BLE001 — każda wada polityki to informacja dla sesji, nie awaria jobu
            print("%s: %s" % (type(e).__name__, e), file=sys.stderr)
            return 1
        return 0
    if cmd == "init":   # bieżąca polityka jako wersja 0
        t, run = args
        shutil.rmtree(run, ignore_errors=True)
        zapisz_rewizje(run, 0, os.path.join(base, drzewo.POLICY), odtworz_bezpiecznie(base, os.path.join(base, drzewo.POLICY)))
        if wczytaj_wyniki(run)[0]["blad"]:
            raise SystemExit("bieżąca polityka nie przechodzi odtworzenia: " + wczytaj_wyniki(run)[0]["blad"])
        return 0
    if cmd == "meta":
        m, run, meta = args
        przygotuj_meta(base, run, meta)
        return 0
    if cmd == "wynik":
        m, run, meta = args
        plik = os.path.join(meta, "policy.py")
        zapisz_rewizje(run, int(m), plik, odtworz_bezpiecznie(base, os.path.abspath(plik)))
        return 0
    if cmd == "wybierz":
        t, run = args
        wyniki = wczytaj_wyniki(run)
        wybrana = najlepsza(wyniki)
        wdroz(base, run, t, wybrana)
        print(podsumowanie(base, t, wyniki, wybrana))
        return 0
    raise SystemExit("nieznane polecenie: " + cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
