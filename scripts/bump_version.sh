#!/bin/bash
# bump_version.sh - Semantic version bumping script
# Usage: ./scripts/bump_version.sh [major|minor|patch]

set -e

VERSION_FILE="VERSION"

if [ ! -f "$VERSION_FILE" ]; then
    echo "Error: VERSION file not found"
    exit 1
fi

# Read current version
CURRENT_VERSION=$(cat "$VERSION_FILE" | tr -d '[:space:]')

# Parse version components
if [[ ! $CURRENT_VERSION =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    echo "Error: Invalid version format in VERSION file: $CURRENT_VERSION"
    echo "Expected format: MAJOR.MINOR.PATCH (e.g., 1.2.3)"
    exit 1
fi

MAJOR="${BASH_REMATCH[1]}"
MINOR="${BASH_REMATCH[2]}"
PATCH="${BASH_REMATCH[3]}"

# Determine bump type (default to patch)
BUMP_TYPE="${1:-patch}"

case "$BUMP_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        echo "Bumping MAJOR version: $CURRENT_VERSION → $MAJOR.$MINOR.$PATCH"
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        echo "Bumping MINOR version: $CURRENT_VERSION → $MAJOR.$MINOR.$PATCH"
        ;;
    patch)
        PATCH=$((PATCH + 1))
        echo "Bumping PATCH version: $CURRENT_VERSION → $MAJOR.$MINOR.$PATCH"
        ;;
    *)
        echo "Error: Invalid bump type '$BUMP_TYPE'"
        echo "Usage: $0 [major|minor|patch]"
        echo ""
        echo "  major - Increment major version (breaking changes)"
        echo "  minor - Increment minor version (new features)"
        echo "  patch - Increment patch version (bug fixes) [default]"
        exit 1
        ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"

# Update VERSION file
echo "$NEW_VERSION" > "$VERSION_FILE"
echo "✓ Updated VERSION file: $NEW_VERSION"

# Update CHANGELOG.md if it exists
if [ -f "CHANGELOG.md" ]; then
    TODAY=$(date +%Y-%m-%d)

    # Check if there's an [Unreleased] section
    if grep -q "\[Unreleased\]" CHANGELOG.md; then
        # Replace [Unreleased] with the new version and date
        sed -i.bak "s/## \[Unreleased\]/## [Unreleased]\n\n## [$NEW_VERSION] - $TODAY/" CHANGELOG.md
        rm -f CHANGELOG.md.bak
        echo "✓ Updated CHANGELOG.md with version $NEW_VERSION"
    else
        echo "⚠ Warning: No [Unreleased] section found in CHANGELOG.md"
        echo "  Please manually update CHANGELOG.md"
    fi
fi

echo ""
echo "Version bumped successfully!"
echo "Current version: $NEW_VERSION"
echo ""
echo "Next steps:"
echo "  1. Review changes: git diff VERSION CHANGELOG.md"
echo "  2. Commit: git add VERSION CHANGELOG.md && git commit -m 'chore: bump version to $NEW_VERSION'"
echo "  3. Tag: git tag -a v$NEW_VERSION -m 'Release $NEW_VERSION'"
echo "  4. Push: git push && git push --tags"
