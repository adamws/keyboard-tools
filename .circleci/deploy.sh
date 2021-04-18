#!/bin/sh

set -o nounset
set -o errexit

if [ -z "$(ssh-keygen -F $SSH_HOST)" ]; then
    echo "Adding host to known hosts"
    ssh-keyscan -H $SSH_HOST >> ~/.ssh/known_hosts 2> /dev/null
fi

scp deploy/docker-compose.yml deploy/production.env $SSH_USER@$SSH_HOST:/home/$SSH_USER/app
ssh $SSH_USER@$SSH_HOST <<'EOL'
    cd app
    docker-compose up -d
EOL
