#!/usr/bin/env bash
#
# release.sh — Create a release branch, bump version, tag, publish to npm,
#               and create a GitHub release.
#
# Usage:
#   npm run release -- 1.0.0
#
set -e

VERSION="$1"

if [ -z "$VERSION" ]; then
  echo "Usage: npm run release -- <version>"
  echo "  e.g. npm run release -- 1.0.0"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# Validate semver (basic check)
if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$'; then
  echo "Error: '$VERSION' is not a valid semver version"
  exit 1
fi

# Ensure gh CLI is available
if ! command -v gh &> /dev/null; then
  echo "Error: GitHub CLI (gh) is required but not installed."
  echo "Install it: https://cli.github.com/"
  exit 1
fi

# Ensure working tree is clean
if [ -n "$(git status --porcelain)" ]; then
  echo "Error: Working tree is not clean. Commit or stash changes first."
  exit 1
fi

CURRENT=$(node -p "require('./package.json').version")
BRANCH="release/v$VERSION"
TAG="v$VERSION"

echo "Releasing @jhillrva/agentic-filesystem"
echo "  Current version: $CURRENT"
echo "  New version:     $VERSION"
echo "  Branch:          $BRANCH"
echo "  Tag:             $TAG"
echo ""

# Create and switch to release branch
echo "Creating release branch: $BRANCH"
git checkout -b "$BRANCH"

# Bump version in package.json
npm version "$VERSION" --no-git-tag-version

# Update lockfile
echo "Running npm install to update package-lock..."
npm install

# Commit the version bump
echo ""
echo "Committing version bump..."
git add package.json package-lock.json
git commit -m "$(cat <<EOF
release: v$VERSION
)"

# Tag
echo "Creating tag: $TAG"
git tag "$TAG"

# Push branch and tag
echo ""
echo "Pushing branch and tag..."
git push -u origin "$BRANCH"
git push origin "$TAG"

# Publish to npm
echo ""
echo "Publishing @jhillrva/agentic-filesystem@$VERSION to npm..."
npm publish --access public

# Create GitHub release
echo ""
echo "Creating GitHub release..."
gh release create "$TAG" \
  --title "v$VERSION" \
  --generate-notes \
  --target "$BRANCH"

echo ""
echo "Done! Released @jhillrva/agentic-filesystem@$VERSION"
echo "  npm:    https://www.npmjs.com/package/@jhillrva/agentic-filesystem"
echo "  branch: $BRANCH"
echo "  tag:    $TAG"
