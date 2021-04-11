#!/bin/sh

set -o nounset
set -o errexit
set -o pipefail

build_and_push () {
    docker build -t admwscki/$1:$2 -f $3 $4
    docker tag admwscki/$1:$2 admwscki/$1:latest
    #docker push admwscki/$1:$2
    #docker push admwscki/$1:latest
}

build_and_push keyboard-tools-server $TAG deploy/Dockerfile .
build_and_push keyboard-tools-kicad $TAG kicad-api/Dockerfile kicad-api
