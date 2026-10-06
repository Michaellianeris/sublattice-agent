import os
import shutil

# Base path where broadband_response exists
base_path = '/Users/michaillianeris/Desktop/python/macrospin_code_3/broadband_response'

# Source folder and file
source_folder = os.path.join(base_path, '25GHz')
source_file = os.path.join(source_folder, 'parameters.txt')

# Read the original parameters.txt content
with open(source_file, 'r') as f:
    original_content = f.read()

# Loop over new frequencies
for freq in range(1200, 2000):
    folder_name = f"{freq}GHz"
    new_folder_path = os.path.join(base_path, folder_name)
    
    # Create the new folder
    os.makedirs(new_folder_path, exist_ok=True)
    
    # Copy ALL files from 25GHz to the new folder
    for file_name in os.listdir(source_folder):
        src_file_path = os.path.join(source_folder, file_name)
        dest_file_path = os.path.join(new_folder_path, file_name)
        
        # If it's parameters.txt, modify frequency
        if file_name == 'parameters.txt':
            new_content = original_content.replace('--Fr=25e9', f'--Fr={freq}e9')
            with open(dest_file_path, 'w') as f:
                f.write(new_content)
        else:
            # Simply copy the file as-is
            shutil.copy2(src_file_path, dest_file_path)

print("All folders created and parameter files updated.")
