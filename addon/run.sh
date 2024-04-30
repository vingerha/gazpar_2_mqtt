#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

# Do not require that bash variables are set before use:
set +u
MYDIR="$(realpath .)"
MYDIR="${MYDIR%/}/"
