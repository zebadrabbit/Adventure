#!/bin/bash
# Helper script to reset a user's password in the Docker container

if [ $# -ne 2 ]; then
    echo "Usage: $0 <username> <password>"
    echo "Example: $0 myuser newpassword123"
    exit 1
fi

docker-compose exec web python run.py reset-password "$1" "$2"
