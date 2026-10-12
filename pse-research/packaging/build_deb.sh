#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; APP="$(dirname "$HERE")"; REPO="$(dirname "$APP")"
PY="${PYTHON:-$APP/.venv/bin/python}"
VERSION="${1:-0.1.0}"; ARCH="${ARCH:-amd64}"; PKG="pse-math"
STAGE="$HERE/stage"; OUT="$REPO/dist"
echo "== PyInstaller bundle"
rm -rf "$APP/build/pyi" "$STAGE"
"$PY" -m PyInstaller --noconfirm --clean --onedir --name "$PKG" \
  --distpath "$APP/build/pyi/dist" --workpath "$APP/build/pyi/work" --specpath "$APP/build/pyi" \
  --collect-submodules pse_research --collect-data pse_research \
  "$HERE/entry.py"
APPDIR="$STAGE/opt/$PKG"; mkdir -p "$APPDIR"
cp -a "$APP/build/pyi/dist/$PKG/." "$APPDIR/"
cp "$REPO/LICENSE" "$APPDIR/LICENSE"; cp "$REPO/NOTICE" "$APPDIR/NOTICE"
mkdir -p "$STAGE/usr/bin" "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor/256x256/apps" "$STAGE/usr/share/doc/$PKG" "$STAGE/DEBIAN"
ln -s "/opt/$PKG/$PKG" "$STAGE/usr/bin/$PKG"
cp "$HERE/$PKG.png" "$STAGE/usr/share/icons/hicolor/256x256/apps/$PKG.png"
cp "$REPO/LICENSE" "$STAGE/usr/share/doc/$PKG/LICENSE"; cp "$REPO/NOTICE" "$STAGE/usr/share/doc/$PKG/NOTICE"
cat > "$STAGE/usr/share/applications/$PKG.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=PSE Math
Comment=A PSE-governed research workbench for mathematical conjectures
Exec=$PKG
Icon=$PKG
Terminal=false
Categories=Education;Science;Math;
DESK
SIZE="$(du -sk "$STAGE/opt" "$STAGE/usr" | awk '{s+=$1} END{print s}')"
cat > "$STAGE/DEBIAN/control" <<CTL
Package: $PKG
Version: $VERSION
Section: science
Priority: optional
Architecture: $ARCH
Installed-Size: $SIZE
Maintainer: Andrej Ristic <andrej.s.ristic@gmail.com>
Depends: libc6 (>= 2.34), libgl1, libegl1, libfontconfig1, libxkbcommon0, libdbus-1-3
Homepage: https://github.com/andrejristic/pse-math
Description: PSE Math - a research workbench for mathematical conjectures
 A PSE-governed desktop workbench for building, refuting and tracking
 mathematical conjectures, with a shared library of results and a journal.
CTL
echo "== dpkg-deb"; mkdir -p "$OUT"
DEB="$OUT/${PKG}_${VERSION}_${ARCH}.deb"
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "$DEB"; echo "built $DEB"
