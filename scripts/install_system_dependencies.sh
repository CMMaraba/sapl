#!/usr/bin/env bash
set -euo pipefail

if [[ $(id -u) != 0 ]]; then
    printf '%s\n' 'Execute como root para instalar os pacotes APT.' >&2
    exit 1
fi
. /etc/os-release
if [[ ${ID:-} != ubuntu || ${VERSION_ID:-} != 26.04 ]]; then
    printf '%s\n' 'Esta branch foi validada com os pacotes do Ubuntu 26.04.' >&2
    exit 1
fi
sapl_repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
sapl_manifest="$sapl_repo_dir/system-dependencies-apt.txt"
sapl_packages=()
while IFS= read -r sapl_line || [[ -n $sapl_line ]]; do
    [[ -z $sapl_line || $sapl_line == \#* ]] && continue
    if [[ ! $sapl_line =~ ^[a-z0-9][a-z0-9+.-]*$ ]]; then
        printf '%s\n' 'Nome de pacote inválido no manifesto APT.' >&2
        exit 1
    fi
    sapl_packages+=("$sapl_line")
done < "$sapl_manifest"
[[ ${#sapl_packages[@]} -gt 0 ]]
sapl_install_log=$(mktemp /tmp/sapl-system-install.XXXXXX)
trap 'rm -f -- "$sapl_install_log"' EXIT
if ! apt-get update -qq >"$sapl_install_log" 2>&1; then
    tail -n 30 "$sapl_install_log" >&2
    exit 1
fi
if ! DEBIAN_FRONTEND=noninteractive apt-get install -qq "${sapl_packages[@]}" >"$sapl_install_log" 2>&1; then
    tail -n 30 "$sapl_install_log" >&2
    exit 1
fi
