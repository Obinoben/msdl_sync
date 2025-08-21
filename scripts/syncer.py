#!/usr/bin/env python3

import yaml
import subprocess
import time
import os
import fcntl
import sys

SYNC_CONF_FILE = "/etc/quadrumane/sync.yml"
global_exit_code = 0

with open(SYNC_CONF_FILE, "r") as f:
    conf = yaml.safe_load(f)

log_dir = conf["global"]["rclone"]["paths"]["log_dir"]
rclone_conf_file = conf["global"]["rclone"]["paths"]["conf_file"]

# Construction des options rclone
rclone_options = []
for key, value in conf["global"]["rclone"].get("options", {}).items():
    if value == "switch_arg":
        rclone_options.append(f"--{key}")
    else:
        rclone_options.append(f"--{key}={value}")

# Traitement des jobs
for job in conf.get("jobs", []):
    title = job["title"]
    sync_type = job["type"]
    create_subfolder = job.get("create_subfolder", False)

    source_provider = job["source"]
    source_bucket = job["buckets"][source_provider]
    source_provider_name = conf["global"]["rclone"]["providers"][source_provider]
    source_cmd = f"{source_provider_name}:{source_bucket}"

    target_provider = job["target"]
    target_bucket = job["buckets"][target_provider]
    target_provider_name = conf["global"]["rclone"]["providers"][target_provider]
    target_cmd = f"{target_provider_name}:{target_bucket}"
    if str(create_subfolder) == "True":
        target_cmd = f"{target_cmd}/{source_bucket}/"

    now_timestamp = int(time.time())
    max_age_days = job.get("max_age_days", 30)
    max_age_seconds = max_age_days * 86400

    last_success_file = os.path.join(log_dir, f"{source_bucket}.last_success")

    skip_job = False
    if os.path.exists(last_success_file):
        with open(last_success_file) as f:
            last_success = int(f.read().strip())
        last_success_age = now_timestamp - last_success
        if last_success_age < max_age_seconds:
            print(f"{title}: SKIPPED - too recent (last success on "
                  f"{time.strftime('%Y-%m-%d at %H:%M:%S', time.localtime(last_success))})")
            skip_job = True
        else:
            print(f"{title}: TO RUN - too old (last success on "
                  f"{time.strftime('%Y-%m-%d at %H:%M:%S', time.localtime(last_success))})")
    else:
        print(f"{title}: TO RUN - first execution")

    if skip_job:
        continue

    log_file = os.path.join(log_dir, f"{source_bucket}.log")
    rclone_cmd = [
        "rclone", sync_type,
        "--config", rclone_conf_file,
        source_cmd, target_cmd,
        *rclone_options,
        f"--log-file={log_file}"
    ]

    print(f"{title}: Running in {sync_type} mode")

    lock_file = f"/tmp/s3_sync_{source_bucket}"
    with open(lock_file, "w") as lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
            state = subprocess.call(rclone_cmd)
        except BlockingIOError:
            print(f"{title}: Another process is already running for {source_bucket}, skipping.")
            state = 1

    global_exit_code += state

    if state == 0:
        print(">>> Success")
        with open(last_success_file, "w") as f:
            f.write(str(time.time()))
    else:
        print(">>> Failed")

sys.exit(global_exit_code)
