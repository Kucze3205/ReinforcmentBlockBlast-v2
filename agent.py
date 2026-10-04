
import numpy as np
import random
from collections import deque

import torch
from game import Game
from model import QTrainer, CustomNet
# from helper import plot  # UI/plotting disabled
from pieces import PIECE_POOL, PIECE_GRID, PIECE_SHAPES_PADDED
from board import Board


MAX_MEMORY = 100_000
BATCH_SIZE = 256
GRID_SIZE = 8*8
EPSILON_START = 1.0
EPSILON_END   = 0.1
EPSILON_STEPS = 500

class Agent:
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.n_games = 0
        self.epsilon = EPSILON_START # randomness
        self.gamma = 0.9 # discount rate
        self.memory = deque(maxlen=MAX_MEMORY)
        self.model = CustomNet(4, 3*8*8).to(self.device) # Placeholder for the neural network model
        self.trainer = QTrainer(self.model, lr=5e-4, gamma=0.9) # Placeholder for the trainer (e.g., optimizer, loss function)
        self.mask = np.zeros(3*8*8, dtype=int)
        self.spaces_amount = 0
        
        pass

    def get_state(self, game):
        # Grid jako [8,8] float32
        grid = np.array(game.board.grid, dtype=np.float32)
       
        self.mask, self.spaces_amount = self.get_weighted_mask(game)
        # Kanały: plansza + 3 maski
        grid4 = np.zeros((4, 8, 8), dtype=np.float32)
        grid4[0] = grid
        # mask: 192 -> 3x[8,8]
        for i in range(3):
            grid4[i+1] = self.mask[i*64:(i+1)*64].reshape(8,8)

        # Shapes jako lista 3 x [PIECE_GRID,PIECE_GRID] float32
        shapes = []
        for piece in game.pieces:
            if piece is None:
                shape = np.zeros((PIECE_GRID, PIECE_GRID), dtype=np.float32)
            else:
                shape = np.array(PIECE_SHAPES_PADDED[piece.index][0], dtype=np.float32)
            shapes.append(shape)

        # Wartości liczbowe jako [log1p(score), combo, round_placement, spaces_amount] float32.
        # score kumuluje się przez całą partię (do milionów), więc surowa wartość
        # zdominowałaby pozostałe cechy — stąd skala logarytmiczna.
        numeric = np.array([np.log1p(game.score), game.combo, game.round_placement, self.spaces_amount], dtype=np.float32)

        meta_pieces_indices = [piece.index if piece else -1 for piece in game.pieces]
        return grid4, shapes, numeric, meta_pieces_indices
    
    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))
        pass

    def train_long_term(self):
        if len(self.memory) > BATCH_SIZE:
            # Implementation for long-term training
            mini_sample = random.sample(self.memory, BATCH_SIZE) # list of tuples
        else:
            mini_sample = self.memory

        states, actions, rewards, next_states, dones = zip(*mini_sample)
        self.trainer.train_step(states, actions, rewards, next_states, dones)
        pass

    def train_short_term(self, state, action, reward, next_state, done):
        self.trainer.train_step(state, action, reward, next_state, done)
        pass

    def print_board_and_masks(self, grid, mask, game):

        shapes = []
        for piece in game.pieces:
            if piece is None:
                shape = np.zeros((PIECE_GRID, PIECE_GRID), dtype=np.float32)
            else:
                shape = np.array(PIECE_SHAPES_PADDED[piece.index][0], dtype=np.float32)
            shapes.append(shape)

        # grid: 8x8, mask: 3*8*8, shapes: 3x[4x4]
        board_arr = np.array(grid)
        masks = [mask[i*64:(i+1)*64].reshape(8,8) for i in range(3)]
        print("\nTablice obok siebie:")
        for y in range(8):
            row = []
            row.append(' '.join(f"{int(board_arr[y][x])}" for x in range(8)))
            for m in masks:
                row.append(' '.join(f"{int(m[y][x])}" for x in range(8)))
            # Dodaj kształty tylko dla pierwszych 4 wierszy
            if shapes is not None and y < 4:
                shape_row = []
                for shape in shapes:
                    shape_row.append(' '.join(f"{int(shape[y][x])}" for x in range(4)))
                row.append('   |   '.join(shape_row))
            print('   |   '.join(row))

    def get_mask(self, game):
        grid = game.board.grid
        pieces_indices = [piece.index if piece else -1 for piece in game.pieces]
        spaces_amount = 0
        mask = np.zeros(3*8*8, dtype=int)

        i = 0
        for idx in pieces_indices:
            if idx >= 0:
                piece = PIECE_POOL[idx]
                for y in range(8 - len(piece.shape) + 1):
                    for x in range(8 - len(piece.shape[0]) + 1):
                        temp_board = Board()
                        temp_board.grid = grid.copy()
                        if temp_board.can_place_piece(piece, x, y):
                            mask_idx = i * 64 + y * 8 + x
                            mask[mask_idx] = 1
                            spaces_amount += 1
            i += 1

        # Przygotuj shapes do wyświetlenia
        shapes = []
        for piece in game.pieces:
            if piece is None:
                shape = np.zeros((PIECE_GRID, PIECE_GRID), dtype=np.float32)
            else:
                shape = np.array(PIECE_SHAPES_PADDED[piece.index][0], dtype=np.float32)
            shapes.append(shape)

        # Wywołanie funkcji drukującej tablice z shapes
        #self.print_board_and_masks(grid, mask, shapes)
        return mask, spaces_amount
    
    def get_weighted_mask(self, game):
        mask, spaces_amount = self.get_mask(game)
        grid = game.board.grid
        pieces_indices = [piece.index if piece else -1 for piece in game.pieces]
        weighted_mask = np.zeros(3 * 8 * 8, dtype=float)

        # N=0, E=1, S=2, W=3
        face_adj  = [(-1,0),(0,1),(1,0),(0,-1)]   # sąsiednia komórka po zewnętrznej stronie ściany
        travel    = [(0,1),(1,0),(0,-1),(-1,0)]   # kierunek ruchu wzdłuż ściany

        def is_contact(r, c, d, cells):
            nr, nc = r + face_adj[d][0], c + face_adj[d][1]
            if not (0 <= nr < 8 and 0 <= nc < 8):
                return 1                                      # ściana planszy
            if (nr, nc) not in cells and grid[nr][nc] == 1:
                return 1                                      # zajęte pole
            return 0

        def next_face(r, c, d, cells):
            """Następna ściana obwodu idąc zgodnie z ruchem wskazówek zegara."""

            # 1. Narożnik wypukły: skręt w prawo — sąsiednia komórka w kierunku rd
            #    NIE należy do klocka → oba boki tego narożnika są zewnętrzne
            rd = (d + 1) % 4
            ar, ac = r + face_adj[rd][0], c + face_adj[rd][1]
            if (ar, ac) not in cells:
                return r, c, rd                               # ta sama komórka, następna ściana

            # 2. Prosto: następna komórka w kierunku ruchu ma tę samą zewnętrzną ścianę
            tr, tc = r + travel[d][0], c + travel[d][1]
            if (tr, tc) in cells:
                er, ec = tr + face_adj[d][0], tc + face_adj[d][1]
                if (er, ec) not in cells:
                    return tr, tc, d

            # 3. Narożnik wklęsły: skok po przekątnej do sąsiedniej komórki
            #    (zmiana kierunku o 90° w lewo, przejście na inną komórkę)
            er, ec = r + face_adj[d][0], c + face_adj[d][1]
            tr2, tc2 = er + travel[d][0], ec + travel[d][1]
            return tr2, tc2, (d - 1) % 4

        def trace_perimeter(piece_cells): #funckja może być zhardcodowana dla każdego elementu, zeby przyspieszyć!!!!!!!!!!!!!!!!!!!!
            """Obchodzi obwód klocka zgodnie z ruchem wskazówek zegara.
            Przy narożniku wypukłym: oba boki pojawiają się kolejno (2 elementy).
            Przy narożniku wklęsłym: skok — też 2 elementy z różnych komórek.
            Zwraca listę 0/1 (czy dana ściana dotyka czegoś)."""


            cells = frozenset(piece_cells)

            # Start: najwyższy wiersz, najbardziej lewy, ściana N
            min_r = min(r for r, c in cells)
            min_c = min(c for r, c in cells if r == min_r)
            start = (min_r, min_c, 0)

            seq = []
            r, c, d = start
            for _ in range(500):                              # limit bezpieczeństwa
                seq.append(is_contact(r, c, d, cells))
                r, c, d = next_face(r, c, d, cells)
                if (r, c, d) == start:
                    break
            return seq

        def longest_run(seq):
            """Najdłuższy ciągły odcinek jedynek w kołowej tablicy."""
            if not seq:
                return 0
            if all(v == 1 for v in seq):
                return len(seq)
            doubled = seq + seq
            best = cur = 0
            for v in doubled:
                if v == 1:
                    cur += 1
                    if cur > best:
                        best = cur
                else:
                    cur = 0
            return min(best, len(seq))                        # nie więcej niż cały obwód

        for i, idx in enumerate(pieces_indices):
            if idx < 0:
                continue
            piece = PIECE_POOL[idx]
            shape = piece.shape
            ph, pw = len(shape), len(shape[0])

            for y in range(8 - ph + 1):
                for x in range(8 - pw + 1):
                    if mask[i * 64 + y * 8 + x] == 0:
                        continue

                    piece_cells = {
                        (y + py, x + px)
                        for py in range(ph)
                        for px in range(pw)
                        if shape[py][px]
                    }

                    seq = trace_perimeter(piece_cells)
                    weighted_mask[i * 64 + y * 8 + x] = longest_run(seq)

        #self.print_board_and_masks(grid, weighted_mask, game)
        return weighted_mask, spaces_amount
    
    def get_action(self, state, epsilon=None):
        """Wybiera ruch. `epsilon=0` daje tryb deterministyczny wymagany przez benchmark (#8).

        Bez podanego `epsilon` obowiązuje harmonogram treningowy, który nigdy nie schodzi
        poniżej EPSILON_END — w pełni wytrenowany bot i tak grałby 10% ruchów losowo.
        """
        if epsilon is None:
            progress = min(1.0, self.n_games / EPSILON_STEPS)
            epsilon = EPSILON_START - progress * (EPSILON_START - EPSILON_END)
        self.epsilon = epsilon

        final_move = [0,0,0] # Placeholder for the action (e.g., piece index, x, y)

        if self.epsilon > 0 and random.random() < self.epsilon:
            random_prediction = []
            for i in range(3*8*8):
                random_prediction.append(random.random())
            masked_prediction = np.where(self.mask, random_prediction, -np.inf) # Apply mask to filter out invalid moves
            #masked_prediction = self.mask
        else:
            grid, shapes, numeric = state
            # grid: [4,8,8] -> [1,4,8,8]
            grid_t = torch.tensor(grid, dtype=torch.float32, device=self.device).unsqueeze(0)
            shapes_t = [torch.tensor(s, dtype=torch.float32, device=self.device).unsqueeze(0).unsqueeze(0) for s in shapes]
            numeric_t = torch.tensor(numeric, dtype=torch.float32, device=self.device).unsqueeze(0)

            self.model.eval()                    # wyłącz Dropout i BN podczas inferencji
            with torch.no_grad():
                prediction = self.model(grid_t, shapes_t, numeric_t)
            self.model.train()

            prediction = prediction.detach().cpu().numpy().flatten() # Ensure on CPU for numpy

            masked_prediction = np.where(self.mask > 0, prediction + self.mask * 0.1 , -np.inf)

        idx = torch.argmax(torch.tensor(masked_prediction)).item()

        if idx < 64:
            piece_index = 0
            x = idx % 8
            y = idx // 8
        elif idx < 128:
            piece_index = 1
            x = (idx - 64) % 8
            y = (idx - 64) // 8
        else:
            piece_index = 2
            x = (idx - 128) % 8
            y = (idx - 128) // 8

        final_move = [piece_index, x, y]

        return final_move
    
    def count_blobs(self, grid):
        """
        Tworzy grid 10x10 z ramką jedynek wokół planszy 8x8.
        Liczy wszystkie odrębne plamy (i zer i jedynek).
        Zwraca liczba_plam - 2.

        Pusta plansza:  ramka(1 plama) + wnętrze(1 plama) = 2 → 2-2 = 0
        Klocek w środku: ramka(1) + klocek(1) + wnętrze(1) = 3 → 3-2 = 1
        Klocek przy ścianie: klocek łączy się z ramką → ramka(1) + wnętrze(1) = 2 → 2-2 = 0
        """
        # Stwórz planszę 10x10 z ramką jedynek
        padded = [[1] * 10 for _ in range(10)]
        for y in range(8):
            for x in range(8):
                padded[y + 1][x + 1] = grid[y][x]

        visited = [[False] * 10 for _ in range(10)]
        blobs = 0

        def bfs(start_y, start_x):
            value = padded[start_y][start_x]
            queue = deque([(start_y, start_x)])
            visited[start_y][start_x] = True
            while queue:
                cy, cx = queue.popleft()
                for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < 10 and 0 <= nx < 10:
                        if not visited[ny][nx] and padded[ny][nx] == value:
                            visited[ny][nx] = True
                            queue.append((ny, nx))

        for y in range(10):
            for x in range(10):
                if not visited[y][x]:
                    bfs(y, x)
                    blobs += 1

        return blobs - 2

    def count_new_holes(self, board_before, board_after):
        holes_before = self.count_blobs(board_before)
        holes_after  = self.count_blobs(board_after) #można zooptymalizować
        return holes_after - holes_before

    def get_heuristic_action(self, state):
        """
        Heuristic: choose (piece, x, y) that results in the minimal number of new blobs after placement.
        If there are ties, select the one with the highest weighted_mask value.
        """
        grid, shapes, numeric, pieces_indices = state
        weighted_mask = self.mask
        # We need the indices of the pieces in the current state

        min_blobs = None
        best_moves = []
        # First pass: find all moves with minimal new blobs
        for idx in range(3*8*8):
            if weighted_mask[idx] <= 0:
                continue
            # Decode idx to (piece_slot, x, y)
            if idx < 64:
                piece_slot = 0
                x = idx % 8
                y = idx // 8
            elif idx < 128:
                piece_slot = 1
                x = (idx - 64) % 8
                y = (idx - 64) // 8
            else:
                piece_slot = 2
                x = (idx - 128) % 8
                y = (idx - 128) // 8
            piece_idx = pieces_indices[piece_slot] if piece_slot < len(pieces_indices) else -1
            if piece_idx < 0:
                continue
            piece = PIECE_POOL[piece_idx]
            board_before = np.array(grid[0])
            temp_board = Board()
            temp_board.grid = board_before.copy()
            if not temp_board.can_place_piece(piece, x, y):
                continue
            temp_board.place_piece(piece, x, y)
            board_after = temp_board.grid
            new_blobs = self.count_new_holes(board_before, board_after)
            if (min_blobs is None) or (new_blobs < min_blobs):
                min_blobs = new_blobs
                best_moves = [(piece_slot, x, y, weighted_mask[idx])]
            elif new_blobs == min_blobs:
                best_moves.append((piece_slot, x, y, weighted_mask[idx]))
        # Second pass: among best_moves, pick one with max weighted_mask
        if best_moves:
            best_moves.sort(key=lambda t: t[3], reverse=True)
            piece_slot, x, y, _ = best_moves[0]
            return [piece_slot, x, y]
        # Fallback: pick any valid move
        for idx in range(3*8*8):
            if weighted_mask[idx] > 0:
                if idx < 64:
                    return [0, idx % 8, idx // 8]
                elif idx < 128:
                    return [1, (idx - 64) % 8, (idx - 64) // 8]
                else:
                    return [2, (idx - 128) % 8, (idx - 128) // 8]
        # If still none, just return a default
        return [0, 0, 0]

def train():
    # UI/plotting disabled for long training
    total_score = 0
    total_reward = 0
    recod = 0
    agent = Agent()
    game = Game(seed=42)
    SAVE_EVERY = 100  # Save model and print stats every N games
    state_new = agent.get_state(game) # Initialize state_new before the loop
    import csv
    import os
    CSV_FILE = 'training_stats1.csv'
    csv_header = ['Game', 'Sample_score', 'Sample_reward', 'MeanScore', 'Mean_reward', 'Record']

    # Write header if file does not exist
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(csv_header)

    while True:

        #get old state
        state_old = state_new
        #get move
        #final_move = agent.get_action(state_old)

        final_move = agent.get_action(state_old)
        
        #perform move and get new state
        reward, score, done, message = game.step(final_move)

        state_new = agent.get_state(game)

        # Nagroda = przyrost wyniku zwrocony przez game.step (decyzja #23).
        # Zadnego shapingu: poprzedni pochodzil z nieskalibrowanej gry.

        #train short memory
        agent.train_short_term(state_old, final_move, reward, state_new, done)

        #remember
        agent.remember(state_old, final_move, reward, state_new, done)

        total_reward += reward
        

        #print('Message:', message)
        if done:
            #train long memory, plot result
            game.reset(seed=42)

            agent.n_games += 1

            agent.train_long_term()

            if score > recod:
                recod = score

            mean_reward = total_reward / agent.n_games
            #print(f'Game {agent.n_games} Score {score} Record: {recod} Mean reward {mean_reward}', end='\r', flush=True)

            total_score += score
            mean_score = total_score / agent.n_games
            # Save and print stats every SAVE_EVERY games
            if agent.n_games % SAVE_EVERY == 0:
                print(f'Game {agent.n_games} Sample_score {score} Sample_reward {reward} MeanScore: {mean_score} Mean reward {mean_reward} Record: {recod}', end='\r', flush=True)

                # Append stats to CSV
                with open(CSV_FILE, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        agent.n_games,
                        score,
                        reward,
                        mean_score,
                        mean_reward,
                        recod
                    ])
                
                agent.model.save()
        
    pass

if __name__ == "__main__":
    train()