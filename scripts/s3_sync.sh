#!/bin/bash

wasabi_bucket=$1 #Wasabi CN Source - first argument when calling the script
aws_bucket=$2 #AWS destination bucket - a folder named as $wasabi_bucket will be created in the root of the AWS bucket

conf_file="--config /etc/quadrumane/rclone.cfg"
options="--checksum --fast-list --create-empty-src-dirs --ignore-errors --s3-upload-cutoff=0 --progress --metadata"
threads="--multi-thread-streams=12 --transfers=12 --checkers=28"
log_file="--log-file=/opt/logs/"$wasabi_bucket".log"
excludes="--exclude=/.tt_rt/**"


echo "Lancement de la synchro $wasabi_bucket vers $aws_bucket"
echo flock -n /tmp/s3_sync rclone sync $conf_file WasabiCN:"$wasabi_bucket" AWS:"$aws_bucket"/"$wasabi_bucket"/ $options $threads $log_file $excludes
flock -n /tmp/s3_sync rclone sync $conf_file WasabiCN:"$wasabi_bucket" AWS:"$aws_bucket"/"$wasabi_bucket"/ $options $threads $log_file $excludes
state=$?

if [[ $state -ne 0 ]]; then
        echo ">>> Echec"
else
        echo ">>> OK"
fi

exit $?
