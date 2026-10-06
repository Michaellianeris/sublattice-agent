import argparse
import numpy as np
from conf import conFile
import shlex

def comma_separated_floats(s):
	try:
		# Split the string on commas and convert each part to a float.
		return [float(item) for item in s.split(',')]
	except Exception as e:
		raise argparse.ArgumentTypeError("Invalid array format. Use comma-separated floats, e.g., '1.0,2.0,3.0'.")


def parse_arguments():
	parser = argparse.ArgumentParser(description="Parse input parameters for the simulation.")

	# Create an instance of conFile to access default values
	config = conFile()

	parser.add_argument("--input-file", type=str, help="Path to file containing input parameters.")

	# Dynamically add arguments for each parameter in conFile
	parser.add_argument("--g0", type=float, default=config.g0, help="mu0 * gamma (default: %(default)s)")
	parser.add_argument("--gamma", type=float, default=config.gamma, help="gamma (default: %(default)s)")
	parser.add_argument("--mu0", type=float, default=config.mu0, help="mu zero (default: %(default)s)")
	parser.add_argument("--muB", type=float, default=config.muB, help="Bohr magneton (default: %(default)s)")
	parser.add_argument("--kB", type=float, default=config.kB, help="Boltzmann constant (default: %(default)s)")
	parser.add_argument("--e", type=float, default=config.e, help="Elementary charge (default: %(default)s)")
	parser.add_argument("--h", type=float, default=config.h, help="Euler step (default: %(default)s)")
	parser.add_argument("--t", type=float, default=config.t, help="Total time (default: %(default)s)")
	parser.add_argument("--Lx", type=float, default=config.Lx, help="Dimension along x (default: %(default)s)")
	parser.add_argument("--Ly", type=float, default=config.Ly, help="Dimension along y (default: %(default)s)")
	parser.add_argument("--Lz", type=float, default=config.Lz, help="Dimension along z (default: %(default)s)")
	parser.add_argument("--Temp", type=float, default=config.Temp, help="Temperature in K (default: %(default)s)")
	parser.add_argument("--Temp_Ampl", type=float, default=config.Temp_Ampl, help="Amplitude of temperature distribution (default: %(default)s)")
	parser.add_argument("--a", type=float, default=config.a, help="Damping constant (default: %(default)s)")
	parser.add_argument("--Ms", type=float, default=config.Ms, help="Saturation magnetization (default: %(default)s)")
	parser.add_argument("--A0", type=float, default=config.A0, help="Homogeneous interlattice exchange (default: %(default)s)")
	parser.add_argument("--Ku", type=float, default=config.Ku, help="Uniaxial anisotropy (default: %(default)s)")
	parser.add_argument("--l", type=float, default=config.l, help="Lattice constant (default: %(default)s)")
	parser.add_argument("--H", type=float, default=config.H, help="Field (default: %(default)s)")
	parser.add_argument("--Fr", type=float, default=config.Fr, help="Frequency (default: %(default)s)")
	parser.add_argument("--T", type=float, default=config.T, help="Period (default: %(default)s)")
	parser.add_argument("--phase", type=float, default=config.phase, help="Phase (default: %(default)s)")
	parser.add_argument("--flagShape", action="store_true", default=config.flagShape, help="Shape flag (default: %(default)s)")
	parser.add_argument("--flag0", action="store_true", default=config.flag0, help="Temperature flag (default: %(default)s)")
	parser.add_argument("--flag1", action="store_true", default=config.flag1, help="Current flag (default: %(default)s)")
	parser.add_argument("--flag2", action="store_true", default=config.flag2, help="Ku(t) flag (default: %(default)s)")
	parser.add_argument("--flag3", action="store_true", default=config.flag3, help="H(t) flag (default: %(default)s)")
	parser.add_argument("--flag4", action="store_true", default=config.flag4, help="Activate Chirp signal (default: %(default)s)")
	parser.add_argument("--flag5", action="store_true", default=config.flag5, help="Activate SOT (default: %(default)s)")
	parser.add_argument("--flagSinc", action="store_true", default=config.flagSinc, help="Sinc flag (default: %(default)s)")
	parser.add_argument("--flagTempVarying", action="store_true", default=config.flagTempVarying, help="Temperature dependent parameters flag (default: %(default)s)")
	parser.add_argument("--Hex_DC", type=comma_separated_floats, default=config.Hex_DC.tolist(), help="Ex Field Components (DC) (default: %(default)s)")
	parser.add_argument("--Hex_AC", type=comma_separated_floats, default=config.Hex_AC.tolist(), help="Ex Field Components (AC) (default: %(default)s)")
	parser.add_argument("--m1", type=comma_separated_floats, default=config.m1.tolist(), help="Initial condition m1 (default: %(default)s)")
	parser.add_argument("--m2", type=comma_separated_floats, default=config.m2.tolist(), help="Initial condition m2 (default: %(default)s)")
	parser.add_argument("--p", type=comma_separated_floats, default=config.p.tolist(), help="Polarizer (default: %(default)s)")
	parser.add_argument("--Demag", type=comma_separated_floats, default=config.Demag.tolist(), help="Demag tensor (default: %(default)s)")
	parser.add_argument("--u_ani", type=comma_separated_floats, default=config.u_ani.tolist(), help="Anisotropy easy axis(default: %(default)s)")
	parser.add_argument("--u_ani_AC", type=comma_separated_floats, default=config.u_ani.tolist(), help="AC Anisotropy easy axis(default: %(default)s)")
	parser.add_argument("--A0_Amp", type=float, default=config.A0_Amp, help="J Amp (default: %(default)s)")
	parser.add_argument("--Ku_Amp", type=float, default=config.Ku_Amp, help="Ku(t) Amp (default: %(default)s)")
	parser.add_argument("--Ku_Fr", type=float, default=config.Ku_Fr, help="Ku(t) frequency (default: %(default)s)")
	parser.add_argument("--Ku_phase", type=float, default=config.Ku_phase, help="Ku(t) phase  (default: %(default)s)")
	parser.add_argument("--H_Amp", type=float, default=config.H_Amp, help="Field Amp (default: %(default)s)")
	parser.add_argument("--t_chirp", type=float, default=config.t_chirp, help="Duration of Chirp pulse (default: %(default)s)")
	parser.add_argument("--Chirp_Amp", type=float, default=config.Chirp_Amp, help="Amplitude of Chirp signal (default: %(default)s)")
	parser.add_argument("--Chirp_min_Fr", type=float, default=config.Chirp_min_Fr, help="Minimum Chirp frequency (default: %(default)s)")
	parser.add_argument("--Chirp_max_Fr", type=float, default=config.Chirp_max_Fr, help="Maximum Chirp frequency (default: %(default)s)")
	parser.add_argument("--Chirp_phase", type=float, default=config.Chirp_phase, help="Chirp phase (default: %(default)s)")
	parser.add_argument("--SHE_angle", type=float, default=config.SHE_angle, help="SHE angle (default: %(default)s)")
	parser.add_argument("--SOT_DC_Amp", type=float, default=config.SOT_DC_Amp, help="SOT DC current amplitude (default: %(default)s)")
	parser.add_argument("--SOT_AC_Amp", type=float, default=config.SOT_AC_Amp, help="SOT AC current amplitude (default: %(default)s)")
	parser.add_argument("--SOT_AC_Fr", type=float, default=config.SOT_AC_Fr, help="SOT AC current frequency (default: %(default)s)")
	parser.add_argument("--SOT_AC_phase", type=float, default=config.SOT_AC_phase, help="SOT AC current phase (default: %(default)s)")
	parser.add_argument("--SOT_pol", type=comma_separated_floats, default=config.SOT_pol.tolist(), help="SOT polarization (default: %(default)s)")
	parser.add_argument("--SOT_FL_q", type=float, default=config.SOT_FL_q, help="SOT FL strength (default: %(default)s)")

	# Add Gaussian distribution argument
	parser.add_argument(
		"--gaussian",
		type=str,
		nargs=2,
		action="append",
		metavar=("PARAM", "RELATIVE_SIGMA"),
		help="Apply Gaussian distribution to a parameter. Specify as '--gaussian PARAM RELATIVE_SIGMA', where RELATIVE_SIGMA is a fraction of the mean value."
	)

	args, remaining = parser.parse_known_args()

	if args.input_file:
		with open(args.input_file, "r") as f:
			# Use shlex.split to properly handle quotes and whitespace.
			file_args = shlex.split(f.read())
		# Re-parse with both file arguments and any remaining command-line arguments so command-line options override what’s in the file
		args = parser.parse_args(file_args + remaining)
	else:
		args = parser.parse_args()

	return args

if __name__ == "__main__":
	args = parse_arguments()
	print(args)