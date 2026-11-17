#!/bin/bash
# Fetch XFOIL 6.99 from the Ubuntu archive and unpack it here, without root. Builds the no-FPE-trap preload shim.
# Not needed if a system xfoil is installed and works headless.
set -e
cd "$(dirname "$0")"
if [ ! -x xfoil_pkg/usr/bin/xfoil ]; then
  mkdir -p xfoil_pkg && cd xfoil_pkg
  apt-get download xfoil
  dpkg -x xfoil_*.deb . && rm -f xfoil_*.deb
  cd ..
fi
gcc -shared -fPIC -O2 -o nofpe_shim.so nofpe_shim.c
echo "xfoil ready: $(pwd)/xfoil_pkg/usr/bin/xfoil"
