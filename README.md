Kelp
====

Audio Player with FIR Convolver

```
% python Kelp/gui.py
```

[日本語](./README_JP.md)


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

There are two convolution modes that switch according to the dimensions of the FIR data array:

* **SISO mode with 1D array**
–
FIR is treated as a SISO system if its data array has only one dimention. 
For multi-channel sound sources, FIR is applied in parallel to each channel.

* **MIMO mode with 3D array**
–
FIR is treated as a MIMO/MISO/SIMO system if its data array has three dimentions.
The axes 0, 1, 2 should be output channels, input channels, and taps, respectively.
If the number of sound source channels and the number of FIR input channels do not match, playback will stop.




Usage
-----

* **Playlist**
–
Drop a `.wav` or `.npy` file into the playlist field to organize sound source and FIRs in the playlist.
Dropping multiple files add all combinations of sources and FIRs.
If there are selection, dropping one item replace the selected items.

* **Device**
–
Select output device in the combo box on the top right of the window.

* **Reorder items**
–
Drag and drop items to reorder them.
Click the column headers to sort items.

* **Play/Pause button**
–
Play/Pause/Resume.
You can also use the space key.

* **Play from the head**
–
By double-clicking or pressing the enter key, the selected item is played back from the beginning.
(Internally, the Wave file is reopened and the FIR is reloaded.)

* **Position slider**
–
Move the handle of the slider to set playback position.

* **Gain adjustment**
–
Turn the mouse wheel on it to adjust it in 1 dB steps
(0.1 dB steps with the ⌘ key).
Double click it to toggle between 0 and -inf.

* **Peak Reset**
–
Double click it.

* **Escape Key**
–
Clear all selection.

* **⌘+A Key**
–
Select all.

* **Delete/Backspace Key**
–
Remove selected FIRs.
Or remove items from playlist if they have no FIRs.

* **⌘+S Key**
–
Save the playlist.
The saved list is loaded when presssing ⌘+R key or next start.

* **⌘+R Key**
–
Rollback playlist to the previous savepoint.

* **⌘+Q Key**
–
Quit.




Automator app
-------------

* Start Automator.app
* Choose "Application"
* Choose "Run Shell Script"
* For example, write the folowing scripts:

```
PATH_PYTHON="/path/to/python"
PATH_KELP="/path/to/kelp"
${PATH_PYTHON}/python ${PATH_KELP}/gui.py $@ > ${PATH_KELP}/log.txt
```
* Save the recipe



ToDo
----------------------------

* Show indicator when drag and drop files, and drop there
* Improve convolution performance
	- Optimize overlap length
	- Avoid FFTs with the same FIR (when "Export"ing)
