#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION_FILE="$PROJECT_ROOT/VERSION"
CHART_FILE="$PROJECT_ROOT/helm/resume-tailor/Chart.yaml"

usage() {
    echo "Usage: $0 <patch|minor|major>"
    exit 1
}

[[ $# -ne 1 ]] && usage

BUMP_TYPE="$1"
if [[ "$BUMP_TYPE" != "patch" && "$BUMP_TYPE" != "minor" && "$BUMP_TYPE" != "major" ]]; then
    usage
fi

# Read current version
CURRENT_VERSION=$(tr -d '[:space:]' < "$VERSION_FILE")
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Bump
case "$BUMP_TYPE" in
    patch) PATCH=$((PATCH + 1)) ;;
    minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
    major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"
echo "Bumping $BUMP_TYPE: $CURRENT_VERSION -> $NEW_VERSION"

# Update VERSION file
echo "$NEW_VERSION" > "$VERSION_FILE"

# Update Chart.yaml version (portable: works on both GNU sed and macOS BSD sed)
if sed --version >/dev/null 2>&1; then
    # GNU sed
    sed -i "s/^version: .*/version: $NEW_VERSION/" "$CHART_FILE"
else
    # BSD sed (macOS)
    sed -i '' "s/^version: .*/version: $NEW_VERSION/" "$CHART_FILE"
fi

# Commit and tag
cd "$PROJECT_ROOT"
git add VERSION helm/resume-tailor/Chart.yaml
git commit -m "release: v$NEW_VERSION"
git tag "v$NEW_VERSION"

echo "Released v$NEW_VERSION"
echo "Run 'make release-push' to push to GitHub."
