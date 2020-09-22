Kelp
====

FIR 畳み込み機能つきオーディオプレーヤ


Requirements
------------

* Python3
* PortAudio, PyAudio
* NumPy
* PyQt5



File format
-----------

### 音源

WAVE ファイル (16/24/32 bit 整数型) に対応。


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


操作
---

* **プレイリスト構築**
–

* **ゲイン調整**
–

* **ピークリセット**
–

* **Escape Key**
–

* **Delete/Backspace Key**
–

* **Space Key**
–

* **Enter Key**
–

* **⌘+S Key**
–

* **⌘+R Key**
–

* **⌘+Q Key**
–


Automator app 作成
-----------------

* Start Automator.app
* Choose "Application"
* Choose "Run Shell Script"
* For example, write the folowing scripts:

```
path2kelp="/path/to/kelp"
path2python="/path/to/python"
${path2python}/python ${PATH2KELP}/gui.py > ${PATH2KELP}/log.txt
```

* Save the recipe
* 



ToDo
----------------------------

* Export convolved signal
* Enrich Help
* repeat one/all
* Show indicator when drag and drop files, and drop there
* show clipped sections in the slider groove