#!/usr/bin/env bash
# Sandbox Claude Code na runnerze: bubblewrap i socat, zwolnione przestrzenie nazw użytkownika (ubuntu 24.04
# blokuje je w AppArmorze: "bwrap: setting up uid map: Permission denied") i próba, która kończy job od razu,
# a nie po 3 sesjach agenta bez Basha. Wołają ją wszystkie joby z CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1.
set -eu
sudo apt-get install -y -q bubblewrap socat
sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0 || true   # na starszych obrazach klucza nie ma
bwrap --unshare-all --ro-bind / / --dev /dev --proc /proc true
echo "sandbox: bwrap działa"
