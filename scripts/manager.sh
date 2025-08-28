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

update_monday_item () {
  local board_id="$1"
  local item_id="$2"
  local column_id="$3"
  local value="$4"

  # JSON dans un fichier temporaire
  QUERY_JSON=$(jq -n --arg item "$item_id" \
                    --arg board "$board_id" \
                    --arg column "$column_id" \
                    --argjson val "$value" \
                    '{query: "mutation { change_simple_column_value(item_id: \($item), board_id: \($board), column_id: \($column), value: \($val)) { id } }"}')

  curl -s -X POST "https://api.monday.com/v2" \
    -H "Authorization: $MONDAY_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$QUERY_JSON"
}

echo "Message reçu"
update_monday_item $MONDAY_BOARD $MONDAY_ITEM "status" "Traitement"
global=0
for archive in $(echo "$m" | jq -r '.archives' | sed 's/,//g'); do
  echo "Lance la synchronisation de ${archive}"
  ${SCRIPT_DIR}/syncer.py -s -b ${archive}
  global=$(( $global + $? ))
done

if [[ $global -eq 0 ]]; then
  echo "Tout a fonctionné"
  update_monday_item $MONDAY_BOARD $MONDAY_ITEM "status" "Succès"
else
  echo "Erreur de sync"
  update_monday_item $MONDAY_BOARD $MONDAY_ITEM "status" "Échec"
fi

exit $global
