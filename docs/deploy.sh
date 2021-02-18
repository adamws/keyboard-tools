#!/usr/bin/env sh

# Build and deploy documentation with github actions

# abort on errors
set -e

# install and build
echo "==> Dependencies install\n"
npm install

echo "==> Build\n"
npm run build

# navigate into the build output directory
cd src/.vuepress/dist

echo "==> Prepare to deploy\n"
git init
git config user.name "${GITHUB_ACTOR}"
git config user.email "${GITHUB_ACTOR}@users.noreply.github.com"

if [ -z "$(git status --porcelain)" ]; then
    echo "Something went wrong" && \
    echo "Exiting..."
    exit 0
fi

echo "==> Start deploying"
git add -A
git commit -m 'Deploy documentation'

DEPLOY_REPO="https://${ACCESS_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
git push --force $DEPLOY_REPO master:gh-pages

rm -fr .git

cd $GITHUB_WORKSPACE
echo "==> Deploy succeeded"
