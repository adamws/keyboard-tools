#!/bin/sh

set -o nounset
set -o errexit

tag () {
    docker tag admwscki/$1:circleci admwscki/$1:$2
    docker push admwscki/$1:$2
    docker tag admwscki/$1:circleci admwscki/$1:latest
    docker push admwscki/$1:latest
}

tag keyboard-tools-server $TAG
tag keyboard-tools-kicad $TAG
