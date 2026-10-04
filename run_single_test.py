"""Uruchamia pojedynczy test z test_agent.py i zapisuje wynik do pliku."""
import sys
import io

# Przekieruj stdout do pliku
with open("test_output.txt", "w", encoding="utf-8") as f:
    old_stdout = sys.stdout
    sys.stdout = f

    from agent import Agent
    from game import Game
    import test_agent as ta

    agent = Agent()
    game = Game(seed=42)

    ta.test_gradients(agent, game)
    ta.test_output_variance(agent, game)
    ta.test_overfit_single_sample(agent, game)
    ta.test_q_growth(agent, game)
    ta.test_vs_random(agent, game)

    sys.stdout = old_stdout

print("DONE - wyniki w test_output.txt")
