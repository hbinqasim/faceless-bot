import sys
import subprocess
from daily_guard import already_ran_today, mark_ran_today

VIDEOS_TO_CREATE = 10
PYTHON = sys.executable

if already_ran_today():
    print("Bot already ran today. Skipping.")
    exit()

print("Generating reels...")

for i in range(VIDEOS_TO_CREATE):
    print(f"\nCreating reel {i + 1} of {VIDEOS_TO_CREATE}")
    subprocess.run([PYTHON, "main.py"], check=True)

print("\nExporting metadata...")
subprocess.run([PYTHON, "export_metadata.py"], check=True)

print("\nChecking quality...")
subprocess.run([PYTHON, "quality_check.py"], check=True)

print("\nUploading unuploaded videos...")
for i in range(VIDEOS_TO_CREATE):
    subprocess.run([PYTHON, "youtube_uploader.py", str(i)], check=True)

print("\nProduction and upload complete.")
mark_ran_today()