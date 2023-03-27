#!/bin/sh

set -o nounset
set -o errexit

if [ -z "$(ssh-keygen -F $SSH_HOST)" ]; then
    echo "Adding host to known hosts"
    ssh-keyscan -H $SSH_HOST >> ~/.ssh/known_hosts 2> /dev/null
fi

SCRIPT_DIR="$(dirname "${0}")"

rsync -avP --exclude="letsencrypt" --exclude="flower" --exclude=".env" \
  ${SCRIPT_DIR}/ $SSH_USER@$SSH_HOST:/home/$SSH_USER/app

ssh $SSH_USER@$SSH_HOST << EOF
    cd app
    export TAG=$TAG
    docker-compose down -v --rmi="all"
    docker-compose pull
    docker-compose up -d --force-recreate
EOF
