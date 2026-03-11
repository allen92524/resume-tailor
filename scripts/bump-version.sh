#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

usage() {
    echo "Usage: $0 <patch|minor|major>"
    echo ""
    echo "Creates a version tag based on the latest git tag."
    echo "No files are modified — versioning is tag-only."
    exit 1
}

[[ $# -ne 1 ]] && usage

BUMP_TYPE="$1"
if [[ "$BUMP_TYPE" != "patch" && "$BUMP_TYPE" != "minor" && "$BUMP_TYPE" != "major" ]]; then
    usage
fi

cd "$PROJECT_ROOT"

# Get current version from the latest git tag, fall back to VERSION file
CURRENT_VERSION=$(git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//' || cat VERSION | tr -d '[:space:]')
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Bump
case "$BUMP_TYPE" in
    patch) PATCH=$((PATCH + 1)) ;;
    minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
    major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"
TAG="v$NEW_VERSION"
echo "Bumping $BUMP_TYPE: $CURRENT_VERSION -> $NEW_VERSION"

# Create annotated tag on current HEAD
git tag -a "$TAG" -m "release: $TAG"

echo "Created tag $TAG"
echo "Run 'git push origin $TAG' to push to GitHub."
