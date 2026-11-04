#!/bin/bash
# Start nemo on this machine: ./run.sh, then open http://127.0.0.1:8473/new. Rooms and logs stay in run/.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="${NEMO_RUN:-$HERE/run}"
PY="${NEMO_PYTHON:-$HERE/.venv/bin/python}"
mkdir -p "$RUN/rooms" "$RUN/approot"
if [ ! -s "$RUN/cookie-secret" ]; then
    (umask 077; "$PY" -c 'import secrets; print(secrets.token_hex(32))' > "$RUN/cookie-secret")
fi
export CHAINLIT_AUTH_SECRET="$(cat "$RUN/cookie-secret")"
export PYTHONPATH="$HERE/src" NEMO_ROOMS="$RUN/rooms" NEMO_SEED="$HERE/seed" NEMO_DEP_GRAPH="$HERE/skin/vendor"
export CHAINLIT_APP_ROOT="$RUN/approot" PROTO_LOG="$RUN/nemo.log" PYTHONDONTWRITEBYTECODE=1
cd "$RUN/approot"
exec "$PY" -m chainlit run "$HERE/skin/PROTOTYPE_conversation_app.py" -h --host 127.0.0.1 --port "${NEMO_PORT:-8473}"
