import pyaudio
import wave
import numpy as np
from PyQt5 import QtCore

class Player(QtCore.QObject):

    # Qt signal
    stream_ended = QtCore.pyqtSignal()

    # status value
    empty = 0 # no wave file
    ready = 1 # file opened (Need to create a new stream)
    playing = 2
    pausing = 3
    
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
            generator = WavGenerator(config, self.stream_ended)
        
        else:
            ndim_fir = np.load(config['path2fir'], 'r').ndim

            if ndim_fir == 1:
                generator = ParallelSISOGenerator(config, self.stream_ended)
            elif ndim_fir == 3:
                generator = MIMOGenerator(config, self.stream_ended)
            else:
                raise Exception('Invalid FIR shape')

        self.config = config
        self.generator = generator
        self.state = self.ready
        return self.state

    def play(self):
        if self.state == self.playing or self.state == self.pausing:
            self.stop()
        
        if self.state == self.ready:
            # open stream
            self.stream = self.p.open(
                    format=pyaudio.paFloat32,
                    channels=self.generator.nchannels, rate=self.generator.fs,
                    output=True, stream_callback=self.generator.callback,
                    output_device_index=self.device['index']
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


class WavGenerator:

    def __init__(self, config, stream_ended):
        self.config = config
        self.stream_ended = stream_ended # Qt Signal

        self.wf = wave.open(config['path2src'], 'rb')

        self.fs = self.wf.getframerate()
        self.ws = self.wf.getsampwidth()
        self.nframes = self.wf.getnframes()
        self.nchannels = self.wf.getnchannels()
        
        self.bytes_per_frame = self.wf.getnchannels() * 4 # PaFloat32

        if self.ws == 2:
            self.buffer2float = self.buffer2float_16bit
        elif self.ws == 3:
            self.buffer2float = self.buffer2float_24bit
        elif self.ws == 4:
            self.buffer2float = self.buffer2float_32bit
        else:
            raise Exception ('Unsupported wave format')
        
        # config['gain_src'] can be changed on the GUI side
        self.gain_dB = config['gain_src']
        self.gain = 10 ** (self.gain_dB / 20)
        
        
    def __del__(self):
        self.wf.close()

    def callback(self, in_data, frame_count, time_info, status):
        if self.wf.tell() == self.nframes:
            self.stream_ended.emit() # --------------------------> emit signal
            return b'', pyaudio.paComplete
        else:
            # read frame
            frames = self.wf.readframes(frame_count)
            nlack = self.bytes_per_frame * frame_count - len(frames)
            if nlack != 0:
                frames += b'\x00' * nlack
            
            # convert to numpy array
            data = self.buffer2float(frames)

            # detect config['gain_src'] changes and recalculate linear gain
            if self.gain_dB != self.config['gain_src']:
                self.gain_dB = self.config['gain_src']
                self.gain = 10 ** (self.gain_dB / 20)
                
            # gain                
            data *= self.gain

            # convert to binary
            out_data = data.astype(np.float32).tostring()

            return out_data, pyaudio.paContinue
        
    def set_pos(self, pos):
        self.wf.setpos(pos)

    def get_pos(self):
        return self.wf.tell()

    def buffer2float_16bit(self, frames):
        return np.frombuffer(frames, dtype=np.int16) / 32768

    def buffer2float_24bit(self, frames):
        a8 = np.frombuffer(frames, dtype=np.uint8)
        tmp = np.zeros((nframes * nchannels, 4), dtype=np.uint8)
        tmp[:, 1:] = a8.reshape(-1, 3)
        return tmp.view(np.int32)[:, 0] / 2147483648

    def buffer2float_32bit(self, frames):
        return np.frombuffer(frames, dtype=np.int32) / 2147483648



class ParallelSISOGenerator:

    def __init__(self, config, stream_ended):
        raise Exception ('not supported yet')


class MIMOGenerator:
    
    def __init__(self, config, stream_ended):
        raise Exception ('not supported yet')


    

if __name__ == '__main__':

    import time
    
    # (1) instantiate Player
    p = Player()

    # (2) set config
    config = {
        'path2src': '../source/hato.wav',
        'path2fir': '',
        'gain_fir': 0,
        'gain_src': 0,
        'peak': None,
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
    config['gain_src'] = -10
    time.sleep(5)



