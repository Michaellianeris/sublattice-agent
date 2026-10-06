import os
import numpy as np
import matplotlib.pyplot as plt

# Base path
base_path = '/Users/michaillianeris/Desktop/python/macrospin_code_3/broadband_response'

# === CHOOSE WHICH FOLDERS ===

frequencies_to_run = list(range(1, 1200))
folders_to_run = [f"{freq}GHz" for freq in frequencies_to_run]

# Lists to collect results
frequencies = []
average_neel_z_values = []

for folder_name in folders_to_run:
    folder_path = os.path.join(base_path, folder_name)
    neel_file = os.path.join(folder_path, 'neel_z.dat')
    
    if not os.path.isfile(neel_file):
        print(f"File neel_z.dat missing in {folder_name}. Skipping.")
        continue

    # Load the data
    try:
        data = np.loadtxt(neel_file, comments="#")
    except Exception as e:
        print(f"Error reading neel_z.dat in {folder_name}: {e}")
        continue

    # Extract n_z column
    neel_z = data[:, 1]

    # Compute average
    avg_neel = np.mean(neel_z)

    # Store frequency and average
    freq_value = int(folder_name.rstrip("GHz"))
    frequencies.append(freq_value)
    average_neel_z_values.append(avg_neel)

    print(f"Folder {folder_name}: Average Neel_z = {avg_neel:.6e}")

# Convert to numpy arrays for sorting
frequencies = np.array(frequencies)
average_neel_z_values = np.array(average_neel_z_values)

# Sort by frequency
sort_idx = np.argsort(frequencies)
frequencies = frequencies[sort_idx]
average_neel_z_values = average_neel_z_values[sort_idx]

# Plot
plt.figure(figsize=(4,3))
plt.plot(frequencies, average_neel_z_values, 'bo-', markersize=4)
plt.xlabel('Frequency (GHz)')
plt.ylabel(r'Average $n_z$')
plt.title('Average Neel Vector vs Frequency')
plt.grid(True)
plt.tight_layout()
plt.savefig(os.path.join(base_path, 'average_neel_vs_frequency.png'), dpi=300)
plt.show()

print("Plot saved as average_neel_vs_frequency.png")
