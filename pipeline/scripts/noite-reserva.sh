#!/usr/bin/env bash
# Reserva da noite eleitoral: corre a recolha e a projeção num computador local, quando o
# GitHub Actions falha (ver docs/noite-eleitoral-operacao.md, "Reserva local").
#
# Faz o mesmo que os jobs "noite" de resultados.yml e noite.yml: recolhe as fontes a cada
# 30 s, projeta a cada 30 s e envia os ficheiros para as mesmas Releases, com o `gh` da
# pessoa que o corre. Se um dos dois processos parar, volta a lançá-lo até à hora `--ate`.
#
# Uso (na raiz do repositório):
#
#   pipeline/scripts/noite-reserva.sh --ate 2026-11-04T16:00
#   pipeline/scripts/noite-reserva.sh --ate 2026-11-04T16:00 --estados NC,FL,GA,AK,TX
#   pipeline/scripts/noite-reserva.sh --verificar      # só confere os requisitos
#
# Requisitos: uv, gh com sessão iniciada e permissão de escrita no repositório.
# Para parar: Ctrl+C (pára os dois processos).

set -euo pipefail

REPO="${GH_REPO:-tpereira2005/intercalares-eua-2026}"
DATA="2026-11-03"
ATE=""
ESTADOS="NC,FL,GA,AK,TX"
INTERVALO="30"
FORCAR=0
SO_VERIFICAR=0
PAUSA_RELANCAR=15

ajuda() { sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --ate) ATE="$2"; shift 2 ;;
    --data) DATA="$2"; shift 2 ;;
    --estados) ESTADOS="$2"; shift 2 ;;
    --intervalo) INTERVALO="$2"; shift 2 ;;
    --forcar) FORCAR=1; shift ;;
    --verificar) SO_VERIFICAR=1; shift ;;
    -h | --help) ajuda; exit 0 ;;
    *) echo "Opção desconhecida: $1" >&2; ajuda >&2; exit 2 ;;
  esac
done

registo() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*"; }
falhar() { registo "ERRO: $*" >&2; exit 1; }

# 1. Requisitos
[ -f pyproject.toml ] && [ -d pipeline ] || falhar "corre o script na raiz do repositório"
command -v uv > /dev/null || falhar "falta o uv (https://docs.astral.sh/uv/)"
command -v gh > /dev/null || falhar "falta o gh (https://cli.github.com/)"
gh auth status > /dev/null 2>&1 || falhar "o gh não tem sessão iniciada: gh auth login"
gh release view dados-previsao --repo "$REPO" > /dev/null 2>&1 ||
  falhar "sem acesso à Release dados-previsao de $REPO"
registo "Requisitos: uv, gh e acesso a $REPO verificados"

# 2. Nunca dois publicadores ao mesmo tempo: os jobs do Actions e esta reserva escreveriam
# por cima uns dos outros nas mesmas Releases.
a_correr=$(
  for w in resultados.yml noite.yml; do
    gh run list --repo "$REPO" --workflow "$w" --json status,databaseId \
      -q '.[] | select(.status == "in_progress" or .status == "queued") | .databaseId'
  done
)
if [ -n "$a_correr" ]; then
  if [ "$FORCAR" -eq 1 ]; then
    registo "Aviso: há execuções no Actions ($(echo "$a_correr" | tr '\n' ' ')); --forcar dado"
  else
    falhar "há execuções do Actions a correr: $(echo "$a_correr" | tr '\n' ' ').
Cancela-as primeiro (gh run cancel <id> --repo $REPO) ou usa --forcar."
  fi
fi

[ "$SO_VERIFICAR" -eq 1 ] && { registo "Verificação concluída"; exit 0; }
[ -n "$ATE" ] || falhar "falta --ate AAAA-MM-DDTHH:MM (hora UTC até à qual correr)"

uv sync --all-packages --locked > /dev/null

# 3. Entradas da projeção: a previsão congelada e o histórico da noite, se já existir.
mkdir -p entrada data/publicado/noite
gh release download dados-previsao --repo "$REPO" --pattern previsao-2026.json \
  --dir entrada --clobber
if gh release view dados-noite --repo "$REPO" --json assets -q '.assets[].name' |
  grep -qx historico-noite-2026.json; then
  gh release download dados-noite --repo "$REPO" --pattern historico-noite-2026.json \
    --dir data/publicado/noite --clobber
fi
gh release view resultados-2026 --repo "$REPO" > /dev/null 2>&1 ||
  gh release create resultados-2026 --repo "$REPO" --latest=false \
    --title "Resultados da noite eleitoral de 2026" \
    --notes "Resultados oficiais tal como publicados por cada estado; substituídos a cada recolha."

export GH_REPO="$REPO"

restante() {
  # Segundos até $ATE (UTC); 0 se já passou. GNU date ou BSD date (macOS).
  local fim
  fim=$(date -u -d "$ATE" +%s 2> /dev/null || date -u -j -f "%Y-%m-%dT%H:%M" "$ATE" +%s)
  local agora
  agora=$(date -u +%s)
  echo $((fim > agora ? fim - agora : 0))
}

recolha() {
  uv run python -m pipeline.jobs.resultados --data "$DATA" --estados "$ESTADOS" \
    --intervalo "$INTERVALO" --duracao "$1" --publicar resultados-2026
}

projecao() {
  uv run python -m pipeline.jobs.projecao_noite \
    --previsao entrada/previsao-2026.json \
    --parciais "https://github.com/$REPO/releases/download/resultados-2026/parciais.json" \
    --historico data/publicado/noite/historico-noite-2026.json \
    --saida data/publicado/noite --intervalo "$INTERVALO" \
    --duracao "$1" --publicar dados-noite
}

# 4. Cada processo corre até $ATE; se parar antes (erro, rede), volta a ser lançado.
vigiar() {
  local nome="$1"
  while :; do
    local segundos
    segundos=$(restante)
    [ "$segundos" -gt 0 ] || { registo "$nome: chegou a $ATE, a terminar"; return 0; }
    registo "$nome: a correr durante ${segundos}s"
    if "$nome" "$segundos"; then
      registo "$nome: terminou"
    else
      registo "$nome: parou com erro $?; relança em ${PAUSA_RELANCAR}s"
    fi
    sleep "$PAUSA_RELANCAR"
  done
}

filhos=()
parar() {
  registo "A parar a reserva"
  for p in "${filhos[@]}"; do kill "$p" 2> /dev/null || true; done
  wait
  exit 0
}
trap parar INT TERM

vigiar recolha &
filhos+=($!)
vigiar projecao &
filhos+=($!)
registo "Reserva a correr até $ATE (recolha: $ESTADOS). Ctrl+C para parar."
wait
