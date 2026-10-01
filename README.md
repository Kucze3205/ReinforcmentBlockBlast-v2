# ReinforcmentBlockBlast

Instrukcja obsługi pętli agentów. Szczegóły (sekrety, etykiety, limity):
[docs/loop-config.md](docs/loop-config.md).

## Włączenie

```
gh variable set AUTOPILOT --body on
gh workflow run dispatch.yml -f issue=<N>
```

`<N>` to issue z etykietą `rola:orchestrator`. Alternatywa: etykieta `ready`
na dowolnym issue z etykietą `rola:*`.

## Wyłączenie

```
gh variable set AUTOPILOT --body off
```

Zatrzymuje start nowych sesji. Przebieg już w toku dokańcza się sam.
