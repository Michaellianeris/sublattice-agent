import time  # Import the time module to measure execution time
from output import output
from run import run 

class MAIN():

	def __init__(self) : 
		
		self.output = output()
		self.run = run()

	def log_simulation_time(self, total_time):
		"""Log the total simulation time to the metadata log file."""
		log_file = "simulation_metadata.log"
		with open(log_file, "a") as f:  # Open in append mode to add to the existing log
			f.write(f"Total Execution Time: {total_time:.1f} seconds\n")
		print(f"Total execution time logged to {log_file}")
	
	def main(self):

		# Start timing the simulation
		start_time = time.time()
		
		# Run the simulation
		xx = self.run.RUN()

		# Save the output data
		self.output.save_data(xx)
		self.output.Two_Dynamics()

		# End timing the simulation
		end_time = time.time()
		total_time = end_time - start_time

		# Log the total simulation time
		self.log_simulation_time(total_time)
	
	
if __name__ == "__main__":
	a=MAIN()
	a.main()