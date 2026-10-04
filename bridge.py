"""
Most do oryginału (#18): zrzut ekranu -> stan -> ruch -> przeciągnięcie -> potwierdzenie.

Działa na emulatorze w Actions (ekran 320x640). Stan planszy i trzech klocków
czytany z pikseli, ruch wybiera polityka zachłanna z benchmarku, wykonanie przez
`adb shell input motionevent`. Każdy ruch trafia do bridge-out/moves.jsonl
(stan, trójka, ruch, wynik — wejście z #9 dla dopasowania symulatora).

Geometria zmierzona na zrzutach z sondy #14 — aktualizacja gry może ją zepsuć.
"""
import io
import json
import os
import subprocess
import sys
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw

from board import Board
from pieces import Piece
from policies import GreedyPolicy

OUT = "bridge-out"
PACKAGE = "com.block.juggle"
SCREEN = (320, 640)
BOARD_X, BOARD_Y, CELL = 17, 136, 35.6
TRAY_Y0, TRAY_Y1, TRAY_CELL = 440, 585, 16
SCORE_BOX = (60, 70, 260, 130)
FRAMES = 3
DRAG_GAIN = 1.5  # zmierzone: klocek przesuwa się 1,5 px na 1 px palca
LIFT = 80.6  # środek podniesionego klocka jest tyle px nad środkiem klocka na tacce


def adb(*args):
    return subprocess.run(["adb", *args], check=True, capture_output=True).stdout


def touch(action, x, y):
    adb("shell", "input", "motionevent", action, str(int(x)), str(int(y)))


def screenshot():
    img = np.asarray(Image.open(io.BytesIO(adb("exec-out", "screencap", "-p"))).convert("RGB"))
    assert img.shape[1::-1] == SCREEN, f"ekran {img.shape[1::-1]}, oczekiwano {SCREEN}"
    return img.astype(int)


def in_game():
    return PACKAGE in adb("shell", "dumpsys", "window").decode(errors="replace").split("mCurrentFocus", 1)[-1][:200]


def settled_state():
    """Stan z kilku klatek: animacja tutorialu przesłania pola i tackę tylko chwilowo.

    Pole planszy zajęte, jeśli klocek widać na którejkolwiek klatce (duch podpowiedzi
    nigdy nie przechodzi is_block). Tacka: najczęstszy odczyt.
    """
    frames = []
    for _ in range(FRAMES):
        frames.append(screenshot())
        time.sleep(0.25)
    grids = [read_board(f) for f in frames]
    grid = [[max(g[r][c] for g in grids) for c in range(8)] for r in range(8)]
    trays = [read_tray(f) for f in frames]
    keys = [json.dumps([s[0] if s else None for s in t]) for t in trays]
    tray = trays[max(range(FRAMES), key=keys.count)]
    return frames[-1], grid, tray


def stable_state(tries=6):
    """Czeka, aż dwa kolejne odczyty będą identyczne: czyszczenie linii i licznik wyniku są animowane."""
    prev = None
    for _ in range(tries):
        img, grid, tray = settled_state()
        key = json.dumps([grid, [s[0] if s else None for s in tray]])
        if key == prev:
            break
        prev = key
    return img, grid, tray


def is_block(img):
    """Kolor klocka: nasycony i jasny. Tło, puste pola, duch podpowiedzi i dłoń tutorialu nie przechodzą."""
    return ((img.max(axis=-1) - img.min(axis=-1)) >= 100) & (img.max(axis=-1) >= 150)


def read_board(img):
    grid = [[0] * 8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            x, y = cell_center(c, r)
            patch = img[int(y) - 5:int(y) + 6, int(x) - 5:int(x) + 6].reshape(-1, 3).mean(axis=0)
            grid[r][c] = int(is_block(patch))
    return grid


def read_tray(img):
    """Trzy sloty: (kształt, środek w px) albo None, gdy slot pusty."""
    mask = is_block(img[TRAY_Y0:TRAY_Y1])
    slots = []
    for s in range(3):
        x0, x1 = s * SCREEN[0] // 3, (s + 1) * SCREEN[0] // 3
        ys, xs = np.nonzero(mask[:, x0:x1])
        if len(xs) < 20:
            slots.append(None)
            continue
        top, left = ys.min() + TRAY_Y0, xs.min() + x0
        h = max(1, round((ys.max() - ys.min() + 1) / TRAY_CELL))
        w = max(1, round((xs.max() - xs.min() + 1) / TRAY_CELL))
        step_y = (ys.max() - ys.min() + 1) / h
        step_x = (xs.max() - xs.min() + 1) / w
        shape = [[int(is_block(img[int(top + (i + .5) * step_y), int(left + (j + .5) * step_x)]))
                  for j in range(w)] for i in range(h)]
        center = (left + (xs.max() - xs.min()) / 2, top + (ys.max() - ys.min()) / 2)
        slots.append((shape, center))
    return slots


def read_score(img):
    """OCR wyniku przez tesseract; None, gdy się nie da."""
    x0, y0, x1, y1 = SCORE_BOX
    crop = img[y0:y1, x0:x1]
    bw = np.where(crop.min(axis=2) > 170, 0, 255).astype(np.uint8)
    path = os.path.join(OUT, "_score.png")
    Image.fromarray(bw).resize(((x1 - x0) * 3, (y1 - y0) * 3)).save(path)
    try:
        run = subprocess.run(["tesseract", path, "stdout", "--psm", "7", "-c",
                              "tessedit_char_whitelist=0123456789"], capture_output=True, text=True)
        text = run.stdout.strip()
        if not text:
            print("OCR:", run.stderr.strip()[:200], flush=True)
        return int(text) if text else None
    except (OSError, ValueError):
        return None


def cell_center(c, r):
    return BOARD_X + (c + .5) * CELL, BOARD_Y + (r + .5) * CELL


def legal_moves(board, pieces):
    return [(i, x, y) for i, p in enumerate(pieces) if p is not None
            for y in range(8) for x in range(8) if board.can_place_piece(p, x, y)]


def simulate(board, piece, x, y):
    after = board.copy()
    after.place_piece(piece, x, y)
    after.clear_lines(*after.check_full_lines())
    return after.grid


def glide(frm, to, steps=10):
    for k in range(1, steps + 1):
        touch("MOVE", frm[0] + (to[0] - frm[0]) * k / steps, frm[1] + (to[1] - frm[1]) * k / steps)


def drag(slot_center, piece, x, y):
    """Przeciąga klocek ze slotu tak, żeby jego lewy górny róg trafił w pole (x, y).

    Model zmierzony na emulatorze: po podniesieniu środek klocka jest LIFT px nad palcem,
    a potem klocek przesuwa się DRAG_GAIN razy szybciej niż palec.
    Pomiar w trakcie ciągnięcia odpada: nad trafionym celem gra podświetla linie do
    wyczyszczenia w kolorze klocka.
    """
    sx, sy = slot_center
    h, w = len(piece.shape), len(piece.shape[0])
    cx, cy = BOARD_X + (x + w / 2) * CELL, BOARD_Y + (y + h / 2) * CELL
    fx = sx + (cx - sx) / DRAG_GAIN
    fy = sy + (cy - (sy - LIFT)) / DRAG_GAIN
    touch("DOWN", sx, sy)
    glide((sx, sy), (fx, fy))
    time.sleep(0.5)  # klocek dogania palec z opóźnieniem
    aim = screenshot()
    touch("UP", fx, fy)
    return {"finger": [round(fx, 1), round(fy, 1)]}, aim


def annotate(img, grid, path):
    im = Image.fromarray(img.astype(np.uint8))
    d = ImageDraw.Draw(im)
    for r in range(8):
        for c in range(8):
            x, y = cell_center(c, r)
            d.ellipse([x - 16, y - 16, x - 8, y - 8], fill=(0, 255, 0) if grid[r][c] else (255, 0, 255))
    im.save(path)


def main(max_moves):
    os.makedirs(OUT, exist_ok=True)
    policy = GreedyPolicy()
    log = open(os.path.join(OUT, "moves.jsonl"), "w")
    img, grid, slots = settled_state()
    ok_streak = best_streak = 0
    for n in range(max_moves):
        score = read_score(img)
        Image.fromarray(img.astype(np.uint8)).save(os.path.join(OUT, f"{n:03d}_state.png"))
        annotate(img, grid, os.path.join(OUT, f"{n:03d}_read.png"))
        board = Board()
        board.grid = [row[:] for row in grid]
        pieces = [Piece(s[0], f"slot{i}", -1) if s else None for i, s in enumerate(slots)]
        moves = legal_moves(board, pieces)
        entry = {"n": n, "board": grid, "tray": [s[0] if s else None for s in slots], "score": score}
        if not in_game():
            entry["end"] = "gra nie jest na pierwszym planie"
            log.write(json.dumps(entry) + "\n")
            print(entry["end"], flush=True)
            break
        if not moves:
            entry["end"] = "brak legalnego ruchu wg odczytu"
            log.write(json.dumps(entry) + "\n")
            break
        game = SimpleNamespace(board=board, pieces=pieces, combo=0)
        i, x, y = policy.act(game, moves)
        expected = simulate(board, pieces[i], x, y)
        info, aim = drag(slots[i][1], pieces[i], x, y)
        Image.fromarray(aim.astype(np.uint8)).save(os.path.join(OUT, f"{n:03d}_aim.png"))
        img, observed, slots = stable_state()
        ok = observed == expected
        grid = observed
        ok_streak = ok_streak + 1 if ok else 0
        best_streak = max(best_streak, ok_streak)
        entry.update(move={"slot": i, "x": x, "y": y}, drag=info, expected=expected, observed=observed, ok=ok)
        log.write(json.dumps(entry) + "\n")
        log.flush()
        print(f"ruch {n}: slot {i} -> ({x},{y}) wynik {score} {'OK' if ok else 'ROZBIEŻNOŚĆ'}", flush=True)
    annotate(img, grid, os.path.join(OUT, "final.png"))
    print(f"najdłuższa seria zgodnych ruchów: {best_streak}")
    return best_streak


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
