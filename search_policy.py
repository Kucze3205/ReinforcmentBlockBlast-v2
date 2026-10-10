"""
Polityka przeżycia: wiązka po tacce na bitboardach (bit = y * 8 + x).

Plan trzech postawień liczony raz na tackę, wykonywany krok po kroku. Liście wiązki
oceniane ryzykiem, że następna tacka nie ma żadnego pasującego klocka.
"""
import random

from pieces import PIECE_POOL, PIECE_TYPES

HARD_TYPES = [4, 6, 7, 10, 9]  # beam5, rect23, square3, corner5, L

_FULL = (1 << 64) - 1
_ROWS = [0xFF << (8 * r) for r in range(8)]
_COLS = [sum(1 << (8 * r + c) for r in range(8)) for c in range(8)]
_NOT_A = 0xFEFEFEFEFEFEFEFE  # bez kolumny 0
_NOT_H = 0x7F7F7F7F7F7F7F7F  # bez kolumny 7
_LEFT_WALL = 0x0101010101010101
_RIGHT_WALL = 0x8080808080808080
_TOP_WALL = 0xFF
_BOTTOM_WALL = 0xFF << 56


def _pose_masks():
    out = []
    for piece in PIECE_POOL:
        h, w = len(piece.shape), len(piece.shape[0])
        cells = [(r, c) for r in range(h) for c in range(w) if piece.shape[r][c]]
        masks = []
        for y in range(8 - h + 1):
            for x in range(8 - w + 1):
                m = 0
                for r, c in cells:
                    m |= 1 << ((y + r) * 8 + x + c)
                masks.append((x, y, m))
        out.append(masks)
    return out


_MASKS = _pose_masks()


def _clear(board):
    """Zwraca (plansza po czyszczeniu, liczba linii)."""
    kill = 0
    lines = 0
    for m in _ROWS:
        if board & m == m:
            kill |= m
            lines += 1
    for m in _COLS:
        if board & m == m:
            kill |= m
            lines += 1
    return board & ~kill, lines


def _popcount(x):
    return bin(x).count("1")


P = {"occ": 1.4, "iso": 0.75, "edge": 1.5, "wall": 2.0, "line": 4.2,
     "risk": 400.0, "fit": 80.0, "dead": 66.0,
     "beam": 40, "final": 12, "mid": 0,
     "hard": 500.0, "nhard": 16}


def _cheap(board):
    """Tania ocena planszy: mało zajętych pól i mało zamkniętych dziur."""
    empty = ~board & _FULL
    a = ((board << 1) & _NOT_A) | _LEFT_WALL
    b = ((board >> 1) & _NOT_H) | _RIGHT_WALL
    c = (board << 8) | _TOP_WALL
    d = (board >> 8) | _BOTTOM_WALL
    three = (a & b & c) | (a & b & d) | (a & c & d) | (b & c & d)
    edges = _popcount((board ^ (board >> 1)) & _NOT_H) + _popcount(board ^ (board >> 8))
    walls = _popcount(empty & (_LEFT_WALL | _RIGHT_WALL | _TOP_WALL | _BOTTOM_WALL))
    return (-P["occ"] * _popcount(board) - P["iso"] * _popcount(three & empty)
            - P["edge"] * edges - P["wall"] * walls)


def _playable(board, poses):
    """Czy tackę (krotka póz) da się wyłożyć w całości, w dowolnej kolejności."""
    if not poses:
        return True
    seen = set()
    for k, pose in enumerate(poses):
        if pose in seen:
            continue
        seen.add(pose)
        rest = poses[:k] + poses[k + 1:]
        for _x, _y, m in _MASKS[pose]:
            if not board & m and _playable(_clear(board | m)[0], rest):
                return True
    return False


def _fit_stats(board):
    """(średnia po typach z odsetka pasujących póz, P(następna tacka ma klocek bez miejsca))."""
    tot = 0.0
    q = 0.0
    for poses in PIECE_TYPES:
        fit = 0
        for pi in poses:
            if any(not board & m for _x, _y, m in _MASKS[pi]):
                fit += 1
            else:
                q += 1.0 / (len(PIECE_TYPES) * len(poses))
        tot += fit / len(poses)
    return tot / len(PIECE_TYPES), 1.0 - (1.0 - q) ** 3


class SearchPolicy:
    BEAM = 40
    FINAL = 12
    LINE_W = 6.0
    RISK_W = 400.0
    FIT_W = 40.0
    DEAD_W = 8.0

    name = "search"

    def __init__(self):
        self.plan = []
        self.rng = random.Random(0)

    def reset(self, game_seed):
        self.plan = []
        self.rng = random.Random(game_seed)

    def _hard_trays(self):
        n = int(P["nhard"])
        types = [PIECE_TYPES[t] for t in HARD_TYPES]
        return [
            tuple(self.rng.choice(self.rng.choice(types)) for _ in range(3)) for _ in range(n)
        ]

    def _leaf(self, board, lines):
        mean_fit, dead_next = _fit_stats(board)
        risk = (1.0 - mean_fit) ** 3
        hard = 0.0
        if P["hard"] and self._trays:
            hard = sum(not _playable(board, t) for t in self._trays) / len(self._trays)
        return (
            -P["hard"] * hard +
            _cheap(board)
            + P["line"] * lines
            - P["risk"] * risk
            - P["fit"] * (1.0 - mean_fit)
            - P["dead"] * dead_next
        )

    def _search(self, board, poses):
        """poses: lista (idx_w_tacce, pose). Zwraca najlepszy ciąg (idx, x, y) lub None."""
        self._trays = self._hard_trays() if P["hard"] else []
        states = [(board, 0, tuple(range(len(poses))), ())]
        for depth in range(len(poses)):
            nxt = {}
            for bd, lines, rem, seq in states:
                for k in rem:
                    idx, pose = poses[k]
                    rest = tuple(r for r in rem if r != k)
                    for x, y, m in _MASKS[pose]:
                        if bd & m:
                            continue
                        nb, ln = _clear(bd | m)
                        key = (nb, rest)
                        sc = _cheap(nb) + P["line"] * (lines + ln)
                        cur = nxt.get(key)
                        if cur is None or sc > cur[0]:
                            nxt[key] = (sc, nb, lines + ln, rest, seq + ((idx, x, y),))
            if not nxt:
                return max(states, key=lambda s: len(s[3]))[3] or None
            ranked = sorted(nxt.values(), key=lambda v: -v[0])
            keep = int(P["final"] if depth == len(poses) - 1 else P["beam"])
            states = [(v[1], v[2], v[3], v[4]) for v in ranked[:keep]]
            mid = int(P["mid"])
            if mid and depth < len(poses) - 1:
                states.sort(key=lambda s: -self._leaf(s[0], s[1]))
                states = states[:mid]
        best, best_s = None, None
        for bd, lines, _rem, seq in states:
            s = self._leaf(bd, lines)
            if best_s is None or s > best_s:
                best, best_s = seq, s
        return best

    def act(self, game, actions):
        if self.plan and self.plan[0] in actions:
            return self.plan.pop(0)
        board = 0
        for y, row in enumerate(game.board.grid):
            for x, v in enumerate(row):
                if v:
                    board |= 1 << (y * 8 + x)
        poses = [(i, p.index) for i, p in enumerate(game.pieces) if p is not None]
        seq = self._search(board, poses)
        if not seq or seq[0] not in actions:
            self.plan = []
            return actions[0]
        self.plan = list(seq[1:])
        return seq[0]


def build(weights=None):
    return SearchPolicy()
