#!/usr/bin/env bash
# Sets up the `develop` stage on top of Microsoft's Python devcontainer
# image (which already provides the `vscode` user, git, sudo, and curl).
set -euo pipefail

uv_version=$1
claude_code_version=$2
pyright_version=$3
snip_version=$4

apt-get update
apt-get install -y --no-install-recommends libpq-dev
apt-get clean
rm -rf /var/lib/apt/lists/*

curl -LsSf "https://releases.astral.sh/github/uv/releases/download/${uv_version}/uv-installer.sh" \
    | sudo -u vscode env HOME=/home/vscode INSTALLER_NO_MODIFY_PATH=1 sh
ln -s /home/vscode/.local/bin/uv /usr/local/bin/uv
ln -s /home/vscode/.local/bin/uvx /usr/local/bin/uvx

curl -fsSL https://claude.ai/install.sh \
    | sudo -u vscode env HOME=/home/vscode bash -s "$claude_code_version"
ln -s /home/vscode/.local/bin/claude /usr/local/bin/claude

# For the pyright-lsp Claude Code plugin — see .claude/README.md.
sudo -u vscode env HOME=/home/vscode /usr/local/bin/uv tool install "pyright==${pyright_version}"
ln -s /home/vscode/.local/bin/pyright /usr/local/bin/pyright
ln -s /home/vscode/.local/bin/pyright-langserver /usr/local/bin/pyright-langserver

# For the snip Claude Code PreToolUse hook — see .claude/README.md. Not on
# PyPI/npm like the tools above, so fetched as a release tarball and
# checksum-verified against the project's own published checksums.txt
# instead of trusting a curl-pipe-to-sh installer.
snip_arch="$(dpkg --print-architecture)"
snip_asset="snip_${snip_version}_linux_${snip_arch}.tar.gz"
snip_tmpdir="$(mktemp -d)"
sudo chmod a+rwx "$snip_tmpdir"
curl -LsSf -o "${snip_tmpdir}/${snip_asset}" \
    "https://github.com/edouard-claude/snip/releases/download/v${snip_version}/${snip_asset}"
curl -LsSf -o "${snip_tmpdir}/checksums.txt" \
    "https://github.com/edouard-claude/snip/releases/download/v${snip_version}/checksums.txt"
(cd "$snip_tmpdir" && grep " ${snip_asset}\$" checksums.txt | sha256sum -c -)
tar -xzf "${snip_tmpdir}/${snip_asset}" -C "$snip_tmpdir" snip
sudo -u vscode install -Dm755 "${snip_tmpdir}/snip" /home/vscode/.local/bin/snip
rm -rf "$snip_tmpdir"
ln -s /home/vscode/.local/bin/snip /usr/local/bin/snip
