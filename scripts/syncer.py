#!/usr/bin/env python3

import argparse
import yaml
import subprocess
import time
import os
import fcntl
import sys

class syncer:
    def __init__(self, config, verbose, dry_run, bucket, force):
        self.global_exit_code = 0
        self.dry_run = dry_run
        self.verbose = verbose or self.dry_run
        self.bucket = bucket
        self.force = force
        with open(config, "r") as f:
            self.config = yaml.safe_load(f)

        self.log_dir = self.config["global"]["rclone"]["paths"]["log_dir"]
        self.rclone_conf_file = self.config["global"]["rclone"]["paths"]["conf_file"]

        # Construction des options rclone
        self.rclone_options = []
        for key, value in self.config["global"]["rclone"].get("options", {}).items():
            if value == "switch_arg":
                self.rclone_options.append(f"--{key}")
            else:
                self.rclone_options.append(f"--{key}={value}")

    class jobject:
        def __init__(self, job, syncer):
            self.syncer = syncer
            self.job = job
            self.title = self.job["title"]
            self.sync_type = self.job["type"]
            self.create_subfolder = self.job.get("create_subfolder", False)
            self.max_age_days = self.job.get("max_age_days", 30)
            self.max_age_seconds = self.max_age_days * 86400

            self.source_cmd, self.source_bucket = self.get_rclone_bucket_command("source")
            self.target_cmd, self.target_bucket = self.get_rclone_bucket_command("target")

            if self.create_subfolder:
                self.target_cmd = f"{self.target_cmd}/{self.source_bucket}/"

            self.last_success_file = os.path.join(log_dir, f"{self.source_bucket}.last_success")
            self.run = self.is_job_runnable
            self.log_file = os.path.join(self.syncer.log_dir, f"{self.source_bucket}.log")

        def get_rclone_bucket_command(self, context):
            provider = self.job[context]
            bucket = self.job["buckets"][provider]
            provider_name = self.syncer.config["global"]["rclone"]["providers"][provider]
            command = f"{provider_name}:{bucket}"
            return command, bucket

        def is_job_runnable(self):
            ## Skip this job if not asked for
            if self.syncer.bucket != "all" and self.syncer.bucket != self.source_bucket:
                print(f"{self.title}: SKIPPED - Not the wanted bucket ({self.syncer.bucket})")
                return False

            ## Always run if forced
            if self.syncer.force:
                print(f"{title}: TO RUN - Forced by argument")
                return True

            ## Check age
            now_timestamp = int(time.time())

            # First run
            if not os.path.exists(self.last_success_file):
                print(f"{title}: TO RUN - first execution")
                return True

            with open(self.last_success_file) as f:
                last_success = int(f.read().strip())
            last_success_age = now_timestamp - last_success

            ## Last run too young - skip this run
            if last_success_age < self.max_age_seconds:
                print(f"{title}: SKIPPED - too recent (last success on "
                      f"{time.strftime('%Y-%m-%d at %H:%M:%S', time.localtime(last_success))})")
                return False

            ## Last run too old - need a run
            print(f"{title}: TO RUN - too old (last success on "
                  f"{time.strftime('%Y-%m-%d at %H:%M:%S', time.localtime(last_success))})")
            return True

        def get_rclone_command(self):
            self.command = [
                "rclone_dummy", self.syncer.sync_type,
                "--config", self.syncer.rclone_conf_file,
                self.source_cmd, self.target_cmd,
                *self.syncer.rclone_options,
                f"--log-file={self.log_file}"
            ]

        def run_command(self):
            self.lock_file = f"/tmp/s3_sync_{self.source_bucket}"
            with open(lock_file, "w") as lf:
                try:
                    fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.state = subprocess.call(self.command)
                except BlockingIOError:
                    print(f"{self.title}: Another process is already running for {self.source_bucket}, skipping.")
                    self.state = 1

        def exit_command(self):
            if self.state == 0:
                print(">>> Success")
                with open(self.last_success_file, "w") as f:
                    f.write(str(time.time()))
            else:
                print(">>> Failed")

    def jobs_loop(self):
        # Traitement des jobs
        for job in self.config.get("jobs", []):
            job_handler = jobject(job = job, syncer = self)
            if not job_handler.run:
                continue

            job_handler.get_rclone_command()

            if self.verbose:
                print(" ".join(job_handler.command))

            print(f"{job_handler.title}: Running in {job_handler.sync_type} mode")

            if self.dry_run:
                print(">>> Dry run: skipping execution")
                state = 0
            else:
                job_handler.run_command()

            self.global_exit_code += job_handler.state


        sys.exit(global_exit_code)




def main():
    parser = argparse.ArgumentParser(description="Script de synchronisation rclone basé sur une config YAML")
    parser.add_argument(
        "-b", "--bucket",
        default="all",
        help="Name of the source bucket to sync)"
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Ignore the schedule, run anyway"
    )
    parser.add_argument(
        "-c", "--config",
        default="/etc/quadrumane/sync.yml",
        help="Path to the sync configuration YAML file (default: /etc/quadrumane/sync.yml)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose mode"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only display, does not run the sync jobs"
    )
    args = parser.parse_args()

    handler = syncer(config = args.config,
                     verbose = args.verbose,
                     dry_run = args.dry_run,
                     bucket = args.bucket,
                     force = args.force)

    handler.jobs_loop()

if __name__ == "__main__":
    main()
