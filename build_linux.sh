#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
build_env="$project_dir/.venv-build-linux"

cd "$project_dir"
python3 -m venv "$build_env"
"$build_env/bin/python" -m pip install --upgrade pip
"$build_env/bin/python" -m pip install -r requirements-build.txt
"$build_env/bin/python" -m unittest -v
"$build_env/bin/python" -m PyInstaller --clean --noconfirm Ani-Watch.spec

echo "Executável criado em: $project_dir/dist/Ani-Watch"
