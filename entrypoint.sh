#!/bin/sh

python src/main.py "$@" || exit_code=$?
exit_code=${exit_code:-0}

# Fix file ownership so host user can access generated files.
# HOST_UID / HOST_GID are passed from docker-compose.yml.
if [ -n "$HOST_UID" ]; then
    chown -R "${HOST_UID}:${HOST_GID:-$HOST_UID}" /output 2>/dev/null || true
    chown -R "${HOST_UID}:${HOST_GID:-$HOST_UID}" /root/.resume-tailor 2>/dev/null || true
fi

exit $exit_code
