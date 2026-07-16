import os
from datetime import datetime

LOCK_FILE = "logs/last_successful_run.txt"


def already_ran_today():
    if not os.path.exists(LOCK_FILE):
        return False

    with open(LOCK_FILE, "r") as file:
        last_date = file.read().strip()

    today = datetime.now().strftime("%Y-%m-%d")

    return last_date == today


def mark_ran_today():
    os.makedirs("logs", exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")

    with open(LOCK_FILE, "w") as file:
        file.write(today)
