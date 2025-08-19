#!/bin/bash

sync_conf_file="/etc/quadrumane/sync.yml"
global_exit_code=0

log_dir=$(cat $sync_conf_file | shyaml get-value global.rclone.paths.log_dir)

rclone_conf_file=$(cat $sync_conf_file | shyaml get-value global.rclone.paths.conf_file)
rclone_options=""
for key in $(cat $sync_conf_file | shyaml keys global.rclone.options); do
  value=$(cat $sync_conf_file | shyaml get-value global.rclone.options.$key)
  case $value in
    switch_arg)
        rclone_options="$rclone_options --$key"
        ;;
    *)
        rclone_options="$rclone_options --$key=$value"
        ;;
  esac
done

rclone_base_cmd="rclone sync $rclone_conf_file $rclone_options"

count=$(cat $sync_conf_file | shyaml get-length jobs)
for i in $(seq 0 $((count-1))); do
    title=$(cat $sync_conf_file | shyaml get-value jobs.$i.title)
    type=$(cat $sync_conf_file | shyaml get-value jobs.$i.type)
    create_subfolder=$(cat $sync_conf_file | shyaml get-value jobs.$i.create_subfolder)

    source_provider=$(cat $sync_conf_file | shyaml get-value jobs.$i.source)
    source_bucket=$(cat $sync_conf_file | shyaml get-value jobs.$i.buckets.${source_provider})
    source_provider_name=$(cat $sync_conf_file | shyaml get-value global.rclone.providers.${source_provider})
    source_cmd="${source_provider_name}:${source_bucket}"

    target_provider=$(cat $sync_conf_file | shyaml get-value jobs.$i.target)
    target_bucket=$(cat $sync_conf_file | shyaml get-value jobs.$i.buckets.${target_provider})
    target_provider_name=$(cat $sync_conf_file | shyaml get-value global.rclone.providers.${target_provider})
    target_cmd="${target_provider_name}:${target_bucket}"
    if [[ "$create_subfolder" == "True" ]]; then
      target_cmd="${target_cmd}/${source_bucket}/"
    fi


    frequency=$(cat $sync_conf_file | shyaml get-value jobs.$i.frequency)
    now_timestamp=$(date +%s)
    case $frequency in
      daily)
          max_age_days=1
          ;;
      weekly)
          max_age_days=7
          ;;
      *)
          max_age_days=30
          ;;
    esac
    max_age_seconds=$(( $max_age_days * 86400 ))
    if [ -f ${log_dir}/${source_bucket}.last_success ]; then
      last_success=$(cat ${log_dir}/${source_bucket}.last_success)
      last_success_age=$(( $now_timestamp - $last_success ))
      if [[ $last_success_age < $max_age_seconds ]]; then
        echo "${title}: SKIPPED - too recent (last success on $(date -d @$last_success '+%Y-%m-%d at %H:%M:%S'))"
        continue
      fi
      echo "${title}: TO RUN - too old (last success on $(date -d @$last_success '+%Y-%m-%d at %H:%M:%S'))"
    else
      echo "${title}: TO RUN - first execution"
    fi
    

    log_file="--log-file=${log_dir}/"${source_bucket}".log"

    rclone_cmd="rclone $type $rclone_conf_file $source_cmd $target_cmd $rclone_options $log_file"

    echo "${title}: Running in $type mode"
    echo "echo flock -n /tmp/s3_sync_${source_bucket} ${rclone_cmd}"
    state=$?

    global_exit_code=$(( $global_exit_code + $state ))

    if [[ $state -eq 0 ]]; then
      echo ">>> Sucess"
      date +%s > ${log_dir}/${source_bucket}.last_success
    else
      echo ">>> Failed"
    fi
done

exit $global_exit_code
