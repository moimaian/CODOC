# Empacotamento .deb do CODOC

## Build

```bash
packaging/deb/build.sh              # versão = MODULES/versao.py (ex.: 1.0.0-1)
packaging/deb/build.sh 1.0.0-2      # versão explícita
INCLUDE_BIN_ARCHIVES=1 packaging/deb/build.sh   # embute boost + Vina-GPU (≈150 MB a mais)
```

Gera `packaging/dist/codoc_<versão>_amd64.deb`. Antes de gerar um novo pacote,
atualize `MODULES/versao.py` e o topo de `packaging/deb/changelog` com o mesmo
número — o script recusa rodar se os dois divergirem. Regras para escolher o
número (MAJOR/MINOR/PATCH-N) em [`packaging/VERSIONING.md`](../VERSIONING.md).

Dependências para *buildar* (não para instalar/usar): `dpkg-deb`, `rsync`
(já vêm em qualquer Debian/Ubuntu/Mint). `lintian` é opcional.

## O que vai no pacote

Em `/opt/codoc`: `CODOC.py`, `MODULES/`, `ICONS/`, `TUTORIALS/`, `LICENSE.txt` e
os binários do Vina 1.2.5 em `BIN/`.

**Não** vão: `PROJECTS`, `BASE` (bancos de ligantes/alvos, vários GB),
`BENCHMARK`, `TEST` — são dados de trabalho do usuário. Também ficam de fora, por padrão,
`BIN/boost_1_84_0.tar.gz` e `BIN/Vina-GPU-2.1.zip` (150 MB): o CODOC os baixa da release
`deps-v1` do GitHub quando o usuário usa "Install requirements" para compilar o Vina-GPU.
Use `INCLUDE_BIN_ARCHIVES=1` para uma instalação offline.

## Instalar

```bash
sudo apt install ./packaging/dist/codoc_<versão>_amd64.deb
```

Isso cria:
- `/opt/codoc` — código-fonte da aplicação (arquivo do pacote, gerenciado pelo dpkg);
- `/usr/bin/codoc` — launcher;
- `/usr/share/applications/CODOC.desktop` — entrada no menu.

## O que acontece no primeiro clique em "CODOC" no menu

1. `/usr/bin/codoc` sincroniza `/opt/codoc` → `$HOME/CODOC` (sem tocar em `PROJECTS`,
   `BASE`, `TEST`, `BENCHMARK`) e abre o CODOC.
2. Sem `$HOME/.venv/CODOC`, roda `python3 $HOME/CODOC/CODOC.py`, que chama
   `bootstrap_pyqt5(interactive=True, reexec=True)` em
   `MODULES/module_requirements.py`: cria o venv com Python 3.10, instala o PyQt5 e se
   reinicia dentro dele. O resto das dependências (RDKit, Meeko, ADFRsuite, Vina-GPU...)
   é instalado pelo menu Help > Install requirements / splash.
3. Com o venv já criado, o launcher usa o python do venv direto — sem a pergunta
   "Continue? [S/n]".
4. O splash (`MODULES/splash_screen.py`) recria `~/.local/share/applications/CODOC.desktop`
   (mesmo nome do arquivo do sistema, então ele substitui o do pacote no menu).

O `.desktop` usa `Terminal=false`: o CODOC abre sem janela de terminal, e quem quiser ver as
saídas ou rodar comandos no ambiente do programa usa o menu Help > Terminal. A primeira
execução (sem venv) pergunta "Continue? [S/n]" no terminal, então o launcher reabre a si
mesmo num emulador de terminal só nessa situação. Instalações de requisitos que usam
`apt-get` pedem a senha por `sudo` quando há terminal e, sem terminal, por `pkexec` (janela
gráfica de autenticação).

## Por que o pacote não cria o venv/instala as dependências no `postinst`

`postinst`/`postrm` rodam como **root** durante `apt install`/`dpkg -i`, quando `$HOME`
não é o do usuário final, e instalar via pip pacotes pesados (RDKit etc.) depende de rede
e, se falhar no meio, deixa o `dpkg` em `half-configured`. Por isso o pacote é fino: só
coloca arquivos em `/opt/codoc`, registra o menu e deixa o bootstrap por-usuário ao
`CODOC.py`.

## Atualizações

`apt upgrade` atualiza `/opt/codoc`; na próxima abertura pelo menu o launcher sincroniza a
versão nova para `$HOME/CODOC` (preservando as pastas de trabalho). O venv não é recriado
por uma atualização.

**Atenção na máquina de desenvolvimento:** o launcher sobrescreve os arquivos de
`~/CODOC` com os do pacote instalado. Se `~/CODOC` for o seu repositório git de trabalho,
alterações ainda não commitadas em `CODOC.py`/`MODULES/` seriam sobrescritas — não instale
o `.deb` na mesma máquina/usuário do repositório (ou faça commit antes).

## Desinstalar

```bash
sudo apt remove codoc     # mantém ~/CODOC e ~/.venv/CODOC
sudo apt purge codoc      # idem — avisa no terminal, mas não apaga nada em $HOME
```

Dados por-usuário (`~/CODOC`, incluindo `~/CODOC/PROJECTS`, e `~/.venv/CODOC`) nunca são
apagados automaticamente pelo pacote.
