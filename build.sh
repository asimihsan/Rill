#!/usr/bin/env bash

CWD=`pwd`
if [ ! -d "ssh_tap" ] || [ ! -d "masspinger" ] || [ ! -d "bin" ]; then
    echo "Make sure you execute from root of Rill."
    exit 1
fi
if [ ! -d "bin/linux" ]; then
    mkdir -p "bin/linux"
fi
cd "${CWD}"/ssh_tap/build/linux
./make.sh
cd "${CWD}"/masspinger/build/linux
./make.sh
cd "${CWD}"

