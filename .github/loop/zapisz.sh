#!/usr/bin/env bash
# Commit plików na gałąź pętli z ponowieniami. Równoległe węzły i ocena piszą rozłączne pliki,
# więc rebase nie ma konfliktów. Użycie: zapisz.sh <komunikat> <ścieżka>...
set -u
msg=$1; shift
git add "$@"
git diff --cached --quiet && exit 0
git commit -q -m "$msg"
url="https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}"
for i in 1 2 3 4 5; do
  git pull -q --rebase "$url" "$DEFAULT_BRANCH" && git push -q "$url" "HEAD:$DEFAULT_BRANCH" && exit 0
  sleep $((i * 10))
done
exit 1
