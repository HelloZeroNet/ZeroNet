#!/bin/sh
set -e

do_alpine() {
    local deps="python3 py3-pip openssl tor"
    local makedeps="python3-dev gcc g++ libffi-dev musl-dev make automake autoconf libtool"

    case "$1" in
    install)
        apk --update --no-cache --no-progress add $deps $makedeps
        ;;
    remove-makedeps)
        apk del $makedeps
        ;;
    esac
}

do_ubuntu() {
    local deps="python3 python3-pip openssl tor"
    local makedeps="python3-dev gcc g++ libffi-dev make automake autoconf libtool"

    case "$1" in
    install)
        apt-get update && \
        apt-get install --no-install-recommends -y $deps $makedeps && \
        rm -rf /var/lib/apt/lists/*
        ;;
    remove-makedeps)
        apt-get remove -y $makedeps
        ;;
    esac
}

if test -f /etc/os-release ; then
    . /etc/os-release
elif test -f /usr/lib/os-release ; then
    . /usr/lib/os-release
else
    echo "No such file: /etc/os-release" > /dev/stderr
    exit 1
fi

case "$ID" in
    ubuntu) do_ubuntu "$@" ;;
    alpine) do_alpine "$@" ;;
    *)
        echo "Unsupported OS ID: $ID" > /dev/stderr
        exit 1
esac
