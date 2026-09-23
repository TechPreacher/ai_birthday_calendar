#!/bin/bash
# Install an nginx site config, verify it, and roll back if it does not hold.
#
#   sudo deploy/apply-nginx-config.sh <source-file> <site-name>
#
# Safer than chaining cp && nginx -t && systemctl reload by hand: a chain that
# stops halfway leaves you believing it applied. This reports each step, and
# restores the previous config if the new one fails to validate.

set -uo pipefail

SRC="${1:-}"
SITE="${2:-}"

if [ -z "$SRC" ] || [ -z "$SITE" ]; then
    echo "usage: sudo $0 <source-file> <site-name>" >&2
    exit 2
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: must run as root (use sudo)" >&2
    exit 2
fi

TARGET="/etc/nginx/sites-available/$SITE"
BACKUP="$TARGET.bak-$(date +%Y%m%d-%H%M%S)"

if [ ! -f "$SRC" ]; then
    echo "ERROR: source file not found: $SRC" >&2
    exit 1
fi

if [ ! -f "$TARGET" ]; then
    echo "ERROR: no existing site at $TARGET" >&2
    exit 1
fi

if cmp -s "$SRC" "$TARGET"; then
    echo "Already identical to $TARGET -- nothing to do."
    exit 0
fi

echo "1/5 backing up  $TARGET"
cp -p "$TARGET" "$BACKUP" || { echo "ERROR: backup failed" >&2; exit 1; }
echo "    -> $BACKUP"

echo "2/5 installing  $SRC"
cp "$SRC" "$TARGET" || { echo "ERROR: copy failed" >&2; exit 1; }

echo "3/5 confirming the file really changed"
if cmp -s "$BACKUP" "$TARGET"; then
    echo "ERROR: target is unchanged after the copy" >&2
    exit 1
fi
echo "    -> $(wc -c < "$BACKUP") bytes became $(wc -c < "$TARGET") bytes"

echo "4/5 validating"
if ! nginx -t 2>&1 | sed 's/^/    /'; then
    echo "    FAILED -- restoring the previous config" >&2
    cp "$BACKUP" "$TARGET"
    nginx -t >/dev/null 2>&1 && echo "    restored, previous config still valid" >&2
    exit 1
fi

echo "5/5 reloading nginx"
if ! systemctl reload nginx; then
    echo "    reload FAILED -- restoring the previous config" >&2
    cp "$BACKUP" "$TARGET"
    systemctl reload nginx
    exit 1
fi

echo
echo "Applied. Previous config kept at:"
echo "  $BACKUP"
