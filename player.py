import pyaudio
import wave
import numpy as np
from PyQt5 import QtCore

from convolution import OverlapSave, OverlapSaveMIMO


class Player(QtCore.QObject):

    # Qt signal
    stream_ended = QtCore.pyqtSignal()
    peak_updated = QtCore.pyqtSignal()

    # status value
    empty = 0 # no wave file
    ready = 1 # file opened (Need to create a new stream)
    playing = 2
    pausing = 3

    # the number of frames per buffer
    CHUNK = 2048
    
    #
    # ----- state -----
    #
    #  ----------------------------
    #  |         | wave  | stream |
    #  ----------------------------
    #  |   empty | close | close  |
    #  |   ready | open  | close  |
    #  | playing | open  | open   |
    #  | pausing | open  | open   |
    #  ----------------------------
    #
    # ----- function and state change -----
    #
    # set_file(): empty/ready*1/playing*2 -> ready
    #     play(): ready/playing*3 -> playing
    #     stop(): playing/pausing -> ready
    #    clear(): ready/playing/pausing -> empty
    #    pause(): playing -> pausing
    #   resume(): pausing -> playing
    # 
    #   *1*2: clear() is called.
    #   *3: stop() is called.
    #   *From other states, the function is passed through.
    #
    #
    # ----- If the status is "playing" but it is not actually playing -----
    #
    # Data supply by the callback function is finished.
    # The PyAudio stream is still open,
    # so I dare treat it as "playing" state.
    # Then, it should be `(stream.is_active | stream.is_stopped) == False`
    # --> see also actually_playing()
    # 
    # ----- configuration -----
    #
    # config = {
    #     'path2src': str,
    #     'path2fir': str,
    #     'gain_fir': float,
    #     'gain_src': float,
    #     'peak': float,
    # }
    #
    
    def __init__(self):
        super().__init__()
        self._init()

    def __del__(self):
        self._del()

    def _init(self):
        self.p = pyaudio.PyAudio()
        self.state = Player.empty

        self.device = self.p.get_default_output_device_info()
        self.host = self.p.get_host_api_info_by_index(self.device['hostApi'])
        self.portaudio_version = pyaudio.get_portaudio_version_text()

    def _del(self):
        self.clear()
        self.p.terminate()

    def reboot(self):
        self._del()
        self._init()

    def set_config(self, config):
        self.clear()

        if config['path2src'] == '':
            raise Exception('No source')
        
        elif config['path2fir'] == '':
            # play wave file direct
            generator = WavGenerator(
                    config, self.stream_ended, self.peak_updated)
        
        else:
            generator = ConvGenerator(
                    config, self.stream_ended, self.peak_updated, self.CHUNK)

        self.config = config
        self.generator = generator
        self.state = self.ready
        return self.state

    def play(self):
        if self.state == self.playing or self.state == self.pausing:
            self.stop()
            
        if self.state == self.ready:
            # check support (throws ValueError exception
            # if the configuration is not supported)
            ret = self.p.is_format_supported(
                    rate=self.generator.fs,
                    output_device=self.device['index'],
                    output_channels=self.generator.nchannels_out,
                    output_format=pyaudio.paFloat32
                    )
            # open stream
            self.stream = self.p.open(
                    rate=self.generator.fs,
                    channels=self.generator.nchannels_out,
                    format=pyaudio.paFloat32,
                    output=True,
                    output_device_index=self.device['index'],
                    frames_per_buffer=self.CHUNK,
                    stream_callback=self.generator.callback
                    )
            self.state = self.playing
        return self.state

    def set_pos(self, pos):
        if self.state != Player.empty:
            self.generator.set_pos(pos)
        return self.state

    def get_pos(self):
        if self.state != Player.empty:
            return self.generator.get_pos()
        return 0

    def pause(self):
        if self.state == Player.playing:
            if self.stream.is_active():
                self.stream.stop_stream()
                self.state = Player.pausing
        return self.state
    
    def resume(self):
        if self.state == Player.pausing:
            if self.stream.is_stopped():
                self.stream.start_stream()
                self.state = Player.playing
        return self.state

    def stop(self):
        if self.state == Player.playing or self.state == Player.pausing:
            self.stream.stop_stream()
            self.stream.close()
            self.generator.set_pos(0)
            self.state = Player.ready
        return self.state

    def clear(self):
        self.stop()
        if self.state == Player.ready:
            del self.generator
            self.state = Player.empty
        return self.state
    
    def actually_playing(self):
        # return True if (stream.is_active | stream.is_stopped) == True
        if self.state == Player.playing or self.state == Player.pausing:
            if self.stream.is_active() or self.stream.is_stopped():
                return True
        return False
    
    def get_output_device_list(self):
        n = self.p.get_device_count()
        device_list = []
        for i in range(n):
            info = self.p.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                device_list.append(info)
        return device_list

    def get_default_output_device(self):
        return self.p.get_default_output_device_info()
    
    def get_fs(self):
        return self.generator.fs

    def get_nframes(self):
        return self.generator.nframes

    def get_generator_info(self):
        info = {}
        info['ch_src'] = self.generator.nchannels_src
        info['ch_out'] = self.generator.nchannels_out
        info['fs'] = self.generator.fs
        info['mode'] = self.generator.mode
        if hasattr(self.generator, 'fir_shape'):
            info['fir_shape'] = self.generator.fir_shape
        else:
            info['fir_shape'] = None
            
        return info


class WavGenerator:
    
    def __init__(self, config, stream_ended, peak_updated):
        self.mode = 'direct'
        self.config = config
        self.stream_ended = stream_ended # Qt Signal
        self.peak_updated = peak_updated # Qt Signal

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
                
    def __del__(self):
        if 'ws' in locals():
            self.wf.close()

    def callback(self, in_data, frame_count, time_info, status):
        if self.wf.tell() == self.nframes:
            self.stream_ended.emit() # --------------------------> emit signal
            return b'', pyaudio.paComplete
        else:
            # read frame
            frames = self.wf.readframes(frame_count)
            nlack = self.bytes_per_frame_src * frame_count - len(frames)
            if nlack != 0:
                frames += b'\x00' * nlack
            
            # convert to numpy array
            data = self.buffer2float(frames)

            # gain                
            data *= self.config['gain_src']
            
            # clipping
            self._detect_peak(data)

            # convert to binary
            out_data = data.astype(np.float32).tostring()

            return out_data, pyaudio.paContinue

    def _detect_peak(self, data):
        peak = np.max(np.abs(data))
        if peak > self.config['peak']:
            self.config['peak'] = peak
            self.config['peak_db'] = 20 * np.log10(peak)
            self.peak_updated.emit()
        
    def set_pos(self, pos):
        self.wf.setpos(pos)

    def get_pos(self):
        return self.wf.tell()

    def buffer2float_16bit(self, frames):
        return np.frombuffer(frames, dtype=np.int16) / 32768

    def buffer2float_24bit(self, frames):
        a8 = np.frombuffer(frames, dtype=np.uint8)
        tmp = np.zeros((a8.shape[0] // 3, 4), dtype=np.uint8)
        tmp[:, 1:] = a8.reshape(-1, 3)
        return tmp.view(np.int32)[:, 0] / 2147483648

    def buffer2float_32bit(self, frames):
        return np.frombuffer(frames, dtype=np.int32) / 2147483648



class ConvGenerator(WavGenerator):
    
    def __init__(self, config, stream_ended, peak_updated, chunksize):
        super().__init__(config, stream_ended, peak_updated)
        
        # try to import FIR filter
        fir = np.load(config['path2fir'], 'r')
        self.fir_shape = fir.shape

        # set convolver
        if fir.ndim == 1:
            self.os = OverlapSave(fir, chunksize, self.nchannels_src)
            self.mode = 'SISO'
        elif fir.ndim == 3:
            if fir.shape[1] != self.nchannels_src:
                msg = 'channel mismatch: source %d-out >> FIR %d-in'\
                                        % (self.nchannels_src, fir.shape[1])
                raise Exception(msg)

            self.os = OverlapSaveMIMO(fir, chunksize)
            self.nchannels_out = fir.shape[0]
            self.mode = 'MIMO'
        else:
            raise Exception('Invalid FIR shape')
    
    def callback(self, in_data, frame_count, time_info, status):
        
        # read frames from source, and convert to float
        frames = self.wf.readframes(frame_count)
        data_in = self.buffer2float(frames)
        
        # gain (source)
        data_in *= self.config['gain_src']
        
        # convolution
        data_in = data_in.reshape([self.nchannels_src, -1], order='F')
        data_out, len_buf = self.os.conv(data_in)
        data_out = data_out.astype(np.float32)
        
        if len_buf < 0:
            self.stream_ended.emit() # emit signal
            return b'', pyaudio.paComplete

        # gain (FIR)
        data_out *= self.config['gain_fir']

        # peak
        self._detect_peak(data_out)
        
        # output
        return data_out.reshape(-1, order='F').tostring(), pyaudio.paContinue

    def set_pos(self, pos):
        self.os.clear_buffer()
        self.wf.setpos(pos)


    

if __name__ == '__main__':

    import time
    
    # (1) instantiate Player
    p = Player()

    # (2) set config
    config = {
        'path2src': '../source/hato.wav',
        'path2fir': '../source/FIR_MINI_HATS.npy',
        'gain_fir': 1,
        'gain_src': 1,
        'peak': 0,
    }
    p.set_config(config)
    '''
    # (3) play
    p.play()
    time.sleep(5)

    # pause
    p.pause()
    time.sleep(2)
    
    # resume
    p.resume()
    time.sleep(5)
    
    # (4) stop
    p.stop()

    # (5) clear
    p.clear()
    '''

    p.play()
    time.sleep(5)
    config['gain_src'] = 0.5
    time.sleep(5)



