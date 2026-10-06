import os
import subprocess

# Base path
base_path = '/Users/michaillianeris/Desktop/python/macrospin_code_3/broadband_response'

# === CHOOSE HERE ===

frequencies_to_run = list(range(1200, 2000))

# Build folder names
folders_to_run = [f"{freq}GHz" for freq in frequencies_to_run]

for folder_name in folders_to_run:
    folder_path = os.path.join(base_path, folder_name)
    
    if not os.path.isdir(folder_path):
        print(f"Folder {folder_name} does not exist. Skipping.")
        continue

    print(f"Running simulation in folder: {folder_name}")
    
    command = ["python3", "main.py", "--input-file", "parameters.txt"]
    
    result = subprocess.run(
        command,
        cwd=folder_path,
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)

print("Selected simulations completed.")
