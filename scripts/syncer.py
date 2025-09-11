#!/usr/bin/env python3

import argparse
import yaml
import subprocess
import time
import os
import fcntl
import sys
import logging
import logging.handlers

class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[94m",    # bleu clair
        "INFO": "\033[92m",     # vert
        "WARNING": "\033[93m",  # jaune
        "ERROR": "\033[91m",    # rouge
        "CRITICAL": "\033[95m", # magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        msg = super().format(record)
        color = self.COLORS.get(record.levelname, "")
        return f"{color}{msg}{self.RESET}"

def setup_logger(debug=False):
    logger = logging.getLogger("sync")

    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # Syslog handler (sans couleur)
    syslog_handler = logging.handlers.SysLogHandler(address="/dev/log")
    syslog_formatter = logging.Formatter(
        "%(asctime)s %(name)s[%(process)d]: %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    syslog_handler.setFormatter(syslog_formatter)

    # Stream handler avec couleur
    stream_handler = logging.StreamHandler()
    stream_formatter = ColoredFormatter(
        "%(asctime)s %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    stream_handler.setFormatter(stream_formatter)

    if not logger.handlers:
        logger.addHandler(syslog_handler)
        logger.addHandler(stream_handler)

    return logger


class syncer:
    def __init__(self, config, verbose, dry_run, bucket, force, logger):
        self.global_exit_code = 0
        self.dry_run = dry_run
        self.verbose = verbose or self.dry_run
        self.bucket = bucket
        self.force = force
        self.logger = logger
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

        self.jobs = self.config.get("jobs", [])
        if not self.jobs:
            self.logger.critical("No job listed in configuration - exiting")
            sys.exit(1)
        self.jobs_list()

    class jobject:
        def __init__(self, job, syncer):
            self.syncer = syncer
            self.job = job
            self.title = self.job["title"]
            self.sync_type = self.job["type"]
            self.create_subfolder = self.job.get("create_subfolder", False)
            self.max_age_days = self.job.get("max_age_days", 30)
            self.max_age_seconds = self.max_age_days * 86400
            self.force = self.syncer.force
            self.state = 0

            self.source_cmd, self.source_bucket = self.get_rclone_bucket_command("source")
            self.target_cmd, self.target_bucket = self.get_rclone_bucket_command("target")
            if self.create_subfolder:
                self.target_cmd = f"{self.target_cmd}/{self.source_bucket}/"

            self.log_file = os.path.join(self.syncer.log_dir, f"{self.source_bucket}.log")
            self.last_success_file = os.path.join(self.syncer.log_dir, f"{self.source_bucket}.last_success")

            self.wanted = False
            self.fisrt_time = not os.path.exists(self.last_success_file)
            self.run = self.is_job_runnable()


        def get_rclone_bucket_command(self, context):
            provider = self.job[context]
            bucket = self.job["buckets"][provider]
            provider_name = self.syncer.config["global"]["rclone"]["providers"][provider]
            command = f"{provider_name}:{bucket}"
            return command, bucket

        def is_job_due(self):
            ## Check age
            now_timestamp = int(time.time())

            # First run
            if self.fisrt_time:
                self.syncer.logger.debug(f"{self.title}: TO RUN - first execution")
                return True

            with open(self.last_success_file) as f:
                last_success = int(f.read().strip())
            last_success_age = now_timestamp - last_success

            ## Last run too young - skip this run
            if last_success_age < self.max_age_seconds:
                self.syncer.logger.debug(f"{self.title}: SKIPPED - too recent (last success on "
                      f"{time.strftime('%Y-%m-%d at %H:%M:%S', time.localtime(last_success))})")
                return False

            ## Last run too old - need a run
            self.syncer.logger.debug(f"{self.title}: TO RUN - too old (last success on "
                  f"{time.strftime('%Y-%m-%d at %H:%M:%S', time.localtime(last_success))})")
            return True

        def is_job_runnable(self):
            ## Skip this job if not asked for
            self.wanted = self.syncer.bucket != "none" and (self.syncer.bucket == "all" or self.syncer.bucket == self.source_bucket)
            if not self.wanted:
                self.syncer.logger.debug(f"{self.title}: SKIPPED - Not the wanted bucket ({self.syncer.bucket})")
                return False

            ## Always run if forced
            if self.force:
                self.syncer.logger.debug(f"{self.title}: TO RUN - Forced by argument regardless of dueness")
                return True

            ## Skip not due job
            self.due = self.is_job_due()
            return self.due


        def get_rclone_command(self):
            self.command = [
                "rclone", self.sync_type,
                "--config", self.syncer.rclone_conf_file,
                self.source_cmd, self.target_cmd,
                *self.syncer.rclone_options,
                f"--log-file={self.log_file}"
            ]

        def run_command(self):
            self.lock_file = f"/tmp/s3_sync_{self.source_bucket}"
            with open(self.lock_file, "w") as lf:
                try:
                    fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.state = subprocess.call(self.command)
                except BlockingIOError:
                    self.syncer.logger.warning(f"{self.title}: Another process is already running for {self.source_bucket}, skipping.")
                    self.state = 1

            if self.state == 0:
                self.syncer.logger.info(">>> Success")
                with open(self.last_success_file, "w") as f:
                    f.write(str(int(time.time())))
                try:
                    ntfy_command = list()
                    ntfy_command.append("/opt/msdl_sync/scripts/report_ntfy.py")
                    ntfy_command.append("--client")
                    ntfy_command.append("MSDL_Archives")
                    ntfy_command.append("--vm")
                    ntfy_command.append(self.source_bucket)
                    ntfy_command.append("--status")
                    ntfy_command.append(str(self.state))
                    ntfy_command.append("--gap")
                    ntfy_command.append(str(self.max_age_days))
                    print(ntfy_command)
                    self.state = subprocess.call(ntfy_command)
                    self.syncer.logger.debug(f"{self.title}: Report sent to monitoring.")
                except BlockingIOError:
                    self.syncer.logger.critical(f"{self.title}: Unable to send report to monitoring.")
                    self.state = 1
            else:
                self.syncer.logger.critical(">>> Failed")

    def jobs_list(self):
        self.job_handlers = list()
        for job in self.jobs:
            self.job_handlers.append(self.jobject(job = job, syncer = self))

    def jobs_loop(self):
        # Traitement des jobs
        for job_handler in self.job_handlers:
            if not job_handler.run:
                self.logger.debug(f"{job_handler.title} - Job is set not to be runned")
                continue

            job_handler.get_rclone_command()

            if self.verbose:
                self.logger.debug(" ".join(job_handler.command))
            self.logger.info(f"{job_handler.title}: Running in {job_handler.sync_type} mode")

            if self.dry_run:
                self.logger.warning(">>> Dry run: skipping execution")
            else:
                job_handler.run_command()

            self.global_exit_code += job_handler.state
        sys.exit(self.global_exit_code)

    def jobs_interractive_choice(self):
        if self.bucket != "all":
            self.logger.debug(f"Bucket to sync already known ({self.bucket})")
            return

        print("Available jobs:")
        for job in self.job_handlers:
            print(f"  * {job.title} - Bucket: {job.source_bucket}")
        # Choix utilisateur
        self.bucket = input("\nEnter bucket name or 'all': ").strip()
        if self.bucket == "":
            self.bucket = "none"

        self.logger.debug(f"Chosen bucket to sync: {self.bucket}")
        for job in self.job_handlers:
            if job.source_bucket == self.bucket:
                job.force = True
            job.run = job.is_job_runnable()



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
        "-s", "--silent",
        action="store_true",
        help="Went true: force a non-interractive mode for scripting"
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
        "-d", "--debug",
        action="store_true",
        help="Display debug"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only display, does not run the sync jobs"
    )
    args = parser.parse_args()

    logger = setup_logger(debug=args.debug)

    handler = syncer(config = args.config,
                     verbose = args.verbose,
                     dry_run = args.dry_run,
                     bucket = args.bucket,
                     force = args.force,
                     logger = logger)
    if not args.silent:
        handler.jobs_interractive_choice()
    handler.jobs_loop()

if __name__ == "__main__":
    main()
