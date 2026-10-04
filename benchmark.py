"""
Benchmark bota Block Blast — narzędzie uruchamialne.

Realizuje definicję z #8: dwa zestawy po N seedów (stały + rotowany), eps = 0,
twardy sufit ruchów, trójstronny pomiar kandydat/poprzednik/rekordzista przez
TEN SAM, aktualny symulator, parowanie na wspólnych seedach.

    python benchmark.py --candidate greedy --previous random --issue 17
    python benchmark.py --candidate model/model.pth --previous w-abc/model.pth --issue 17

Wynik: maszynowy rekord `bench/<sha>.json` + czytelne podsumowanie na stdout.
Próg jest etykietą dla orchestratora, nie bramką — benchmark nigdy nie kończy
się kodem błędu z powodu regresji.
"""
import argparse
import hashlib
import json
import os
import random
import statistics
import subprocess
import sys
import time

from game import Game
from policies import GreedyPolicy, ModelPolicy, RandomPolicy

CONFIG_PATH = "bench/config.json"
HASHED_SOURCES = ["scoring.py", "pieces.py"]

STATUS_OK = "ok"
STATUS_BLOCKED = "blocked"


class ArmUnavailable(Exception):
    """Zażądano ramienia pomiaru, którego nie da się załadować (#21: kończy `blocked`)."""


def load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def fixed_seeds(config):
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        seeds = json.load(fh)
    return seeds[: config["n_seeds"]]


def rotated_seeds(config, issue):
    """Powtarzalny dla audytu, ale niemożliwy do dostrojenia przed przydzieleniem issue."""
    rng = random.Random(f"{config['rotated_seed_salt']}:{issue}")
    return rng.sample(range(1, 2**31 - 1), config["n_seeds"])


def source_hashes():
    out = {}
    for name in HASHED_SOURCES:
        with open(name, "rb") as fh:
            out[name] = hashlib.sha256(fh.read()).hexdigest()[:16]
    return out


def current_sha():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "nogit"


def is_dirty():
    """Czy mierzony kod różni się od HEAD.

    Bez tego rekord `bench/<sha>.json` przypisałby pomiar do commita, którego
    wcale nie mierzył — w pętli autonomicznej to cichy fałsz w szeregu.
    """
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            text=True, stderr=subprocess.DEVNULL,
        )
        return bool(out.strip())
    except Exception:
        return True


def build_policy(spec, config):
    """`random`, `greedy` albo ścieżka do wag."""
    if spec == "random":
        return RandomPolicy(seed=config["torch_seed"])
    if spec == "greedy":
        return GreedyPolicy()

    if not os.path.exists(spec):
        raise ArmUnavailable("brak pliku wag: " + spec)
    try:
        import torch

        from agent import Agent

        torch.manual_seed(config["torch_seed"])
        agent = Agent()
        agent.model.load_state_dict(torch.load(spec, map_location=agent.device))
        agent.model.eval()
        return ModelPolicy(agent, os.path.basename(spec))
    except ArmUnavailable:
        raise
    except Exception as exc:
        # Najrealniejsze zagrożenie z #21: wagi istnieją, ale nie pasują do architektury.
        raise ArmUnavailable("wagi " + spec + " nieładowalne: " + str(exc)) from exc


def play_game(policy, seed, move_cap):
    game = Game(seed=seed)
    policy.reset(seed)
    while not game.done:
        if game.placements >= move_cap:
            return game.score, game.placements, True
        actions = game.available_actions()
        if not actions:
            break
        game.step(policy.act(game, actions))
    return game.score, game.placements, False


def run_set(policy, seeds, move_cap):
    scores, survivals, capped = [], [], 0
    for seed in seeds:
        score, placements, was_capped = play_game(policy, seed, move_cap)
        scores.append(score)
        survivals.append(placements)
        capped += was_capped
    return {
        "mean": round(statistics.mean(scores), 2),
        "median": round(statistics.median(scores), 2),
        "p10": round(percentile(scores, 10), 2),
        "survival_mean": round(statistics.mean(survivals), 2),
        "capped_pct": round(100.0 * capped / len(seeds), 2),
        "scores": scores,
    }


def percentile(values, pct):
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct / 100.0
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def paired_delta(candidate_scores, baseline_scores, threshold_pct):
    """Różnica sparowana na wspólnych seedach + etykieta progu (nieblokująca)."""
    diffs = [c - b for c, b in zip(candidate_scores, baseline_scores)]
    base_mean = statistics.mean(baseline_scores)
    mean_diff = statistics.mean(diffs)
    pct = 100.0 * mean_diff / base_mean if base_mean else 0.0
    if pct >= threshold_pct:
        label = "poprawa"
    elif pct <= -threshold_pct:
        label = "regresja"
    else:
        label = "bez zmian"
    return {
        "mean_diff": round(mean_diff, 2),
        "pct": round(pct, 2),
        "sd_diff": round(statistics.pstdev(diffs), 2) if len(diffs) > 1 else 0.0,
        "label": label,
    }


def measure_arm(policy, seeds_fixed, seeds_rotated, move_cap):
    fixed = run_set(policy, seeds_fixed, move_cap)
    rotated = run_set(policy, seeds_rotated, move_cap)
    base = fixed["mean"]
    gap = round(100.0 * (base - rotated["mean"]) / base, 2) if base else 0.0
    return {
        "policy": policy.name,
        "fixed": fixed,
        "rotated": rotated,
        # Rozjazd stały/rotowany = miara przetrenowania na benchmark (#8).
        "overfit_gap_pct": gap,
    }


def strip_scores(record):
    """Surowe serie zostają poza rekordem — rekord ma być czytelny, nie pełny."""
    for arm in record["arms"].values():
        for key in ("fixed", "rotated"):
            arm[key].pop("scores", None)
    return record


def render_markdown(record):
    lines = ["## Benchmark — `" + record["sha"][:12] + "`", ""]
    if record.get("dirty"):
        lines += ["> Mierzony kod **różni się od HEAD** — pomiar nie opisuje tego commita.", ""]
    if record["status"] == STATUS_BLOCKED:
        lines += ["**status: blocked** — " + str(record["blocked_reason"]), ""]

    cfg = record["config"]
    lines += [
        "N = {0} seedów na zestaw · sufit {1} ruchów · eps = {2} · próg ±{3}% (nieblokujący)".format(
            cfg["n_seeds"], cfg["move_cap"], cfg["epsilon"], cfg["threshold_pct"]
        ),
        "",
        "| ramię | polityka | średnia | mediana | p10 | przeżycie | % uciętych | rozjazd stały/rotowany |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, arm in record["arms"].items():
        f = arm["fixed"]
        lines.append(
            "| {0} | `{1}` | {2} | {3} | {4} | {5} | {6}% | {7}% |".format(
                name, arm["policy"], f["mean"], f["median"], f["p10"],
                f["survival_mean"], f["capped_pct"], arm["overfit_gap_pct"],
            )
        )

    if record["deltas"]:
        lines += [
            "",
            "| porównanie (sparowane, zestaw stały) | Δ średniej | Δ % | etykieta |",
            "|---|---|---|---|",
        ]
        for name, d in record["deltas"].items():
            lines.append(
                "| {0} | {1} | {2}% | **{3}** |".format(name, d["mean_diff"], d["pct"], d["label"])
            )

    hashes = " · ".join("`" + k + "`=" + v for k, v in record["source_hashes"].items())
    lines += ["", "Hash symulatora: " + hashes, "Czas pomiaru: {0} s".format(record["duration_s"])]
    return "\n".join(lines)


def main(argv=None):
    # Raport jest po polsku i zawiera Δ — konsola Windows domyślnie jest cp1250
    # i wywaliłaby cały przebieg na samym drukowaniu wyniku.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description="Benchmark bota Block Blast")
    parser.add_argument("--candidate", required=True, help="random | greedy | ścieżka do wag")
    parser.add_argument("--previous", help="ramię odniesienia: poprzednik")
    parser.add_argument("--record", help="ramię odniesienia: rekordzista")
    parser.add_argument("--issue", type=int, required=True, help="numer issue zadania-benchmarku")
    parser.add_argument("--config", default=CONFIG_PATH)
    parser.add_argument("--n-seeds", type=int, help="nadpisuje n_seeds z konfiguracji")
    parser.add_argument("--out", help="ścieżka rekordu; domyślnie bench/<sha>.json")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.n_seeds:
        config["n_seeds"] = args.n_seeds

    sha = current_sha()
    dirty = is_dirty()
    record = {
        "sha": sha,
        "dirty": dirty,
        "issue": args.issue,
        "status": STATUS_OK,
        "blocked_reason": None,
        # Bez skopiowanych parametrów porównanie dwóch przebiegów o różnych
        # progach byłoby niejawnym kłamstwem (#8).
        "config": config,
        "source_hashes": source_hashes(),
        "arms": {},
        "deltas": {},
        "duration_s": 0.0,
    }

    seeds_f = fixed_seeds(config)
    seeds_r = rotated_seeds(config, args.issue)
    requested = [
        ("candidate", args.candidate),
        ("previous", args.previous),
        ("record", args.record),
    ]

    started = time.time()
    for name, spec in requested:
        if spec is None:
            continue
        try:
            policy = build_policy(spec, config)
        except ArmUnavailable as exc:
            # Rekordzista albo poprzednik zaginął: raport wychodzi, decyzję
            # podejmuje orchestrator (#21).
            record["status"] = STATUS_BLOCKED
            record["blocked_reason"] = "ramię `" + name + "`: " + str(exc)
            continue
        record["arms"][name] = measure_arm(policy, seeds_f, seeds_r, config["move_cap"])

    if "candidate" in record["arms"]:
        cand = record["arms"]["candidate"]["fixed"]["scores"]
        for name in ("previous", "record"):
            if name in record["arms"]:
                record["deltas"]["kandydat vs " + name] = paired_delta(
                    cand, record["arms"][name]["fixed"]["scores"], config["threshold_pct"]
                )

    record["duration_s"] = round(time.time() - started, 1)
    strip_scores(record)

    out_path = args.out or ("bench/" + sha + ("-dirty" if dirty else "") + ".json")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, ensure_ascii=False)

    print(render_markdown(record))
    print("\nRekord: " + out_path, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
