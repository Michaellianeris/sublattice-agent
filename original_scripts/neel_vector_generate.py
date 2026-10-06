import os
import numpy as np

# Base path
base_path = '/Users/michaillianeris/Desktop/python/macrospin_code_3/broadband_response'

# === CHOOSE WHICH FOLDERS ===
frequencies_to_run = list(range(1, 1200))
folders_to_run = [f"{freq}GHz" for freq in frequencies_to_run]

for folder_name in folders_to_run:
    folder_path = os.path.join(base_path, folder_name)
    
    if not os.path.isdir(folder_path):
        print(f"Folder {folder_name} does not exist. Skipping.")
        continue

    print(f"Processing folder: {folder_name}")

    # Paths to the two .dat files
    output1_path = os.path.join(folder_path, 'output1.dat')
    output2_path = os.path.join(folder_path, 'output2.dat')
    
    # Check files exist
    if not os.path.isfile(output1_path) or not os.path.isfile(output2_path):
        print(f"Missing output1.dat or output2.dat in {folder_name}. Skipping.")
        continue

    # Load the data
    try:
        data1 = np.loadtxt(output1_path, comments="#")
        data2 = np.loadtxt(output2_path, comments="#")
    except Exception as e:
        print(f"Error reading data in {folder_name}: {e}")
        continue

    # Extract columns:
    # Assuming columns: time, mx, my, mz
    time = data1[:, 0]
    m1_z = data1[:, 3]
    m2_z = data2[:, 3]

    # Compute neel_z
    neel_z = np.abs((m1_z - m2_z) / 2.0)

    # Stack time and neel_z into two columns
    result = np.column_stack((time, neel_z))

    # Save into neel_z.dat without header
    neel_z_path = os.path.join(folder_path, 'neel_z.dat')
    np.savetxt(neel_z_path, result, fmt='%.6e')

    print(f"Saved neel_z.dat in {folder_name}")

print("All processing complete.")
