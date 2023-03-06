#!/bin/sh

set -o nounset
set -o errexit

# Build and deploy documentation

# install and build
echo "==> Dependencies install\n"
npm install

echo "==> Build\n"
npm run docs:build

echo "==> Configure git\n"
git config --global user.name "CircleCI"
git config --global user.email "${CIRCLE_PROJECT_USERNAME}@users.noreply.github.com"

echo "==> Prepare to deploy\n"

# navigate into the build output directory
cd src/.vitepress

git clone --depth=1 --single-branch --branch gh-pages $CIRCLE_REPOSITORY_URL gh-pages
cd gh-pages

# remove everything except "release" directory
git rm -rf .
git checkout HEAD -- release || true

# move fresh build to repository
cp -r ../dist/* .

mkdir .circleci
wget https://raw.githubusercontent.com/adamws/keyboard-tools/master/.circleci/ghpages-config.yml -O .circleci/config.yml
touch .nojekyll

echo "==> Start deploying"
git add -A
git commit -m "Deploy documentation: ${CIRCLE_SHA1}"

git push

rm -fr .git

echo "==> Deploy succeeded"
