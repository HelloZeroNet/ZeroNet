#!/bin/sh
set -e

arg_push=

case "$1" in
    --push) arg_push=y ; shift ;;
esac

default_suffix=alpine
prefix="${1:-local/}"

for dokerfile in dockerfiles/Dockerfile.* ; do
    suffix="`echo "$dokerfile" | sed 's/.*\/Dockerfile\.//'`"
    image_name="${prefix}zeronet:$suffix"

    latest=""
    t_latest=""
    if [ "$suffix" = "$default_suffix" ] ; then
        latest="${prefix}zeronet:latest"
        t_latest="-t ${latest}"
    fi

    echo "DOCKER BUILD $image_name"
    docker build -f "$dokerfile" -t "$image_name" $t_latest .
    if [ -n "$arg_push" ] ; then
        docker push "$image_name"
        if [ -n "$latest" ] ; then
            docker push "$latest"
        fi
    fi
done
