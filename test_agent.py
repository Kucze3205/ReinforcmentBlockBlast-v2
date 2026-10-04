"""
test_agent.py — Zestaw testów diagnostycznych dla agenta DQN w Block Blast.

Uruchomienie:
    python test_agent.py

Każdy test opiera się na tej samej parze (agent, game) i resetuje grę na początku.
"""

import numpy as np
import random
import copy
import torch
import torch.nn.functional as F

from agent import Agent
from game import Game
from pieces import PIECE_POOL, PIECE_GRID, PIECE_SHAPES_PADDED

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_synthetic_state(agent, game):
    """Tworzy syntetyczny stan zgodny ze strukturą get_state() dla danej gry."""
    grid4 = np.zeros((4, 8, 8), dtype=np.float32)
    shapes = [np.zeros((PIECE_GRID, PIECE_GRID), dtype=np.float32) for _ in range(3)]
    numeric = np.zeros(4, dtype=np.float32)
    meta = [-1, -1, -1]
    return grid4, shapes, numeric, meta


def make_random_state(agent, game):
    """Zwraca losowy syntetyczny stan zgodny ze strukturą get_state()."""
    grid4 = np.random.rand(4, 8, 8).astype(np.float32)
    shapes = [np.random.rand(PIECE_GRID, PIECE_GRID).astype(np.float32) for _ in range(3)]
    numeric = np.random.rand(4).astype(np.float32)
    meta = [-1, -1, -1]
    return grid4, shapes, numeric, meta


def state_to_tensors(state, device):
    """Konwertuje stan (bez meta) na tensory gotowe do forward()."""
    grid4, shapes, numeric, _ = state
    grid_t = torch.tensor(grid4, dtype=torch.float32, device=device).unsqueeze(0)        # [1,4,8,8]
    shapes_t = [torch.tensor(s, dtype=torch.float32, device=device).unsqueeze(0).unsqueeze(0)  # [1,1,PIECE_GRID,PIECE_GRID]
                for s in shapes]
    numeric_t = torch.tensor(numeric, dtype=torch.float32, device=device).unsqueeze(0)   # [1,4]
    return grid_t, shapes_t, numeric_t


def play_one_game(agent, game, use_model=False, max_steps=500):
    """Rozgrywa jedną grę i zwraca końcowy score."""
    game.reset(seed=None)
    # Wymuś aktualizację maski przez get_state
    state = agent.get_state(game)

    steps = 0
    while not game.done and steps < max_steps:
        steps += 1

        # Zbierz aktualną maskę binarną (nie ważoną — do wyboru losowego)
        binary_mask, _ = agent.get_mask(game)
        valid_indices = np.where(binary_mask > 0)[0]

        if len(valid_indices) == 0:
            break

        if use_model:
            # Tryb greedy z maską ważoną
            state = agent.get_state(game)
            grid4, shapes, numeric, _ = state
            grid_t = torch.tensor(grid4, dtype=torch.float32, device=agent.device).unsqueeze(0)
            shapes_t = [torch.tensor(s, dtype=torch.float32, device=agent.device).unsqueeze(0).unsqueeze(0)
                        for s in shapes]
            numeric_t = torch.tensor(numeric, dtype=torch.float32, device=agent.device).unsqueeze(0)
            agent.model.eval()
            with torch.no_grad():
                q_vals = agent.model(grid_t, shapes_t, numeric_t).cpu().numpy().flatten()
            agent.model.train()
            # Maskowanie: tylko ważne indeksy
            masked = np.where(binary_mask > 0, q_vals, -np.inf)
            idx = int(np.argmax(masked))
        else:
            idx = int(random.choice(valid_indices))

        # Dekodowanie indeksu → (piece_slot, x, y)
        if idx < 64:
            piece_slot, x, y = 0, idx % 8, idx // 8
        elif idx < 128:
            piece_slot, x, y = 1, (idx - 64) % 8, (idx - 64) // 8
        else:
            piece_slot, x, y = 2, (idx - 128) % 8, (idx - 128) // 8

        action = [piece_slot, x, y]
        reward, score, done, _ = game.step(action)

        if done:
            break

        # Odśwież stan po ruchu
        state = agent.get_state(game)

    return game.score


# ---------------------------------------------------------------------------
# TEST 1 — Gradienty
# ---------------------------------------------------------------------------

def test_gradients(agent, game):
    print("\n" + "=" * 60)
    print("=== TEST 1: Gradienty ===")
    print("=" * 60)

    game.reset(seed=42)

    # Pobierz prawdziwy stan (inicjalizuje maskę)
    _ = agent.get_state(game)
    state = make_random_state(agent, game)

    grid_t, shapes_t, numeric_t = state_to_tensors(state, agent.device)

    agent.model.train()
    # Upewnij się, że gradienty są czyste
    agent.trainer.optimizer.zero_grad()

    out = agent.model(grid_t, shapes_t, numeric_t)
    # W architekturze Dueling DQN: out = value + (adv - mean(adv))
    # Suma out.sum() powoduje, że składniki adv się skracają (suma(adv) - 192 * 1/192 * suma(adv) = 0).
    # Dlatego sprawdzamy gradient dla pojedynczego elementu, aby uniknąć tego matematycznego wyzerowania.
    loss = out[0, 0]
    loss.backward()

    any_problem = False
    print(f"\n{'Warstwa':<45} {'Status':<10} {'Max |grad|'}")
    print("-" * 75)

    for name, param in agent.model.named_parameters():
        if param.grad is None:
            status = "BRAK"
            max_val = "—"
            any_problem = True
        elif torch.isnan(param.grad).any():
            status = "NaN"
            max_val = "NaN"
            any_problem = True
        elif param.grad.abs().max().item() == 0.0:
            status = "ZEROWY"
            max_val = "0.0"
            any_problem = True
        else:
            status = "OK"
            max_val = f"{param.grad.abs().max().item():.6f}"

        print(f"  {name:<43} {status:<10} {max_val}")

    agent.trainer.optimizer.zero_grad()

    print()
    if any_problem:
        print("WYNIK: PROBLEM — Niektóre warstwy mają problematyczne gradienty (patrz wyżej)")
    else:
        print("WYNIK: OK")


# ---------------------------------------------------------------------------
# TEST 2 — Wariancja wyjść
# ---------------------------------------------------------------------------

def test_output_variance(agent, game):
    print("\n" + "=" * 60)
    print("=== TEST 2: Wariancja wyjść ===")
    print("=" * 60)

    game.reset(seed=42)
    _ = agent.get_state(game)  # inicjuj maskę

    NUM_STATES = 20
    all_outputs = []

    agent.model.eval()
    with torch.no_grad():
        for _ in range(NUM_STATES):
            state = make_random_state(agent, game)
            grid_t, shapes_t, numeric_t = state_to_tensors(state, agent.device)
            q_vals = agent.model(grid_t, shapes_t, numeric_t).cpu().numpy().flatten()
            all_outputs.append(q_vals)
    agent.model.train()

    all_outputs = np.array(all_outputs)  # [20, 192]

    mean_val = float(np.mean(all_outputs))
    var_val  = float(np.var(all_outputs))
    min_val  = float(np.min(all_outputs))
    max_val  = float(np.max(all_outputs))

    print(f"\n  Liczba stanów:    {NUM_STATES}")
    print(f"  Średnia Q:        {mean_val:.6f}")
    print(f"  Wariancja Q:      {var_val:.6f}")
    print(f"  Min Q:            {min_val:.6f}")
    print(f"  Max Q:            {max_val:.6f}")

    # Średnia różnica między parami stanów
    diffs = []
    for i in range(NUM_STATES - 1):
        diffs.append(np.mean(np.abs(all_outputs[i] - all_outputs[i + 1])))
    mean_diff = float(np.mean(diffs))
    print(f"  Śr. różnica Q między kolejnymi stanami: {mean_diff:.6f}")

    print()
    if var_val < 0.01:
        print("  ⚠ OSTRZEŻENIE: wariancja < 0.01 — sieć prawdopodobnie ignoruje wejście!")
        print("WYNIK: PROBLEM — Zbyt mała wariancja wyjść sieci")
    else:
        print("WYNIK: OK")


# ---------------------------------------------------------------------------
# TEST 3 — Overfit na 1 próbce
# ---------------------------------------------------------------------------

def test_overfit_single_sample(agent, game):
    print("\n" + "=" * 60)
    print("=== TEST 3: Overfit na 1 próbce ===")
    print("=" * 60)

    game.reset(seed=42)
    _ = agent.get_state(game)  # inicjuj maskę

    # Stwórz lokalną kopię agenta/trainera żeby nie psuć oryginalnego stanu
    import copy as _copy
    local_model = _copy.deepcopy(agent.model)
    from model import QTrainer
    local_trainer = QTrainer(local_model, lr=0.01, gamma=0.9)

    device = agent.device

    # Ustalony stan i docelowe Q (użyj losowego stanu, ale trzymaj go jako stałą w tym teście)
    fixed_state = make_random_state(agent, game)
    fixed_next_state = make_random_state(agent, game)
    fixed_action = [0, 0, 0]   # piece=0, x=0, y=0  →  flat_idx = 0
    TARGET_Q = 10.0
    flat_idx = 0  # piece_idx*64 + y*8 + x = 0*64 + 0*8 + 0

    NUM_STEPS = 200
    final_loss = None
    final_q = None

    print(f"\n  {'Krok':<8} {'Loss':<14} {'Q[0]'}")
    print("  " + "-" * 35)

    for step in range(1, NUM_STEPS + 1):
        # Ręczny forward + target
        grid_t, shapes_t, numeric_t = state_to_tensors(fixed_state, device)
        local_model.train()
        pred = local_model(grid_t, shapes_t, numeric_t)  # [1, 192]
        target = pred.clone().detach()
        target[0][flat_idx] = TARGET_Q

        loss = F.huber_loss(pred, target)
        local_trainer.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(local_model.parameters(), max_norm=10.0)
        local_trainer.optimizer.step()

        if step % 50 == 0:
            local_model.eval()
            with torch.no_grad():
                q_now = local_model(grid_t, shapes_t, numeric_t)[0][flat_idx].item()
            local_model.train()
            print(f"  {step:<8} {loss.item():<14.6f} {q_now:.4f}")
            final_loss = loss.item()
            final_q = q_now

    print()
    if final_loss is not None and final_loss < 0.01:
        print("WYNIK: OK — architektura zdolna do dopasowania jednego przykładu")
    else:
        print(f"WYNIK: PROBLEM — loss={final_loss:.6f} po {NUM_STEPS} krokach (oczekiwano < 0.01). Sprawdź architekturę.")


# ---------------------------------------------------------------------------
# TEST 4 — Wzrost Q podczas treningu
# ---------------------------------------------------------------------------

def test_q_growth(agent, game):
    print("\n" + "=" * 60)
    print("=== TEST 4: Wzrost Q podczas treningu ===")
    print("=" * 60)

    game.reset(seed=42)

    # Lokalna kopia agenta żeby nie psuć oryginalnego
    import copy as _copy
    local_agent = Agent()
    local_agent.model.load_state_dict(_copy.deepcopy(agent.model.state_dict()))
    local_agent.trainer = type(agent.trainer)(
        local_agent.model,
        lr=agent.trainer.lr,
        gamma=agent.trainer.gamma,
        target_update_freq=agent.trainer.target_update_freq
    )
    local_agent.device = agent.device
    local_agent.model.to(local_agent.device)
    local_agent.epsilon = 0.5  # mix losowych i greedy

    ref_game = Game(seed=0)

    # Zbierz 50 losowych stanów referencyjnych
    REF_STATES = []
    for i in range(50):
        ref_game.reset(seed=i)
        state = local_agent.get_state(ref_game)
        REF_STATES.append(state)

    def mean_max_q(states):
        local_agent.model.eval()
        vals = []
        with torch.no_grad():
            for s in states:
                grid_t, shapes_t, numeric_t = state_to_tensors(s, local_agent.device)
                q = local_agent.model(grid_t, shapes_t, numeric_t).cpu().numpy().flatten()
                vals.append(float(np.max(q)))
        local_agent.model.train()
        return float(np.mean(vals))

    q_at_start = mean_max_q(REF_STATES)
    q_log = [(0, q_at_start)]

    print(f"\n  {'Krok':<8} {'Śr. max Q'}")
    print("  " + "-" * 22)
    print(f"  {'0':<8} {q_at_start:.6f}")

    TRAIN_STEPS = 500
    RECORD_EVERY = 50

    train_game = Game(seed=42)
    train_game.reset(seed=42)
    _ = local_agent.get_state(train_game)

    for step in range(1, TRAIN_STEPS + 1):
        if train_game.done:
            train_game.reset(seed=None)
            _ = local_agent.get_state(train_game)

        state_old = local_agent.get_state(train_game)
        grid4, shapes, numeric, _ = state_old

        # Wybierz akcję: mix losowej i greedy
        binary_mask, _ = local_agent.get_mask(train_game)
        valid_indices = np.where(binary_mask > 0)[0]

        if len(valid_indices) == 0:
            train_game.reset(seed=None)
            _ = local_agent.get_state(train_game)
            continue

        if random.random() < local_agent.epsilon:
            idx = int(random.choice(valid_indices))
        else:
            grid_t, shapes_t, numeric_t = state_to_tensors(state_old, local_agent.device)
            local_agent.model.eval()
            with torch.no_grad():
                q_vals = local_agent.model(grid_t, shapes_t, numeric_t).cpu().numpy().flatten()
            local_agent.model.train()
            masked = np.where(binary_mask > 0, q_vals, -np.inf)
            idx = int(np.argmax(masked))

        if idx < 64:
            action = [0, idx % 8, idx // 8]
        elif idx < 128:
            action = [1, (idx - 64) % 8, (idx - 64) // 8]
        else:
            action = [2, (idx - 128) % 8, (idx - 128) // 8]

        reward, score, done, _ = train_game.step(action)
        state_new = local_agent.get_state(train_game)

        local_agent.train_short_term(state_old, action, reward, state_new, done)
        local_agent.remember(state_old, action, reward, state_new, done)

        if len(local_agent.memory) > 64:
            local_agent.train_long_term()

        if done:
            train_game.reset(seed=None)
            _ = local_agent.get_state(train_game)

        if step % RECORD_EVERY == 0:
            q_now = mean_max_q(REF_STATES)
            q_log.append((step, q_now))
            print(f"  {step:<8} {q_now:.6f}")

    q_at_end = q_log[-1][1]
    print()
    if q_at_end > q_at_start:
        print(f"WYNIK: OK — Q wzrosło z {q_at_start:.4f} do {q_at_end:.4f}")
    else:
        print(f"WYNIK: PROBLEM — Q NIE wzrosło: start={q_at_start:.4f}, koniec={q_at_end:.4f}. Sprawdź trening.")


# ---------------------------------------------------------------------------
# TEST 5 — Porównanie z losowym agentem
# ---------------------------------------------------------------------------

def test_vs_random(agent, game):
    print("\n" + "=" * 60)
    print("=== TEST 5: Porównanie z losowym agentem ===")
    print("=" * 60)

    NUM_GAMES = 50
    MAX_STEPS = 500

    # Losowy agent
    random_scores = []
    for i in range(NUM_GAMES):
        score = play_one_game(agent, game, use_model=False, max_steps=MAX_STEPS)
        random_scores.append(score)

    # Agent z modelem (eval, maska binarna)
    model_scores = []
    for i in range(NUM_GAMES):
        score = play_one_game(agent, game, use_model=True, max_steps=MAX_STEPS)
        model_scores.append(score)

    mean_random = float(np.mean(random_scores))
    max_random  = float(np.max(random_scores))
    mean_model  = float(np.mean(model_scores))
    max_model   = float(np.max(model_scores))

    print(f"\n  {'Agent':<20} {'Śr. score':<15} {'Max score'}")
    print("  " + "-" * 45)
    print(f"  {'Losowy':<20} {mean_random:<15.2f} {max_random:.2f}")
    print(f"  {'Model (eval)':<20} {mean_model:<15.2f} {max_model:.2f}")
    print()

    if mean_model > mean_random:
        print(f"WYNIK: OK — model gra lepiej od losowego ({mean_model:.2f} > {mean_random:.2f})")
    else:
        print(f"WYNIK: PROBLEM — model NIE jest lepszy od losowego (model={mean_model:.2f}, losowy={mean_random:.2f}). "
              f"Potrzeba więcej treningu lub korekty architektury.")


# ---------------------------------------------------------------------------
# Punkt wejścia
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════╗")
    print("║        DIAGNOSTYKA AGENTA DQN — Block Blast             ║")
    print("╚══════════════════════════════════════════════════════════╝")

    agent = Agent()
    game  = Game(seed=42)

    test_gradients(agent, game)
    test_output_variance(agent, game)
    test_overfit_single_sample(agent, game)
    test_q_growth(agent, game)
    test_vs_random(agent, game)

    print("\n" + "=" * 60)
    print("Wszystkie testy zakończone.")
    print("=" * 60)
