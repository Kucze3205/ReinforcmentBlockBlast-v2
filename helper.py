import matplotlib.pyplot as plt

plt.ion()


def plot(scores, mean_scores, meanreward=None):
    plt.clf()
    plt.title('Training...')
    plt.xlabel('Number of Games')
    plt.ylabel('Score')

    ax1 = plt.gca()
    ax1.plot(scores, label='Score', color='tab:blue')
    ax1.plot(mean_scores, label='Mean Score', color='tab:orange')
    ax1.tick_params(axis='y', labelcolor='tab:blue')
    ax1.set_ylim(bottom=0)

    lines, labels = ax1.get_legend_handles_labels()

    if meanreward is not None:
        ax2 = ax1.twinx()
        ax2.plot(meanreward, color='tab:green', label='Mean Reward')
        ax2.set_ylabel('Mean Reward', color='tab:green')
        ax2.tick_params(axis='y', labelcolor='tab:green')
        lines2, labels2 = ax2.get_legend_handles_labels()
        lines += lines2
        labels += labels2

    ax1.legend(lines, labels, loc='upper left')

    plt.show(block=False)
    plt.pause(.1)
