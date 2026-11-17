#!/bin/bash
# Monta o pacote codoc_<versão>_amd64.deb a partir do estado atual do repo.
#
# Uso:
#   packaging/deb/build.sh [versão]
#   INCLUDE_BIN_ARCHIVES=1 packaging/deb/build.sh     # inclui boost/Vina-GPU (≈150 MB)
#
# A versão segue MAJOR.MINOR.PATCH-N (ver packaging/VERSIONING.md antes de
# escolher o próximo número: PATCH para bug fix, MINOR para funcionalidade
# nova sem quebrar nada, MAJOR para mudança incompatível; N é a revisão de
# empacotamento, só sobe sozinha se for uma mudança que não toca em
# CODOC.py nem MODULES/). Sem argumento, usa MODULES/versao.py (fonte única —
# é o mesmo valor mostrado no rodapé da HOME e em Help > About). Lembre de:
# 1) atualizar MODULES/versao.py, 2) adicionar a entrada correspondente no
# topo de packaging/deb/changelog, antes de rodar este script.
#
# O que entra em /opt/codoc: CODOC.py, MODULES/, ICONS/, TUTORIALS/, LICENSE.txt
# e os binários do Vina em BIN/. Ficam de FORA os dados de trabalho do usuário
# (PROJECTS, BASE, BENCHMARK, TEST) e, por padrão, os dois arquivos
# grandes boost_1_84_0.tar.gz e Vina-GPU-2.1.zip: o próprio CODOC os baixa da
# release "deps-v1" do GitHub ao instalar os requisitos (ver
# MODULES/module_requirements.py:_ensure_bundled_archive). INCLUDE_BIN_ARCHIVES=1
# os embute no pacote (instalação offline).
#
# O .deb resultante é gravado em packaging/dist/.

set -euo pipefail
umask 022   # garante dirs 755 / arquivos 644 no staging, independente do umask local

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DIST_DIR="$PROJECT_ROOT/packaging/dist"
VERSAO_CODIGO="$(sed -n 's/^VERSAO = "\(.*\)"$/\1/p' "$PROJECT_ROOT/MODULES/versao.py")"
VERSAO_CHANGELOG="$(sed -n '1s/^codoc (\(.*\)).*/\1/p' "$SCRIPT_DIR/changelog")"
if [ -z "$VERSAO_CODIGO" ] || [ "$VERSAO_CODIGO" != "$VERSAO_CHANGELOG" ]; then
    echo "build.sh: MODULES/versao.py ($VERSAO_CODIGO) e o topo de packaging/deb/changelog" >&2
    echo "          ($VERSAO_CHANGELOG) estão em versões diferentes — atualize os dois" >&2
    echo "          antes de empacotar (ver packaging/VERSIONING.md)." >&2
    exit 1
fi
VERSION="${1:-$VERSAO_CODIGO}"

for tool in dpkg-deb rsync gzip; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "build.sh: dependência ausente: $tool" >&2
        exit 1
    fi
done

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "==> Preparando staging em $STAGE"
mkdir -p \
    "$STAGE/DEBIAN" \
    "$STAGE/opt/codoc" \
    "$STAGE/usr/bin" \
    "$STAGE/usr/share/applications" \
    "$STAGE/usr/share/doc/codoc" \
    "$STAGE/usr/share/lintian/overrides"

echo "==> Copiando arquivos da aplicação para /opt/codoc"
RSYNC_EXCLUDES=(--exclude='__pycache__/' --exclude='*.pyc' --exclude='.git/')
if [ "${INCLUDE_BIN_ARCHIVES:-0}" != "1" ]; then
    RSYNC_EXCLUDES+=(--exclude='BIN/boost_1_84_0.tar.gz' --exclude='BIN/Vina-GPU-2.1.zip')
fi
rsync -a "${RSYNC_EXCLUDES[@]}" \
    --exclude='.~*' --exclude='~$*' \
    "$PROJECT_ROOT/CODOC.py" \
    "$PROJECT_ROOT/MODULES" \
    "$PROJECT_ROOT/ICONS" \
    "$PROJECT_ROOT/BIN" \
    "$PROJECT_ROOT/TUTORIALS" \
    "$PROJECT_ROOT/LICENSE.txt" \
    "$STAGE/opt/codoc/"

# Normaliza permissões: o diretório de trabalho local pode ter modos
# incomuns; o pacote precisa ser legível/executável por qualquer usuário.
find "$STAGE/opt/codoc" -type d -exec chmod 755 {} +
find "$STAGE/opt/codoc" -type f -exec chmod 644 {} +
chmod 755 "$STAGE/opt/codoc/CODOC.py" \
          "$STAGE/opt/codoc/BIN/vina_1.2.5_linux_x86_64" \
          "$STAGE/opt/codoc/BIN/vina_split_1.2.5_linux_x86_64"

echo "==> Instalando launcher e menu"
install -m 755 "$SCRIPT_DIR/codoc-launcher" "$STAGE/usr/bin/codoc"
# O arquivo se chama CODOC.desktop (e não codoc.desktop) de propósito: é o mesmo nome que o
# splash do CODOC grava em ~/.local/share/applications; com o mesmo desktop-file-id a versão
# do usuário SUBSTITUI a do sistema, em vez de aparecer duas entradas "CODOC" no menu.
install -m 644 "$SCRIPT_DIR/CODOC.desktop" "$STAGE/usr/share/applications/CODOC.desktop"
# copyright no formato DEP-5, apontando para /usr/share/common-licenses/GPL-3 (o texto
# completo da GPL continua em /opt/codoc/LICENSE.txt):
install -m 644 "$SCRIPT_DIR/copyright" "$STAGE/usr/share/doc/codoc/copyright"
install -m 644 "$SCRIPT_DIR/lintian-overrides" "$STAGE/usr/share/lintian/overrides/codoc"
install -m 644 "$PROJECT_ROOT/README.txt" "$STAGE/usr/share/doc/codoc/README.txt"
gzip -9nc "$SCRIPT_DIR/changelog" > "$STAGE/usr/share/doc/codoc/changelog.Debian.gz"
chmod 644 "$STAGE/usr/share/doc/codoc/changelog.Debian.gz"

echo "==> Gerando DEBIAN/control (versão $VERSION)"
INSTALLED_SIZE="$(du -sk "$STAGE/opt/codoc" | cut -f1)"
sed \
    -e "s/@VERSION@/$VERSION/" \
    -e "s/@INSTALLED_SIZE@/$INSTALLED_SIZE/" \
    "$SCRIPT_DIR/control.in" > "$STAGE/DEBIAN/control"

install -m 755 "$SCRIPT_DIR/postinst" "$STAGE/DEBIAN/postinst"
install -m 755 "$SCRIPT_DIR/postrm" "$STAGE/DEBIAN/postrm"

mkdir -p "$DIST_DIR"
OUT_DEB="$DIST_DIR/codoc_${VERSION}_amd64.deb"

echo "==> Empacotando $OUT_DEB"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT_DEB"

if command -v lintian >/dev/null 2>&1; then
    echo "==> lintian (informativo, não interrompe o build)"
    lintian "$OUT_DEB" || true
fi

echo "==> Pronto: $OUT_DEB"
