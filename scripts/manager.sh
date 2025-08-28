#!/bin/bash
## Init
export MONDAY_API_KEY=$(cat /etc/quadrumane/monday.key)
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
MONDAY_ITEM=$(echo "$m" | jq -r '.monday_item_id')

update_monday_item () {
  local item_id="$1"
  local column_id="$2"
  local value="$3"

  value=$(echo "$value" | sed 's/"/\\\\"/g')

  curl -s -X POST "https://api.monday.com/v2" \
    -H "Authorization: $MONDAY_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"query\": \"mutation {
        change_simple_column_value(
          item_id: $item_id,
          column_id: \\\"$column_id\\\",
          value: \\\"$value\\\"
        ) {
          id
        }
      }\"
    }"
}



echo "Message reçu"
update_monday_item $MONDAY_ITEM "status" '{"label":"Traitement"}'
global=0
for archive in $(echo "$m" | jq -r '.archives' | sed 's/,//g'); do
  echo "Lance la synchronisation de ${archive}"
  ${SCRIPT_DIR}/syncer.py -s -b ${archive}
  global=$(( $global + $? ))
done

if [[ $global -eq 0 ]]; then
  echo "Tout a fonctionné"
  update_monday_item $MONDAY_ITEM "status" '{"label":"Succès"}'
else
  echo "Erreur de sync"
  update_monday_item $MONDAY_ITEM "status" '{"label":"Échec"}'
fi

exit $global
