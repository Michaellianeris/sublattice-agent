from solver import solver 
from conf import conFile
from importdata import parse_arguments  # Import the argument parser
import numpy as np 
import os
import platform
from datetime import datetime

class run:
	def __init__(self): 
		self.param = conFile()
		self.update_parameters_from_args()  # Update parameters with parsed arguments
		self.calculate_area_and_volume()  # Calculate area and volume
		self.export_parameters_to_log()    # Export parameters to a log file
		self.create_simulation_logfile()   # Create a simulation log file
		self.solver = solver(self.param)
		self.w = 1

	def calculate_area_and_volume(self):
		# Calculate area and volume based on the shape flag
		self.param.Area = self.param.Lx * self.param.Ly
		if self.param.flagShape:
			self.param.Area = 0.25 * np.pi * self.param.Area
			print(f"Area calculation: {self.param.Area:.3e} nm^2")
		# Calculate volume
		self.param.Vol = self.param.Area * self.param.Lz	

	def update_parameters_from_args(self):
		# Parse command-line arguments
		args = parse_arguments()

		# Update the parameters in the conFile instance with the parsed arguments
		gaussian_params = []  # To store parameters with Gaussian distributions
		for key, value in vars(args).items():
			if key == "gaussian" and value:
				# Collect Gaussian parameters and their sigma values
				for param, relative_sigma in value:
					gaussian_params.append((param, float(relative_sigma)))
			elif hasattr(self.param, key):
				# Convert list back to NumPy array for specific parameters
				if key in ["Hex_DC", "Hex_AC", "m1", "m2", "p", "Demag", "u_ani", "u_ani_AC", "SOT_pol"]:
					setattr(self.param, key, np.array(value, dtype=np.float64))
				else:
					setattr(self.param, key, value)

		# Apply Gaussian distributions to specified parameters
		rng = np.random.default_rng()  # Initialize random number generator
		for param, relative_sigma in gaussian_params:
			if hasattr(self.param, param):
				mean_value = getattr(self.param, param)
				sigma = mean_value * relative_sigma  # Calculate absolute sigma
				new_value = rng.normal(loc=mean_value, scale=sigma)
				setattr(self.param, param, new_value)
			else:
				print(f"Warning: Parameter '{param}' not found in conFile class.")
		return

	def export_parameters_to_log(self):
		"""Export all input parameters to a log file."""
		log_file = "simulation_parameters.log"
		with open(log_file, "w") as f:
			f.write("Simulation Parameters:\n")
			f.write("=======================\n")
			for key, value in vars(self.param).items():
				if isinstance(value, np.ndarray):
					f.write(f"{key}: {value.tolist()}\n")  # Convert NumPy arrays to lists for logging
				else:
					f.write(f"{key}: {value}\n")
		print(f"Parameters exported to {os.path.abspath(log_file)}")

	def create_simulation_logfile(self):
		"""Create a log file to store simulation metadata."""
		log_file = "simulation_metadata.log"
		with open(log_file, "w") as f:
			f.write("Simulation Metadata:\n")
			f.write("====================\n")
			f.write(f"Date of Simulation: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
			f.write(f"Time to set Simulation: {self.param.t} seconds\n")
			f.write(f"Location of Simulation: {os.getcwd()}\n")
			f.write(f"Executable Used: {os.path.basename(__file__)}\n")
			f.write(f"Operating System: {platform.system()} {platform.release()} ({platform.version()})\n")
		print(f"Simulation metadata exported to {os.path.abspath(log_file)}")

	def RUN(self):
		param = self.param
		solver = self.solver

		
		m1 = np.array(param.m1, dtype=np.float64)/np.linalg.norm(param.m1)
		m2 = np.array(param.m2, dtype=np.float64)/np.linalg.norm(param.m2)
		t0 = np.float64(0.0)
		i = np.float64(0.0)
		n = 1
		w = self.w

		# Dimensionless time calculation
		tnew = np.float64(param.t)  
		hh = np.float64(param.h)  
		k = int(tnew / hh)
		pp = int(k / w)

		# Temperature
		if param.flag0 and 0 < param.Temp:
			print('Computing temperature standard deviation ...')
			param.Temp_Ampl = np.float64(np.sqrt((2 * param.kB * param.a * param.Temp)/(param.mu0 * param.g0 * param.Ms * param.Vol * param.h)) / param.Ms)
		else:
			param.Temp_Ampl = 0.0
		print(f'Temperature is: {param.Temp:.3f} with a standard deviation of {param.Temp_Ampl:.3e}')
		
		Results1 = np.zeros((pp, 4), dtype=np.float64)
		Results2 = np.zeros((pp, 4), dtype=np.float64)

		for j in range(k): 
			t00 = np.float64(t0 / (param.g0 * param.Ms))  

			if j == 0:
				Results1[j, :] = [t0, m1[0], m1[1], m1[2]]
				Results2[j, :] = [t0, m2[0], m2[1], m2[2]]

			# Call the solver method 
			m1, m2 = solver.Heun(m1, m2, t0)

			if i == w:
				Results1[n, :] = [t0, m1[0], m1[1], m1[2]]
				Results2[n, :] = [t0, m2[0], m2[1], m2[2]]
				
				# print(f'Spin 1 : t= {t00:.16E}, mx= {m1[0]:.16f}, my={m1[1]:.16f}, mz={m1[2]:.16f}')
				# print(f'Spin 2 : t= {t00:.16E}, mx= {m2[0]:.16f}, my={m2[1]:.16f}, mz={m2[2]:.16f}')
				
				n += 1
				i = 0  # Reset counter

			t0 += hh  
			i += 1

		return [Results1, Results2]
