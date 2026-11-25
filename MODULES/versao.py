"""Versão do CODOC — única fonte de verdade, importada tanto pela própria
interface (rodapé da aba HOME e diálogo About Us) quanto por
packaging/deb/build.sh (que a usa como padrão ao gerar o .deb).

Ver packaging/VERSIONING.md para as regras de quando subir MAJOR, MINOR ou
PATCH. A cada mudança que altere a versão, atualize o valor abaixo e
adicione a entrada correspondente no topo de packaging/deb/changelog (mesmo
número, os dois têm que bater)."""

VERSAO = "2.3.0-1"
