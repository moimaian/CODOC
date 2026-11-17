# Versionamento do CODOC

A versão segue **MAJOR.MINOR.PATCH** (SemVer) para o número que importa (o que
aparece antes do traço); o `-N` depois do traço é a *revisão de empacotamento*,
no sentido estrito do Debian — só sobe quando `packaging/` muda (control.in,
postinst, postrm, codoc-launcher, .desktop...) sem nenhuma mudança de código do
programa. Toda mudança de código reseta o `-N` para `-1`.

A `1.0.0-1` é a primeira versão numerada (até então o rodapé dizia apenas
"v1.0 beta").

**Fonte única do número: [`MODULES/versao.py`](../MODULES/versao.py)** (`VERSAO =
"..."`). É o mesmo valor que:
- aparece no rodapé da aba HOME;
- aparece em Help > About;
- `packaging/deb/build.sh` usa como padrão ao gerar o `.deb`.

`packaging/deb/build.sh` recusa rodar se `MODULES/versao.py` e a primeira linha
de `packaging/deb/changelog` não tiverem o mesmo número — os dois precisam
ser atualizados juntos (ver "Ao gerar um novo .deb" abaixo).

```
1.0.0    -1
└─┬─┘    └┬┘
  │       └─ revisão de empacotamento (só packaging/ mudou)
  └─ versão do programa (MAJOR.MINOR.PATCH)
```

Diferente do CODRUG, o `.deb` do CODOC **não usa época** (`1:`) no campo
`Version`: não existem pacotes anteriores numerados por data que precisem ser
ultrapassados. Se um dia o esquema de numeração mudar de forma que um número
novo seja "menor" que um já publicado, é preciso introduzir a época nesse
momento (`1:`), e ela nunca mais pode ser removida.

## Como decidir qual número sobe

A pergunta não é "quanto código mudou" — é **"alguém que já usa o CODOC
hoje vai precisar fazer algo diferente, ou vai ter algo que parou de
funcionar, por causa desta mudança?"**

- **PATCH** (`1.0.0` → `1.0.1`): corrige um bug, sem mudar nenhum
  comportamento que já era esperado. Ex.: o ajuste do nome da pasta do target
  quando o usuário atribui um "Target name".

- **MINOR** (`1.0.0` → `1.1.0`, zera o patch): funcionalidade nova,
  adicionada sem quebrar nada do que já existia — a pessoa ganha algo, não
  perde nada. Ex.: o botão do P2Rank na STEP 3, os nomes de compostos no
  relatório, a troca de idioma PT/EN, a redocagem do ligante co-cristalizado.

- **MAJOR** (`1.0.0` → `2.0.0`, zera minor e patch): muda ou remove algo
  que já existia, de um jeito que quem já usa precisa se adaptar. Ex.:
  - remover/renumerar uma STEP ou um botão do fluxo;
  - mudar o formato de arquivos de estado dos projetos (`PROJECTS/<projeto>/...`,
    os `.json` de cada etapa) de um jeito que projetos salvos por versões
    antigas parem de abrir;
  - renomear pastas do layout (`PROJECTS`, `BASE`, `BIN`,
    `MODULES`...) sem migração automática;
  - mudar a versão de Python do venv (hoje 3.10.12, `TARGET_VENV_PYTHON` em
    `MODULES/module_requirements.py`);
  - mudar `/opt/codoc` para outro caminho no `.deb`.

  Renomeações que vêm **com migração automática e transparente** não
  obrigam MAJOR — contam como MINOR, já que o usuário não precisa fazer nada.

## Ao gerar um novo `.deb`

1. Decida o próximo `MAJOR.MINOR.PATCH` pelas regras acima.
2. Atualize `VERSAO` em `MODULES/versao.py` para o novo número.
3. Adicione uma entrada no topo de `packaging/deb/changelog` (formato
   Debian padrão: `codoc (X.Y.Z-1) unstable; urgency=low`, lista do que
   mudou, linha `-- Nome <email>  data`) com o **mesmo** número do passo 2.
4. `packaging/deb/build.sh` (sem argumento já usa o número de
   `MODULES/versao.py`). O pacote sai como `packaging/dist/codoc_X.Y.Z-1_amd64.deb`.

Se a mudança for só de empacotamento (ex.: ajustar o `postinst`, sem tocar
em `CODOC.py`/`MODULES/`), mantenha o `X.Y.Z` e suba só o `-N` (`1.0.0-1` →
`1.0.0-2`) — também em `MODULES/versao.py`, para o app e o pacote mostrarem o
mesmo número.
