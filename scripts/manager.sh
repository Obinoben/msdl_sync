#!/bin/bash
## Init
export MONDAY_API_KEY=$(cat /etc/quadrumane/monday.key)
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
MONDAY_ITEM=$(echo "$m" | jq -r '.monday_item_id')
MONDAY_BOARD=$(curl -s -X POST "https://api.monday.com/v2" \
                   -H "Authorization: $MONDAY_API_KEY" \
                   -H "Content-Type: application/json" \
                   -d "{\"query\": \"query { items(ids: $MONDAY_ITEM) { board { id } } }\"}" \
                   | jq -r '.data.items[0].board.id')
LOG=""

update_monday_item () {
  local board_id="$1"
  local item_id="$2"
  local column_id="$3"
  local value="$4"

  QUERY_JSON="{\"query\": \"mutation { change_simple_column_value(item_id: $item_id, \
                                                                  board_id: $board_id, \
                                                                  column_id: \\\"$column_id\\\", \
                                                                  value: \\\"$value\\\") { id } }\"}"

  curl -s -X POST "https://api.monday.com/v2" \
    -H "Authorization: $MONDAY_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$QUERY_JSON"
}

update_log () {
  local message="$1"
  local push=$2

  echo $message
  LOG="${LOG}${message}\n"

  if [[ $push -eq 1 ]]; then
    update_monday_item $MONDAY_BOARD $MONDAY_ITEM "text_mkv9fhe0" "$message"
  fi
}

update_log "Message reçu" 1
update_monday_item $MONDAY_BOARD $MONDAY_ITEM "status" "Traitement"
global=0
for archive in $(echo "$m" | jq -r '.archives' | sed 's/,//g'); do
  update_log "Lance la synchronisation de ${archive}" 1
  ${SCRIPT_DIR}/syncer.py -s -b ${archive} --force
  status=$?
  global=$(( $global + $status ))
  if [[ $status -eq 0 ]]; then
    update_log ">> OK" 1
  else
    update_log ">> Échec" 1
  fi
done

if [[ $global -eq 0 ]]; then
  update_log "Tout a fonctionné" 1
  update_monday_item $MONDAY_BOARD $MONDAY_ITEM "status" "Succès"
else
  update_log "Erreur de sync" 1
  update_monday_item $MONDAY_BOARD $MONDAY_ITEM "status" "Échec"
fi

exit $global
