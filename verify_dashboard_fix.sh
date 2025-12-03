#!/bin/bash
# Verification script for dashboard fix

echo "=== Dashboard Fix Verification ==="
echo ""

echo "1. Checking file locations..."
if [ -f "app/static/js/dashboard.js" ]; then
    SIZE=$(stat -f%z "app/static/js/dashboard.js" 2>/dev/null || stat -c%s "app/static/js/dashboard.js" 2>/dev/null)
    echo "   ✓ app/static/js/dashboard.js exists ($SIZE bytes)"
    if [ "$SIZE" -gt 1000 ]; then
        echo "   ✓ File has content"
    else
        echo "   ✗ File is too small or empty!"
        exit 1
    fi
else
    echo "   ✗ app/static/js/dashboard.js NOT FOUND!"
    exit 1
fi

if [ -f "app/static/dashboard.js" ]; then
    echo "   ✗ WARNING: Duplicate app/static/dashboard.js found (should be removed)"
else
    echo "   ✓ No duplicate file in app/static/"
fi

echo ""
echo "2. Checking JavaScript structure..."
if grep -q "updatePartyUI()" app/static/js/dashboard.js; then
    echo "   ✓ updatePartyUI() function found"
else
    echo "   ✗ updatePartyUI() function NOT found!"
    exit 1
fi

if grep -q "begin-adventure-btn" app/static/js/dashboard.js; then
    echo "   ✓ Button reference found"
else
    echo "   ✗ Button reference NOT found!"
    exit 1
fi

if grep -q "console.log.*Dashboard.*Initialized" app/static/js/dashboard.js; then
    echo "   ✓ Debug logging present"
else
    echo "   ✗ Debug logging NOT found!"
fi

echo ""
echo "3. Checking IIFE structure..."
IIFE_OPEN=$(grep -c "^(function ()" app/static/js/dashboard.js)
IIFE_CLOSE=$(grep -c "^})();" app/static/js/dashboard.js)
echo "   IIFE opening: $IIFE_OPEN"
echo "   IIFE closing: $IIFE_CLOSE"
if [ "$IIFE_OPEN" -eq 1 ] && [ "$IIFE_CLOSE" -eq 1 ]; then
    echo "   ✓ Single IIFE structure looks correct"
else
    echo "   ⚠ Unusual IIFE structure (may be okay)"
fi

echo ""
echo "=== Verification Complete ==="
echo ""
echo "To test:"
echo "  1. Start server: python3 run.py server"
echo "  2. Visit: http://localhost:5000/dashboard"
echo "  3. Open browser DevTools (F12) → Console tab"
echo "  4. Look for: [Dashboard] Initialized: {checkboxes: X, ...}"
echo "  5. Select 1-4 characters - button should enable!"
