import pygame
from game import Game
from agent import Agent

# Main event loop for UI interaction and training control

def main():
    game = Game(seed=42)
    agent = Agent()
    running = True
    training = False
    step_once = False

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                btn = game.ui.check_button_click(event.pos)
                if btn == 'train':
                    training = not training
                    game.ui.set_training(training)
                elif btn == 'step':
                    step_once = True
                elif btn == 'restart':
                    game.reset(seed=42)
                    training = False
                    game.ui.set_training(False)

        if training or step_once:
            # Run one training step
            state_old = agent.get_state(game)
            final_move = agent.get_action(state_old)
            reward, score, done, message = game.step(final_move)
            agent.mask, agent.spaces_amount = agent.get_mask(game)
            state_new = agent.get_state(game)
            agent.train_short_term(state_old, final_move, reward, state_new, done)
            agent.remember(state_old, final_move, reward, state_new, done)
            if done:
                game.reset(seed=42)
            step_once = False

        game.refresh_ui()
        game.ui.clock.tick(30)

if __name__ == "__main__":
    main()
