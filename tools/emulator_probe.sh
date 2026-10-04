#!/usr/bin/env bash
# Sonda: instaluje splity Block Blasta, uruchamia grƒô, zbiera zrzuty i logi do probe-out/.
set -u
OUT=probe-out
PKG=com.block.juggle
mkdir -p "$OUT"

# Po pierwszym starcie obraz Play aktualizuje pakiety i zabija procesy ó czekamy, aø ucichnie.
sleep 90
adb shell settings put global verifier_verify_adb_installs 0
adb shell settings put global package_verifier_enable 0

adb install-multiple -r -g assets/*.apk 2>&1 | tee "$OUT/install.txt"
grep -q Success "$OUT/install.txt" || { echo "INSTALL FAILED"; exit 1; }

adb logcat -c
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null
sleep 25
adb exec-out screencap -p > "$OUT/shot_1_terms.png"
adb shell input tap 160 437   # Accept Terms of Use (ekran 320x640)

for i in 1 2 3 4 5 6; do
  sleep 10
  echo "t=+$((25 + i*10))s pid=$(adb shell pidof $PKG)" | tee -a "$OUT/status.txt"
done
adb exec-out screencap -p > "$OUT/shot_2_after_accept.png"

adb shell dumpsys window | grep mCurrentFocus | tee -a "$OUT/status.txt"
adb logcat -d > "$OUT/logcat.txt"
grep -E "FATAL EXCEPTION|No config chosen" "$OUT/logcat.txt" | tee "$OUT/errors.txt"

[ -n "$(adb shell pidof $PKG)" ] || { echo "GAME NOT RUNNING"; exit 1; }
[ ! -s "$OUT/errors.txt" ] || { echo "ERRORS IN LOG"; exit 1; }
echo "PROBE OK (sprawdü zrzuty: czy to ekran rozgrywki)"
