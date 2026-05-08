#!/usr/bin/env bash
# One-shot Obsidian community-plugin installer for the Trading Second Brain.
#
# Downloads manifest.json / main.js / styles.css for each of the 7 plugins
# straight from each project's GitHub "latest release" into the vault's
# .obsidian/plugins/<id>/ folder. Pre-staged data.json configs are preserved.
#
# Usage:
#   ./scripts/install-obsidian-plugins.sh
#   OBSIDIAN_VAULT=/some/other/path ./scripts/install-obsidian-plugins.sh
#
# After running: quit Obsidian fully (⌘Q) and reopen the vault. Because
# .obsidian/community-plugins.json already lists these IDs, Obsidian will
# auto-enable each plugin on startup.
set -euo pipefail

DEFAULT_VAULT="$HOME/TradingSecondBrain/obsidian-vault"
VAULT="${OBSIDIAN_VAULT:-$DEFAULT_VAULT}"
PLUGINS_DIR="$VAULT/.obsidian/plugins"

if [ ! -d "$VAULT/.obsidian" ]; then
  echo "ERROR: vault not found at $VAULT" >&2
  echo "Pass OBSIDIAN_VAULT=/path/to/vault to override." >&2
  exit 1
fi

mkdir -p "$PLUGINS_DIR"

# id|owner/repo — keep in sync with .obsidian/community-plugins.json
PLUGINS=(
  "obsidian-local-rest-api|coddingtonbear/obsidian-local-rest-api"
  "smart-connections|brianpetro/obsidian-smart-connections"
  "dataview|blacksmithgu/obsidian-dataview"
  "templater-obsidian|SilentVoid13/Templater"
  "obsidian-advanced-uri|Vinzent03/obsidian-advanced-uri"
  "obsidian-git|Vinzent03/obsidian-git"
  "calendar|liamcain/obsidian-calendar-plugin"
)

failed=0
for entry in "${PLUGINS[@]}"; do
  id="${entry%|*}"
  repo="${entry#*|}"
  dest="$PLUGINS_DIR/$id"
  mkdir -p "$dest"
  echo "==> $id  ($repo)"
  got_required=0
  for f in manifest.json main.js styles.css; do
    url="https://github.com/$repo/releases/latest/download/$f"
    if curl -fsSL --retry 3 --retry-delay 2 "$url" -o "$dest/$f.tmp"; then
      mv "$dest/$f.tmp" "$dest/$f"
      echo "    fetched $f"
      [ "$f" != "styles.css" ] && got_required=$((got_required + 1))
    else
      rm -f "$dest/$f.tmp"
      if [ "$f" = "styles.css" ]; then
        echo "    (no styles.css — that's normal for some plugins)"
      else
        echo "    WARN: failed to fetch $f for $id from $url" >&2
      fi
    fi
  done
  if [ "$got_required" -lt 2 ]; then
    echo "    !! $id is incomplete (missing manifest.json or main.js)" >&2
    failed=$((failed + 1))
  fi
done

echo
if [ "$failed" -gt 0 ]; then
  echo "$failed plugin(s) failed. They are usually transient — re-run the script." >&2
  exit 2
fi

echo "All 7 plugins installed into $PLUGINS_DIR"
echo
echo "Next:"
echo "  1. Quit Obsidian (Cmd+Q) if open, then reopen the vault."
echo "  2. Settings → Community plugins → confirm all 7 are toggled on."
echo "     (community-plugins.json already lists them so they should auto-enable.)"
echo "  3. Settings → Local REST API → Copy API Key, paste into:"
echo "       - .env  (OBSIDIAN_API_KEY=...)"
echo "       - .obsidian/plugins/obsidian-local-rest-api/data.json"
