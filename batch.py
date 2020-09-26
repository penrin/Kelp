import os
import sys
import time
import wave
import numpy as np

from convolution import OverlapSave, OverlapSaveMIMO
import player

from PyQt5 import QtWidgets, QtGui, QtCore




# 大容量の書き出しの時の判断。

def export(tasks, path, sampwidth, N_str, qprog):
    
    if path[-1] != os.sep:
        path += os.sep

    error_log = ''

    
    num_tasks = len(tasks)
    for cnt_task, task in enumerate(tasks):

        print('batch [%d/%d]' % (cnt_task + 1, num_tasks))
        
        if qprog.wasCanceled():
            break
        
        # check
        if task['path2src'] == '':
            error_log += '[%d/%d] skipped\n' % (cnt_task + 1, num_tasks)
            error_log += 'Reason: No source.\n'
            task['playmark'] = '!'
            continue
        
        elif task['gain_src'] == 0:
            error_log += '[%d/%d] skipped\n' % (cnt_task + 1, num_tasks)
            error_log += 'Reason: Source is muted.\n'
            task['playmark'] = '!'
            continue
        
        elif task['gain_fir'] == 0:
            error_log += '[%d/%d] skipped\n' % (cnt_task + 1, num_tasks)
            error_log += 'Reason: FIR is muted.\n'
            task['playmark'] = '!'
            continue

        # make generator
        try:
            if task['path2fir'] == '':
                gene = WavGenerator(task)
            else:
                gene = ConvGenerator(task, N_str)
        except Exception as e:
            error_log += '[%d/%d] failed\n' % (cnt_task + 1, num_tasks)
            error_log += 'Reason: %s\n' % e
            task['playmark'] = '!'
            continue
        
        if qprog.wasCanceled():
            break

        # process
        src_base = os.path.splitext(os.path.basename(task['disp_src']))[0]
        fir_base = os.path.splitext(os.path.basename(task['disp_fir']))[0]
        
        fname = '%s_%.1fdB' % (src_base, task['gain_src_db'])
        if fir_base:
            fname += '_%s_%.1fdB' % (fir_base, task['gain_fir_db'])
        fname += '.wav'
        
        label = '\nExport [%d/%d]\n' % (cnt_task + 1, num_tasks)
        label += 'Source: %s\n' % task['disp_src']
        label += 'Channels: %d\n' % gene.nchannels_src
        label += 'FIR: %s\n' % task['disp_fir']
        label += 'Shape: %s\n' % gene.fir_shape
        label += 'FFTpoint: %s\n' % gene.fftpoint
        label += '--> %s' % fname
        qprog.setLabelText(label)

        qlabel = QtWidgets.QLabel(label)
        qlabel.setAlignment(QtCore.Qt.AlignLeft)
        qprog.setLabel(qlabel)
        print(label)
        
        # ----- Classificate from here
        if sampwidth == 2:
            float2buffer = float2buffer_16bit
        elif sampwidth == 3:
            float2buffer = float2buffer_24bit
        elif sampwidth == 4:
            float2buffer = float2buffer_32bit
        else:
            raise Exception ('Unsupported wave format')


        wav_params = (gene.nchannels_out, sampwidth, gene.fs,
                                        0, 'NONE', 'not compressed')
        
        try:
            ww =  wave.open(path + fname, 'wb')
            ww.setparams(wav_params)
            task['peak'] = 0
            task['peak_db'] = -np.inf
            qprog.setRange(0, gene.n_loop)
            for n in range(gene.n_loop):
                if qprog.wasCanceled():
                    break
                qprog.setValue(n)
                data = gene.calc()
                frames = float2buffer(data)
                ww.writeframes(frames)
            ww.close()

        except Exception as e:
            error_log += '[%d/%d] failed\n' % (cnt_task + 1, num_tasks)
            error_log += 'Reason: %s\n' % e
            task['playmark'] = '!'
            continue
        # ----- (Classificate) to here

        # peak warning
        if task['peak_db'] > 0:
            error_log += '[%d/%d] warning\n' % (cnt_task + 1, num_tasks)
            error_log += 'Reason: %.1f dB over.\n' % (task['peak_db'])

    return error_log



def float2buffer_16bit(data): # 1-dim input
    data *= 32768
    np.clip(data, -32768, 32767, out=data)
    return data.astype(np.int16).tostring()

def float2buffer_24bit(data): # 1-dim input
    data *= 8388608
    np.clip(data, -8388608, 8388607, out=data)
    a32 = np.asarray(data, dtype=np.int32)
    a8 = (a32.reshape(a32.shape + (1,)) >> np.array([0, 8, 16])) & 255
    return a8.astype(np.uint8).tostring()

def float2buffer_32bit(data): # 1-dim input
    data *= 2147483648
    np.clip(data, -2147483648, 2147483647, out=data)
    return data.astype(np.int32).tostring()



class WavGenerator(player.WavGenerator):
    
    def __init__(self, config):
        
        self.config = config
        self.wf = wave.open(config['path2src'], 'rb')

        self.fs = self.wf.getframerate()
        self.ws = self.wf.getsampwidth()
        self.nframes = self.wf.getnframes()
        self.nchannels_src = self.wf.getnchannels()
        self.nchannels_out = self.nchannels_src

        self.bytes_per_frame_src = self.nchannels_src * self.ws

        if self.ws == 2:
            self.buffer2float = self.buffer2float_16bit
        elif self.ws == 3:
            self.buffer2float = self.buffer2float_24bit
        elif self.ws == 4:
            self.buffer2float = self.buffer2float_32bit
        else:
            raise Exception ('Unsupported wave format')
        
        #
        self.fftpoint = ''
        self.fir_shape = ''
        self.chunksize = 4096
        self.n_loop = int(np.ceil(self.nframes / self.chunksize))

    def calc(self):
        frames = self.wf.readframes(self.chunksize)
        data = self.buffer2float(frames)
        data *= self.config['gain_src']
        self._detect_peak(data)
        return data

    def _detect_peak(self, data):
        peak = np.max(np.abs(data))
        if peak > self.config['peak']:
            self.config['peak'] = peak
            self.config['peak_db'] = 20 * np.log10(peak)



class ConvGenerator(WavGenerator):

    def __init__(self, config, N_str):
        super().__init__(config)
        
        # try to import FIR filter
        fir = np.load(config['path2fir'], 'r')

        # decide chunksize according to N_str
        len_fir = fir.shape[-1]
        if 'nextpow2+' in N_str:
            n = int(N_str.split('+')[1])
            nextpow2 = int(np.ceil(np.log2(len_fir)))
            fftpoint = 2 ** (nextpow2 + n)
        else:
            fftpoint = int(N_str)
        self.chunksize = fftpoint // 2

        # set convolver
        if fir.ndim == 1:
            print('SISO')
            self.os = OverlapSave(fir, self.chunksize, self.nchannels_src)
            self.mode = 'SISO'
        elif fir.ndim == 3:
            print('MIMO')
            if fir.shape[1] != self.nchannels_src:
                msg = 'channel mismatch: source %d-out >> FIR %d-in'\
                                        % (self.nchannels_src, fir.shape[1])
                raise Exception(msg)

            self.os = OverlapSaveMIMO(fir, self.chunksize)
            self.nchannels_out = fir.shape[0]
            self.mode = 'MIMO'
        else:
            raise Exception('Invalid FIR shape')

        # nblocks and count
        len_out = self.nframes + len_fir - 1
        self.n_loop = int(np.ceil(len_out / self.chunksize))
        self.fftpoint = '%d' % (self.chunksize * 2)
        self.fir_shape = str(fir.shape)
        

    def calc(self):
        frames = self.wf.readframes(self.chunksize)
        data = self.buffer2float(frames)
        data *= self.config['gain_src']
        
        data = data.reshape([self.nchannels_src, -1], order='F')
        data_out, len_buf = self.os.conv(data)

        if len_buf > 0:
            data_out *= self.config['gain_fir']
            self._detect_peak(data_out)
            return data_out[:, :len_buf].reshape(-1, order='F')
        else:
            return data_out[:, :0].reshape(-1, order='F')


