#!/usr/bin/env python3
"""Kalibracja symulatora do logów mostu: miary rozjazdu, bramka naprawy, wyzwalacze utrzymania.

Biegnie z checkoutu gałęzi domyślnej; kod symulatora bierze z `--kod` (kopia z naprawą) albo
z tego checkoutu. Agent utrzymania nie zmienia tego pliku ani `config.json`: przy przyjęciu naprawy
odrzucane są wszystkie ścieżki poza `dozwolone()`.

Dwie miary, obie liczone z `moves.jsonl` mostu (stan, tacka, ruch, licznik apki przed ruchem):
- tempo punktów: te same ruchy zagrane w symulatorze dają sumę punktów w ±`tempo` od przyrostu licznika apki;
- rozkład klocków: tylko odczyt mostu (`nieznane` ≤ `nieznane_max`); χ² tacek z logu vs generator symulatora jest podawany
  informacyjnie, bo prawdziwa gra losuje klocki zależnie od rundy i stały generator nigdy go nie zgodzi (p≈0 na każdej świeżej serii).

Podpolecenia: rozjazd, zestaw, bramka, wyzwalacz, hashe, sciezki, dozwolone.
"""
import argparse
import gzip
import importlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import ocena  # noqa: E402

ZESTAW = HERE / "kalibracja" / "zestaw"
SIM = ("board", "game", "generator", "pieces", "scoring")
INFRA = re.compile(r"brak pomiar\.json|adb|device|offline|emulator|INSTALL", re.I)


def cfg():
    return ocena.config()


# ---------------------------------------------------------------- logi i symulator

def sim(kod):
    """Moduły symulatora z katalogu `kod`, nie z checkoutu ewaluatora."""
    for name in SIM:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(kod))
    try:
        return SimpleNamespace(**{n: importlib.import_module(n) for n in SIM})
    finally:
        sys.path.remove(str(kod))


def wczytaj(path):
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def logi(root):
    """Lista partii (każda to lista wpisów ruchów) z `moves.jsonl` i `*.jsonl.gz` pod `root`."""
    root = Path(root) if root else None
    if not root or not root.is_dir():
        return []
    return [wczytaj(p) for p in sorted(list(root.rglob("moves.jsonl")) + list(root.rglob("*.jsonl.gz")))]


def klucz(shape):
    return tuple(tuple(int(c) for c in row) for row in shape)


def poza(mod):
    return {klucz(p.shape): p for p in mod.pieces.PIECE_POOL}


# ---------------------------------------------------------------- tempo punktów

def tempo(partie, mod, k):
    """Te same ruchy w symulatorze vs przyrost licznika apki na odcinkach między odczytami licznika (most czyta
    go co kilka ruchów). Licznik odczytany OCR-em bywa zły: odrzucamy przyrosty ujemne i większe niż `max_delta`
    na ruch; ruch i tak gramy, żeby combo się zgadzało. `pary` to liczba przyjętych odcinków."""
    pozy = poza(mod)
    app = symul = pary = 0
    for wpisy in partie:
        game = mod.game.Game(seed=0)
        start = None
        for a, b in zip(wpisy, wpisy[1:]):
            if a.get("score") is not None:
                start, zysk, ruchy = a["score"], 0, 0
            m = a.get("move")
            if m is None:
                continue
            game.board.grid = [row[:] for row in a["board"]]
            game.pieces = [None if s is None else pozy.get(klucz(s)) or mod.pieces.Piece(s, "?", -1) for s in a["tray"]]
            przed = game.score
            _, _, _, info = game.step((m["slot"], m["x"], m["y"]))   # zwracany przyrost to -5 przy końcu gry, więc różnica wyniku
            game.done = False
            if info == "wrong_placement":
                start = None   # odcinek z ruchem, którego symulator nie zagra, nie ma porównania
                continue
            if start is None:
                continue
            zysk += game.score - przed
            ruchy += 1
            sb = b.get("score")
            if sb is not None and 0 <= sb - start <= k["max_delta"] * ruchy:
                app += sb - start
                symul += zysk
                pary += 1
    ok = None if pary < k["min_pary"] or symul <= 0 else abs(app / symul - 1) <= k["tempo"]
    return {"app": app, "sym": symul, "stosunek": round(app / symul, 4) if symul > 0 else None, "pary": pary, "ok": ok}


# ---------------------------------------------------------------- rozkład klocków

def gamma_q(a, x):
    """Regularyzowana górna niepełna funkcja gamma Q(a, x); p-wartość χ² = Q(df/2, χ²/2)."""
    if x <= 0:
        return 1.0
    front = math.exp(-x + a * math.log(x) - math.lgamma(a))
    if x < a + 1:
        ap, s, d = a, 1.0 / a, 1.0 / a
        for _ in range(1000):
            ap += 1
            d *= x / ap
            s += d
            if abs(d) < abs(s) * 1e-15:
                break
        return max(0.0, 1.0 - front * s)
    tiny = 1e-300
    b = x + 1 - a
    c, d = 1 / tiny, 1 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return min(1.0, front * h)


def wzorzec(mod, n_tacek):
    """Rozkład klocków generatora symulatora, z losowania (działa dla każdej wersji generatora)."""
    gen = mod.generator.Generator(20240101)
    c = Counter(p.index for _ in range(n_tacek) for p in gen.next_pieces())
    total = sum(c.values())
    return {p.index: c[p.index] / total for p in mod.pieces.PIECE_POOL}


def kosze(p, n, minimum=5.0):
    """Poz o oczekiwanej liczbie < `minimum` zlewamy w jeden kosz (dołożony do najmniejszego, gdy wciąż za mały)."""
    duze = sorted((i for i in p if p[i] * n >= minimum), key=lambda i: p[i])
    male = [i for i in p if p[i] * n < minimum]
    out = [[i] for i in duze]
    if male:
        if sum(p[i] for i in male) * n >= minimum or not out:
            out.append(male)
        else:
            out[0] = out[0] + male
    return out


def klocki(partie, mod, k):
    pozy = poza(mod)
    licz, nieznane = Counter(), 0
    for wpisy in partie:
        poprzednia = None
        for e in wpisy:
            t = e.get("tray") or []
            if len(t) == 3 and all(s is not None for s in t) and t != poprzednia:   # nowa runda, nie powtórka po nieudanym ruchu
                for s in t:
                    piece = pozy.get(klucz(s))
                    if piece is None:
                        nieznane += 1
                    else:
                        licz[piece.index] += 1
            poprzednia = t
    n = sum(licz.values())
    out = {"n": n, "nieznane": nieznane, "chi2": None, "df": None, "p": None, "ok": None}
    if n < k["min_klockow"]:
        return out
    p = wzorzec(mod, k["wzorzec_tacek"])
    bins = kosze(p, n)
    chi2 = sum((sum(licz[i] for i in b) - n * sum(p[i] for i in b)) ** 2 / (n * sum(p[i] for i in b)) for b in bins)
    df = len(bins) - 1
    pv = gamma_q(df / 2, chi2 / 2)
    out.update(chi2=round(chi2, 2), df=df, p=round(pv, 4))
    out["ok"] = nieznane <= k["nieznane_max"] * (n + nieznane)
    return out


def mierz(partie, mod, k):
    t, kl = tempo(partie, mod, k), klocki(partie, mod, k)
    return {"partie": len(partie), "ruchy": sum(len(w) for w in partie), "tempo": t, "klocki": kl,
            "ok": t["ok"] is True and kl["ok"] is True}


def opis(nazwa, m):
    t, kl = m["tempo"], m["klocki"]
    return "- %s: %d partii, %d ruchów · tempo apka/sym = %s (%d par, %s) · klocki n=%d, χ²=%s df=%s p=%s nieznane=%d (%s)" % (
        nazwa, m["partie"], m["ruchy"], t["stosunek"], t["pary"], _ok(t["ok"]),
        kl["n"], kl["chi2"], kl["df"], kl["p"], kl["nieznane"], _ok(kl["ok"]))


def _ok(v):
    return {True: "w tolerancji", False: "POZA tolerancją", None: "brak danych"}[v]


# ---------------------------------------------------------------- odcinek na emulatorze

def most_zdrowy(wyjscie):
    """Odcinek na emulatorze: partia ma dojść do końca albo do limitu ruchów, nie paść z awarią/przerwaniem."""
    path = Path(wyjscie) / "pomiar.json"
    if not path.exists():
        return False, "brak pomiar.json"
    p = json.loads(path.read_text(encoding="utf-8"))
    if p.get("koniec") == "przegrana" or (p.get("koniec") == "przerwanie" and p.get("przyczyna") == "limit ruchów"):
        return True, p["koniec"]
    return False, "%s: %s" % (p.get("koniec"), p.get("przyczyna"))


def bramka(kod, odcinek, zestaw=None):
    """Kryterium iteracji: zestaw kontrolny w tolerancji (twardo: brak danych = porażka) i odcinek na emulatorze
    ze zdrowym mostem; miary odcinka liczą się tylko, gdy ma dość danych (krótka przegrana je zwykle nie ma)."""
    k = cfg()["kalibracja"]
    mod = sim(kod)
    z = mierz(logi(zestaw or ZESTAW), mod, k)
    o = mierz(logi(odcinek), mod, k)
    zdrowy, jak = most_zdrowy(odcinek)
    powody = []
    if not z["partie"]:
        powody.append("pusty zestaw kontrolny")
    if not z["ok"]:
        powody.append("zestaw kontrolny poza tolerancją albo bez danych")
    if not zdrowy:
        powody.append("most: " + jak)
    if o["tempo"]["ok"] is False or o["klocki"]["ok"] is False:
        powody.append("odcinek poza tolerancją")
    return {"ok": not powody, "powody": powody, "zestaw": z, "odcinek": dict(o, most=jak)}


# ---------------------------------------------------------------- wyzwalacze

def wyzwalacz(seria, rozjazd, proba):
    """Co dalej po serii: `brak` | `ponow <json partii>` | `utrzymanie <powod>`.
    Awaria infrastruktury z dowodem w pomiarze to ponowienie bez agenta; reszta unieważnień otwiera utrzymanie."""
    c = cfg()
    wazne, niewazne = ocena.zlicz_seria(seria, c)
    if not wazne and not niewazne:   # seria nie zostawiła ani jednej partii: padł job, nie gra
        niewazne = [{"partia": k, "przyczyna": "brak pomiar.json"} for k in range(1, c["partie"] + 1)]
    if niewazne:
        infra = all(INFRA.search(n.get("przyczyna") or "") for n in niewazne)
        if infra and proba < c["kalibracja"]["ponowienia"]:
            return "ponow " + json.dumps(sorted(n["partia"] for n in niewazne))
        return "utrzymanie most"
    return "brak" if rozjazd["ok"] else "utrzymanie rozjazd"


# ---------------------------------------------------------------- zestaw, hash, ścieżki

def zapisz_zestaw(seria, nazwa, out, k):
    """Logi serii w zwartej postaci (pierwsze `zestaw_ruchy` ruchów każdej partii) jako część zestawu kontrolnego."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for i, wpisy in enumerate(logi(seria), 1):
        slim = [{f: e[f] for f in ("n", "board", "tray", "move", "score") if f in e} for e in wpisy[:k["zestaw_ruchy"]]]
        with open(out / ("%s-%d.jsonl.gz" % (nazwa, i)), "wb") as raw, gzip.GzipFile("", "wb", fileobj=raw, mtime=0) as gz:
            gz.write(("\n".join(json.dumps(e, separators=(",", ":")) for e in slim) + "\n").encode())


def hashe(kod):
    """Obie części hasha ewaluatora dla kodu w `kod` (rozdania drzewa pominięte: porównujemy tylko pliki)."""
    stary, ocena.ROOT = ocena.ROOT, Path(kod).resolve()
    try:
        return {"sym": ocena.hash_sym("-"), "most": ocena.hash_most()}
    finally:
        ocena.ROOT = stary


def sciezki_naprawy():
    """Jedyne ścieżki, które agent utrzymania może zmienić: pliki ewaluatora z nakładki i ich testy."""
    c = cfg()
    return sorted({p for grupa in c["tylko_do_odczytu"].values() for p in grupa} | set(c["utrzymanie"]["dodatkowe"]))


def dozwolone(sciezki):
    """Ścieżki spoza `sciezki_naprawy`, które naprawa zmieniła (puste = wszystko w porządku)."""
    ok = set(sciezki_naprawy())
    return [p for p in sciezki if p not in ok]


# ---------------------------------------------------------------- main

def _zapisz(path, obj):
    if path:
        Path(path).write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")


def main(argv):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("rozjazd")
    p.add_argument("--seria", required=True)
    p.add_argument("--kod", default=str(ROOT))
    p.add_argument("--out")
    p.add_argument("--podsumowanie")
    p = sub.add_parser("zestaw")
    p.add_argument("--seria", required=True)
    p.add_argument("--nazwa", required=True)
    p.add_argument("--out", default=str(ZESTAW))
    p = sub.add_parser("bramka")
    p.add_argument("--kod", required=True)
    p.add_argument("--odcinek", required=True)
    p.add_argument("--out")
    p = sub.add_parser("wyzwalacz")
    p.add_argument("--seria", required=True)
    p.add_argument("--rozjazd", required=True)
    p.add_argument("--proba", type=int, default=1)
    sub.add_parser("hashe").add_argument("--kod", default=str(ROOT))
    sub.add_parser("dozwolone")
    sub.add_parser("sciezki")
    a = ap.parse_args(argv[1:])

    if a.cmd == "rozjazd":
        m = mierz(logi(a.seria), sim(a.kod), cfg()["kalibracja"])
        _zapisz(a.out, m)
        if a.podsumowanie:
            with open(a.podsumowanie, "a", encoding="utf-8") as fh:
                fh.write("### Rozjazd symulatora\n\n" + opis("seria", m) + "\n")
        print(opis("seria", m))
        return 0 if m["ok"] else 1
    if a.cmd == "zestaw":
        zapisz_zestaw(a.seria, a.nazwa, a.out, cfg()["kalibracja"])
    elif a.cmd == "bramka":
        b = bramka(a.kod, a.odcinek)
        _zapisz(a.out, b)
        print(opis("zestaw", b["zestaw"]) + "\n" + opis("odcinek", b["odcinek"]))
        print("bramka: %s%s" % ("przeszła" if b["ok"] else "NIE przeszła", "" if b["ok"] else " (" + "; ".join(b["powody"]) + ")"))
        return 0 if b["ok"] else 1
    elif a.cmd == "wyzwalacz":
        print(wyzwalacz(a.seria, json.loads(Path(a.rozjazd).read_text(encoding="utf-8")), a.proba))
    elif a.cmd == "hashe":
        print(json.dumps(hashe(a.kod)))
    elif a.cmd == "sciezki":
        print(*sciezki_naprawy(), sep="\n")
    elif a.cmd == "dozwolone":
        zle = dozwolone(line.strip() for line in sys.stdin if line.strip())
        for z in zle:
            print(z)
        return 1 if zle else 0
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv))
