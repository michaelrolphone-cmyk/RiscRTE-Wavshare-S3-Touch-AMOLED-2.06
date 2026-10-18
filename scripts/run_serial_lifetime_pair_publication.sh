#!/usr/bin/env bash
set -euo pipefail
: "${GITHUB_SHA:?}" "${GITHUB_WORKSPACE:?}"
export PYTHONDONTWRITEBYTECODE=1
root="$RUNNER_TEMP/wave-canonical-pair"
test ! -e "$root"
mkdir -p "$root"
python3 -m venv "$root/venv"
"$root/venv/bin/python" -m pip install -r scripts/serial_lifetime_publisher_requirements.txt
export PATH="$root/venv/bin:$PATH"
python3 scripts/check_serial_lifetime_publisher_environment.py
revision="$(python3 -c 'import json;print(json.load(open("docs/serial-lifetime-recovery/source-pins.json"))["runtime_revision"])')"
schema_revision="$(python3 -c 'import json;print(json.load(open("docs/serial-lifetime-recovery/source-pins.json"))["frozen_payload_schema"])')"
git init --quiet "$root/runtime"
git -C "$root/runtime" remote add origin https://github.com/michaelrolphone-cmyk/RiscRTE.git
git -C "$root/runtime" fetch --no-tags --depth=1 origin "$revision" "$schema_revision"
git -C "$root/runtime" checkout --quiet --detach "$revision"
python3 - "$root" "$schema_revision" <<'PY'
from pathlib import Path
import subprocess,sys
root=Path(sys.argv[1]);prefix='docs/catalog-payload/1.0.0/'
paths=subprocess.check_output(['git','-C',str(root/'runtime'),'ls-tree','-r','--name-only',sys.argv[2],'--',prefix],text=True).splitlines()
assert paths
for path in paths:
 target=root/'schema'/path.removeprefix(prefix);target.parent.mkdir(parents=True,exist_ok=True)
 target.write_bytes(subprocess.check_output(['git','-C',str(root/'runtime'),'show',sys.argv[2]+':'+path]))
PY
python3 scripts/publish_serial_lifetime_pair.py --assets "$GITHUB_WORKSPACE/release-assets" --runtime "$root/runtime" --schema "$root/schema" --work "$root/publication" --source-revision "$GITHUB_SHA"
