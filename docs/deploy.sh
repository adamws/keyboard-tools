#!/bin/sh

set -o nounset
set -o errexit

# Build and deploy documentation

# install and build
echo "==> Dependencies install\n"
npm install

echo "==> Build\n"
npm run build

# navigate into the build output directory
cd src/.vuepress/dist

echo "==> Prepare to deploy\n"

wget https://raw.githubusercontent.com/adamws/keyboard-tools/master/.circleci/config.yml -P .circleci
touch .nojekyll
git init
git config user.name "CircleCI"
git config user.email "${CIRCLE_PROJECT_USERNAME}@users.noreply.github.com"

if [ -z "$(git status --porcelain)" ]; then
    echo "Something went wrong" && \
    echo "Exiting..."
    exit 0
fi

echo "==> Start deploying"
git add -A
git commit -m 'Deploy documentation'

git push --force $CIRCLE_REPOSITORY_URL master:gh-pages

rm -fr .git

echo "==> Deploy succeeded"
