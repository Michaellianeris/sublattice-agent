import matplotlib.pyplot as plt
import numpy as np 
from matplotlib.ticker import ScalarFormatter
import scienceplots
import os
import glob

# plt.style.use('ieee')
# Define IEEE style settings
ieee_style = {
    'font.size': 10,
    'axes.labelsize': 10,
    'axes.titlesize': 10,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 6,
    'lines.linewidth': 1,
    'lines.markersize': 4,
    'grid.linestyle': '--',
    'grid.linewidth': 0.5,
    'figure.figsize': (3.5, 2.5),  # IEEE column width is typically 3.5 inches
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.format': 'pdf',
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.01
}
# Apply the IEEE style
plt.rcParams.update(ieee_style)
# plt.rcParams.update({'figure.dpi': '225'})
plt.rcParams['font.family'] = ['serif']
plt.rcParams['font.serif'] = ['Times New Roman']

class output:
    def __init__(self):
        pass 
    
    def save_data(self, xx):
        Results1 = xx[0]
        Results2 = xx[1]

        with open('output1.dat', 'w') as out1:
            for e in range(len(Results1)):
                out1.write(f'{Results1[e,0]:.16E}  {Results1[e,1]:.16f} {Results1[e,2]:.16f} {Results1[e,3]:.16f} \n')
                  
        with open('output2.dat', 'w') as out2:
            for e in range(len(Results2)):
                out2.write(f'{Results2[e,0]:.16E}  {Results2[e,1]:.16f} {Results2[e,2]:.16f} {Results2[e,3]:.16f} \n')

    def Two_Dynamics(self): 
        # ---- Automatically detect .dat files in the current directory ---- #
        file1 = glob.glob("output1.dat")
        file2 = glob.glob("output2.dat")

        if not file1 or not file2:
            print("Error: One or both data files (output1.dat, output2.dat) are missing.")
            return

        # Load data dynamically
        data1 = np.genfromtxt(file1[0])
        data2 = np.genfromtxt(file2[0])

        # ------- Plot --------- #
        fig, ax = plt.subplots()
        # fig.subplots_adjust(left=None, bottom=0.20, right=0.975, top=0.975, wspace=None, hspace=0.0)
        ax.tick_params(axis="y", direction="in")
        ax.tick_params(axis="x", direction="in")
        # ax.tick_params(bottom=True, top=True, left=True, right=True)

        ax.plot(data1[:,0]*1e9, data1[:,1], color='green', linestyle='solid', label=r'$m_{1,x}$') 
        ax.plot(data1[:,0]*1e9, data1[:,2], color='blue', linestyle='solid', label=r'$m_{1,y}$') 
        ax.plot(data1[:,0]*1e9, data1[:,3], color='red', linestyle='solid', label=r'$m_{1,z}$') 
        ax.plot(data2[:,0]*1e9, data2[:,1], color='orchid', linestyle='dashed', label=r'$m_{2,x}$') 
        ax.plot(data2[:,0]*1e9, data2[:,2], color='purple', linestyle='dashed', label=r'$m_{2,y}$') 
        ax.plot(data2[:,0]*1e9, data2[:,3], color='orange', linestyle='dashed', label=r'$m_{2,z}$') 
        # ax.vlines(x=100, ymin=-1.1, ymax=1.1, linestyles='dashed', colors='gray')
        
        ax.yaxis.set_major_formatter(ScalarFormatter())
        # ax.minorticks_off()
        ax.set_xlabel('Time (ns)')
        ax.set_ylabel('Magnetisation ($M/M_s$)')
        ax.legend(loc='upper left', bbox_to_anchor=(1, 1), ncol=1, frameon=False)

        # ---- Save the figure ---- #
        fig_filename = "Two_Spin_Dynamics.png"  # Change to .pdf, .svg if needed
        plt.savefig(fig_filename) #, dpi=300, bbox_inches='tight')  # High-res save
        
        plt.show()
