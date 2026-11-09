#!/usr/bin/env bash
set -euo pipefail

store=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
sources=${1:-}
base=ssh://forgejo@gentedelcondado.es:2233/wolfbelmi88
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT

apps=()
stage_app() {
  local repo=$1 path=$2 app=$3 checkout revision
  if [[ -n "$sources" ]]; then
    checkout="$sources/$repo"
  else
    checkout="$stage/$repo"
    git clone --quiet --depth 1 --single-branch --branch main -- "$base/$repo.git" "$checkout"
  fi
  revision=$(git -C "$checkout" rev-parse HEAD)
  if git -C "$checkout" ls-tree -r "$revision" -- "$path" |
    awk '$1 == "120000" || $1 == "160000" {bad = 1} END {exit !bad}'; then
    printf '%s/%s contiene enlaces simbólicos o submódulos.\n' "$repo" "$path" >&2
    return 1
  fi
  mkdir -p -- "$stage/apps/$app"
  git -C "$checkout" archive "$revision:$path" | tar -xf - -C "$stage/apps/$app"
  test -s "$stage/apps/$app/config.yaml"
  test -s "$stage/apps/$app/Dockerfile"
  test ! -L "$store/$app"
  apps+=("$app")
  printf '%s ← %s@%s (%s)\n' "$app" "$repo" "$revision" "$path"
}

stage_app HA-Private-Git-Manager private_git_manager private_git_manager
stage_app jacksignal custom_components jacksignal_installer
stage_app pivigia addons/pivigia pivigia
stage_app headscale-gateway addons/headscale_gateway headscale_gateway

# Validate all snapshots before changing the working tree.
for app in "${apps[@]}"; do
  rm -rf -- "$store/$app"
  mv -- "$stage/apps/$app" "$store/$app"
done
