# blockblast-Self-Improvement-loop

Szczegóły (sekrety, zmienne, uprawnienia): [docs/loop-config.md](docs/loop-config.md).

## Włączenie

```
gh variable set AUTOPILOT --body on
gh workflow run drzewo.yml
```

Drugie polecenie startuje harmonogram drzewa: dalej pętla biegnie sama, aż bramka celu ją zakończy.

## Wyłączenie

```
gh variable set AUTOPILOT --body off
```

Zatrzymuje start nowych sesji. Przebieg już w toku dokańcza się sam.
