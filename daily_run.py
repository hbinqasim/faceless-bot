import subprocess

VIDEOS_TO_CREATE = 5

print("Starting daily reel production...")

subprocess.run(["python", "bulk_generate.py"])
subprocess.run(["python", "export_metadata.py"])
subprocess.run(["python", "quality_check.py"])
subprocess.run(["python", "open_latest.py"])

print("Daily production completed.")

