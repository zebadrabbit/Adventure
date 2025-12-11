#!/usr/bin/env python3
"""
Quick script to clear perception markers via the test API endpoint.
Run this while the Flask app is running to clear stale markers.
"""

import sys

import requests


def clear_markers():
    """Call the clear_perception_markers endpoint."""
    url = "http://localhost:5000/api/test/clear_perception_markers"

    try:
        # You'll need to be logged in - this will use your browser session
        response = requests.post(url)

        if response.status_code == 200:
            data = response.json()
            print(f"✓ Success: {data.get('message', 'Markers cleared')}")
            return 0
        elif response.status_code == 403:
            print("✗ Error: Endpoint requires DEBUG or TESTING mode")
            print("  Set DEBUG=True in your config or run tests")
            return 1
        else:
            print(f"✗ Error: {response.status_code} - {response.text}")
            return 1

    except requests.exceptions.ConnectionError:
        print("✗ Error: Could not connect to Flask app")
        print("  Make sure the app is running on localhost:5000")
        return 1
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(clear_markers())
