import pyaudio
import wave
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

    def set_file(self, fname):
        self.clear()
        self.wf = wave.open(fname, 'rb')
        self.fname = fname
        self.fs = self.wf.getframerate()
        self.nframes = self.wf.getnframes()

        self.state = Player.ready
        return self.state

    def _callback(self, in_data, frame_count, time_info, status):

        if self.wf.tell() == self.nframes:
            self.stream_ended.emit() # --------------------------> emit signal
            return b'', pyaudio.paComplete
        else:
            out_data = self.wf.readframes(frame_count)
            nlack = self.bytes_per_frame * frame_count - len(out_data)
            if nlack != 0:
                out_data += b'\x00' * nlack
            return out_data, pyaudio.paContinue

    def play(self):
        if self.state == Player.playing or self.state == Player.pausing:
            self.stop()
        
        if self.state == Player.ready:
            self.nframes = self.wf.getnframes()
            self.bytes_per_frame = self.wf.getsampwidth() * self.wf.getnchannels()
            
            # open stream
            self.stream = self.p.open(
                    format=self.p.get_format_from_width(self.wf.getsampwidth()),
                    channels=self.wf.getnchannels(), rate=self.wf.getframerate(),
                    output=True, stream_callback=self._callback,
                    output_device_index=self.device['index']
                    )
            self.state = Player.playing
        return self.state
        
    def set_pos(self, pos):
        if self.state != Player.empty:
            self.wf.setpos(pos)
        return self.state

    def get_pos(self):
        if self.state != Player.empty:
            return self.wf.tell()
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
            self.wf.rewind()
            self.state = Player.ready
        return self.state
        
    def clear(self):
        self.stop()
        if self.state == Player.ready:
            self.wf.close()
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



if __name__ == '__main__':

    import time
    
    # (1) instantiate Player
    p = Player()
    print('instatiate', p.state)

    # (2) set file
    p.set_file('../source/change_the_world.wav')
    p.set_file('../source/hato.wav')
    print('set file', p.state)

    
    # (3) play
    p.play()
    print('play', p.state)
    
    time.sleep(5)

    # pause
    p.pause()
    print('pause', p.state)

    time.sleep(2)
    
    # resume
    p.resume()
    print('resume', p.state)

    time.sleep(5)
    
    # (4) stop
    p.stop()
    print('stop', p.state)

    # (5) clear
    p.clear()
    print('clear', p.state)





