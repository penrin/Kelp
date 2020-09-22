Kelp
====

FIR Convolution Audio Player with GUI




Requirements
------------

* Python3
* PortAudio, PyAudio
* NumPy
* PyQt5




File format
-----------

### Sound Source

WAVE file (16/24/32 bit integer) format is supported.


### FIR

FIR coefficient data is imported from the `.npy` file, which is standard binary file format in NumPy.

There are two convolution modes that switch according to the dimensions of the FIR data array.

* **SISO mode with 1D array**
–
FIR is treated as a SISO system if its data array has only one dimention. 
For multi-channel sound sources, FIR is applied in parallel to each channel.

* **MIMO mode with 3D array**
–
FIR is treated as a MIMO/MISO/SIMO system if its data array has three dimentions.
The axes 0, 1, 2 should be output channels, input channels, and taps, respectively.
If the number of sound source channels and the number of FIR input channels do not match, playback will stop.







ToDo
----------------------------

* Enrich Help
* repeat one/all
* Show indicator when drag and drop files, and drop there
* Export convolved signal

