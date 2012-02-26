#!/usr/bin/env bash

#CXX=g++
CXX=clang
FLAG_WARNINGS="-pedantic"

"${CXX}" "${FLAG_WARNINGS}" -O3 -march=native -I/usr/local/apr/ -I/usr/local/include/ -L/usr/local/lib/ -lboost_system -lboost_program_options -lboost_regex -lboost_thread -lssh2 -llog4cxx -lzmq -ljson -lyaml `ls ../../src/*.cpp | xargs` -o ../../../bin/linux/masspinger

