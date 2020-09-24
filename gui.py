import sys
import time
import platform
import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore

import pyaudio

from player import Player
from playlist import PlayListView, PlayListModel


class ComboBox(QtWidgets.QComboBox):
    popuped = QtCore.pyqtSignal()

    def showPopup(self):
        self.popuped.emit()
        super(ComboBox, self).showPopup()



class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()

        self.player = Player()
        self.playlistmodel = PlayListModel()
        
        self.initUI()
        self.connect()
        
        #self.count_closecalled = 0 # for cmd+Q call twice the closeEvent (probably Qt Bug)

    def initUI(self):
        
        self.setWindowTitle('Kelp')
        self.resize(800, 500)
        self.setMinimumSize(600, 300) 
        
        # display
        self.label_state = QtWidgets.QLabel(self)

        # time display
        self.label_pos = QtWidgets.QLabel('0:00/0:00', self)
        self.label_pos.setMinimumSize(80, 30)
        self.label_pos.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(500) # milisecond
        self.timer.timeout.connect(self.update_timedisplay)
        
        # play/pause button
        self.btn_play = QtWidgets.QPushButton('Play', self)
        self.btn_play.setMinimumSize(80, 30)

        # slider
        self.slider_pos = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.step_slider = 5000
        self.slider_pos.setMaximum(self.step_slider)
        self.slider_pos.setEnabled(False)

        # Device list
        self.combo_device = ComboBox(self)
        self.combo_device.setMinimumSize(200, 30)
        self.combo_device.setMaximumSize(200, 30)
        self.update_device_combo()
        self.set_device()
        

        # play list
        self.playlistview = PlayListView(self.playlistmodel)
        self.playlistview.installEventFilter(self) # set eventFilter to tableView
        
        # export button
        #btn_export = QtWidgets.QPushButton('Export', self)
        #btn_export.setMinimumSize(80, 30)
        
        # ----- layout -----
        #   row1: display, device list
        #   row2: position slider, position disploy, play/pause button
        #   row3: play list
        #   row4: export butto

        box_row1 = QtWidgets.QHBoxLayout()
        box_row1.addWidget(self.label_state)
        box_row1.addWidget(self.combo_device, alignment=QtCore.Qt.AlignRight)

        box_row2 = QtWidgets.QHBoxLayout()
        box_row2.addWidget(self.label_pos)
        box_row2.addWidget(self.slider_pos)
        box_row2.addWidget(self.btn_play)
        
        central_box = QtWidgets.QVBoxLayout()
        central_box.addLayout(box_row1)
        central_box.addLayout(box_row2)
        central_box.addWidget(self.playlistview)
        #central_box.addWidget(btn_export, alignment=QtCore.Qt.AlignRight)

        central_widget = QtWidgets.QWidget(self)
        central_widget.setLayout(central_box)
        self.setCentralWidget(central_widget)
        

        # set font
        if platform.system() == "Linux": # for Linux using the X Server
            pass
        elif platform.system() == "Windows": # for Windows
            pass
        elif platform.system() == "Darwin": # for MacOS
            font = QtGui.QFont('Monaco', 12)
            self.setFont(font)
        
    def connect(self):
        
        # play button
        self.btn_play.clicked.connect(self.play_pause)

        # play next (automatically)
        self.player.stream_ended.connect(self.play_next)
        
        # double clock the playlist item
        #self.playlistview.doubleClicked.connect(self.play)
        self.playlistview.start_playing.connect(self._play_row)

        # set device
        self.combo_device.popuped.connect(self.update_device_combo)
        self.combo_device.activated.connect(self.set_device)
        
        # set position
        self.slider_pos.sliderMoved.connect(self.indicate_position)
        self.slider_pos.sliderPressed.connect(self.indicate_position)
        self.slider_pos.sliderReleased.connect(self.set_position)

        # stop playing when replacing item being playing
        self.playlistmodel.playingItemReplaced.connect(self.stop)
        self.playlistmodel.playingItemRemoved.connect(self.stop)

        # update peak
        self.player.peak_updated.connect(self.update_peak)


    def eventFilter(self, obj, event):
        # This function is called before the other object-specific event
        # call like QTableView.keyPressEvent(). Those event handling does
        # not continue, if this function returns `True`.

        if event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            mod = event.modifiers()
            
            # space key -> play/pause
            if key == QtCore.Qt.Key_Space:
                self.play_pause()
            
            # enter/return key -> play from the beginning if there is selection
            elif key == QtCore.Qt.Key_Return or key == QtCore.Qt.Key_Enter:
                indexes_sel = self.playlistview.selectedIndexes()
                if indexes_sel:
                    self.play()

            # escape -> clear selection
            elif key == QtCore.Qt.Key_Escape:
                self.playlistview.clearSelection()
                
            # delete/backspace -> remove selection from playlist
            elif key == QtCore.Qt.Key_Backspace:
                self.remove_selected()

            # save playlist
            elif key == QtCore.Qt.Key_S and mod == QtCore.Qt.ControlModifier:
                self.playlistmodel.save_csv(self.playlistmodel.savefile)
                
            # rollback previous save point
            elif key == QtCore.Qt.Key_R and mod == QtCore.Qt.ControlModifier:
                self.playlistmodel.rollback_savepoint()

            else:
                return False # continue to default handling
            return True
        
        elif event.type() == QtCore.QEvent.Drop:
            print('gui-drop')
            
        #print(event.type())

        return False # continue to default handling
            
        
    def play(self):
        indexes_sel = self.playlistview.selectedIndexes()
        if indexes_sel:
            #row = indexes_sel[0].row()
            rows_sel = {index.row() for index in indexes_sel}
            row = sorted(list(rows_sel))[0]
        else:
            row = 0

        self._play_row(row)
        
        
    def _play_row(self, row):
        self.label_pos.setText('0:00/0:00')
        self.slider_pos.setValue(0)
        self.slider_pos.setEnabled(False)
        self.playlistmodel.clear_playmark()

        data = self.playlistmodel.get_data(row)
        print('play: row', row)
        print('source:', data['path2src'])
        print('FIR:', data['path2fir'])
        
        try:
            state = self.player.set_config(data)
        except Exception as e:
            print(e, file=sys.stderr)
            self.label_state.setText('Player Stopped\n%s' % e)
            self.playlistmodel.set_errormark(row)
            return

        # label
        info = self.player.get_generator_info()
        text = 'Source: %d ch, %d Hz, %s\n'\
                % (info['ch_src'], info['fs'], data['disp_src'])

        if info['mode'] == 'SISO':
            text += 'FIR: single, %s' % data['disp_fir']
        elif info['mode'] == 'MIMO':
            shape = info['fir_shape']
            text += 'FIR: %din/%dout, %s'\
                    % (shape[1], shape[0], data['disp_fir'])
        self.label_state.setText(text)

        try:
            state = self.player.play()
        except Exception as e:
            print(e, file=sys.stderr)
            self.label_state.setText('Player Stopped\n%s' % e)
            self.playlistmodel.set_errormark(row)
            return
            
        if state == Player.playing:
            self.btn_play.setText('Pause')
            self.playlistmodel.set_playmark(row)

            # for time display
            self.timer.start()
            self.fs = self.player.get_fs()
            self.nframes = self.player.get_nframes()
            length_sec = self.nframes / self.fs
            self.len_label = '%d:%02d' % (length_sec // 60, length_sec % 60)
            self.slider_pos.setEnabled(True)
        

    def stop(self):
        self.timer.stop()
        self.label_pos.setText('0:00/0:00')
        self.playlistmodel.clear_playmark()
        self.player.stop()
        self.label_state.setText('Player Stopped\n')
        self.slider_pos.setValue(0)
        self.slider_pos.setEnabled(False)


    def play_pause(self):
        # playing or pausing
        if self.player.actually_playing():
            
            if self.player.state == Player.playing:
                self.player.pause()
                self.timer.stop()
                self.btn_play.setText('Play')
            else:
                self.player.resume()
                self.timer.start()
                self.btn_play.setText('Pause')
        else:
            self.play()
            
    
    def play_next(self):
        # now playing
        row_next = self.playlistmodel.get_row_playing() + 1
        if row_next == self.playlistmodel.rowCount():
            self.stop()
            print('play_next: no next')
            return

        while self.player.actually_playing():
            time.sleep(0.005)
            
        # next row
        print('play_next')
        self._play_row(row_next)



    def update_device_combo(self):
        # stop
        self.stop()
        '''
        # newly instantiate pyaudio to get newest info.
        # -> This plan is off and cannot get newest device list.
        #    PyAudio seems to be shared in one process.
        #    We have to terminate everything.
        p = pyaudio.PyAudio()
        avalable_devices = []
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                avalable_devices.append(info)
        p.terminate()
        '''
        # remember current device
        current_device = self.player.device

        # re-instatiate pyaudio
        self.player.reboot() # to get new avalable device list
        avalable_devices = self.player.get_output_device_list()
        avalable_device_names = [dev['name'] for dev in avalable_devices]

        # update combo box
        self.combo_device.clear()
        self.combo_device.addItems(avalable_device_names)

        '''
        # set default device
        default = self.player.get_default_output_device()
        self.player.device = default
        index_current = self.combo_device.findText(default['name'])
        self.combo_device.setCurrentIndex(index_current)
        '''
        # select current device
        if not current_device['name'] in avalable_device_names:
            current_device = self.player.get_default_output_device()
        index_current = self.combo_device.findText(current_device['name'])
        self.combo_device.setCurrentIndex(index_current)
        self.player.device = current_device

        
        
    def set_device(self):
        # This program probably cannot distinguish between devices with
        # the same name. It is necessary to manage by associating with
        # the info['index'].
        # But here this is left for future work:-)

        # stop
        self.stop()

        # get current device name
        designated_name = self.combo_device.currentText()
        print('\ndesignated:', designated_name)
        
        # re-instantiate pyaudio and get new avalable device list
        self.player.reboot()
        avalable_devices = self.player.get_output_device_list()
        avalable_device_names = [dev['name'] for dev in avalable_devices]
        print('avalable:', avalable_device_names)

        # update combo box
        self.combo_device.clear()
        self.combo_device.addItems(avalable_device_names)
        
        # designated device is in avalable devices?
        if not designated_name in avalable_device_names:
            # replace by default device
            default = self.player.get_default_output_device()
            designated_name = default['name']
            
            # report to user
            text = 'Player Stopped\n'
            text += '[Error] %s no longer exists.' % designated_name
            self.label_state.setText(text)
            print(designated_name, 'no longer exists.')
            
        # set device
        index_designated = avalable_device_names.index(designated_name)
        self.player.device = avalable_devices[index_designated]
        i_host = avalable_devices[index_designated]['hostApi']
        self.player.host = self.player.p.get_host_api_info_by_index(i_host)
        self.combo_device.setCurrentIndex(index_designated)
        
        text = 'Player Stopped\n'
        text += 'Device: %s ' % self.player.device['name']
        text += '(%s)' % self.player.host['name']
        self.label_state.setText(text)
        print('Device->', designated_name)

    
    
    def set_position(self):
        pos = int(self.slider_pos.value() / self.step_slider * self.nframes)
        self.player.set_pos(pos)
        self.timer.start()

    
    def indicate_position(self):
        self.timer.stop()
        pos = self.slider_pos.value() / self.step_slider
        pos_sec = pos * self.nframes / self.fs        
        m = pos_sec // 60
        s = pos_sec % 60
        text = '%d:%02d/' % (m, s) + self.len_label
        self.label_pos.setText(text)


    def update_timedisplay(self):
        pos = self.player.get_pos()
        self.slider_pos.setValue(pos / self.nframes * self.step_slider)
        
        pos_sec = pos / self.fs
        m = pos_sec // 60
        s = pos_sec % 60
        text = '%d:%02d/' % (m, s) + self.len_label
        self.label_pos.setText(text)


    def remove_selected(self):
        indexes_sel = self.playlistview.selectedIndexes()
        self.playlistmodel.remove_selected(indexes_sel)


    def closeEvent(self, event):
        '''
        if self.count_closecalled == 0: # for cmd+Q call twice the closeEvent (probably Qt Bug)
            self.playlistmodel.save_csv(self.playlistmodel.savefile)
        self.count_closecalled += 1
        '''
        event.accept()

    def update_peak(self):
        # now playing
        row = self.playlistmodel.get_row_playing()
        if row < 0:
            return
        col = 5 #col = self.playlistmodel.header.index('Peak')
        index = self.playlistmodel.index(row, col)
        self.playlistmodel.dataChanged.emit(index, index)


vvvvv = '''
 ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ><>
    Kelp -- FIR Convolution Player
    penrin(github.com/penrin/Kelp)
<>< ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
\n
'''
vvvvv += 'Python: %s\n' % sys.version
vvvvv += 'NumPy: %s\n' % np.__version__
vvvvv += 'PyQt5: %s\n' % QtCore.PYQT_VERSION_STR
vvvvv += 'platform: %s\n' % platform.platform()

if __name__ == '__main__':
    print(vvvvv)
    
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
    



