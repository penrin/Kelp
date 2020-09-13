import sys
import platform
#import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore


from player import Player
from playlist import PlayListView, PlayListModel



class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()

        self.player = Player()
        self.playlistmodel = PlayListModel()
        
        self.initUI()
        self.connect()
        
        self.count_closecalled = 0 # for cmd+Q call twice the closeEvent (probably Qt Bug)

    def initUI(self):
        
        self.setWindowTitle('Kelp')
        self.resize(1000, 500)
        self.setMinimumSize(600, 300) 
        
        # display
        text = 'Player Stopped\n'
        text += 'Host API: %s' % self.player.host['name']
        self.label_state = QtWidgets.QLabel(text, self)

        # Device list
        self.combo_device = QtWidgets.QComboBox(self)
        self.combo_device.setMinimumSize(80, 30)
        self.refresh_device_combo()
        
        # play/pause button
        self.btn_play = QtWidgets.QPushButton('Play', self)
        self.btn_play.setMinimumSize(80, 30)

        # slider
        self.slider_pos = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.step_slider = 5000
        self.slider_pos.setMaximum(self.step_slider)
        self.slider_pos.setEnabled(False)
        
        
        # time display
        self.label_pos = QtWidgets.QLabel('0:00/0:00', self)
        self.label_pos.setMinimumSize(80, 30)
        self.label_pos.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(500) # milisecond
        self.timer.timeout.connect(self.update_timedisplay)

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
        #   row4: export button

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
        
        # double clock the playlist item
        self.playlistview.doubleClicked.connect(self.play)

        # set device
        self.combo_device.activated.connect(self.set_device)
        
        # set position
        self.slider_pos.sliderMoved.connect(self.indicate_position)
        self.slider_pos.sliderPressed.connect(self.indicate_position)
        self.slider_pos.sliderReleased.connect(self.set_position)
        

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
                self.playlistmodel.save_csv(PlayListModel.savefile)
                
            else:
                return False # continue to default handling
            return True
        return False # continue to default handling
            
        
    def play(self):
        self.label_pos.setText('0:00/0:00')
        self.slider_pos.setValue(0)
        self.playlistmodel.clear_playmark()
        
        indexes_sel = self.playlistview.selectedIndexes()
        if indexes_sel:
            #row = indexes_sel[0].row()
            rows_sel = {index.row() for index in indexes_sel}
            row = sorted(list(rows_sel))[0]
        else:
            row = 0

        data = self.playlistmodel.get_data(row)
        fname = data[1]

        print('play: row', row, ',', fname)
        
        try:
            state = self.player.set_file(fname)
        except Exception as e:
            print(e, file=sys.stderr)
            self.label_state.setText('Player Stopped\n%s' % e)
            return

        self.label_state.setText('Source: %s\nFIR:' % fname)
        try:
            state = self.player.play()
        except Exception as e:
            print(e, file=sys.stderr)
            self.label_state.setText('Player Stopped\n%s' % e)
            
        if state == Player.playing:
            self.btn_play.setText('Pause')
            self.playlistmodel.set_playmark(row)
            #self.playlistview.

            # for time display
            self.timer.start()
            self.fs = self.player.fs
            self.nframes = self.player.nframes
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
            
    
    def refresh_device_combo(self):
        # re-instantiate pyaudio
        self.player.reboot()
        
        # get new avalable device list
        avalable_devices = self.player.get_output_device_list()
        avalable_device_names = [dev['name'] for dev in avalable_devices]

        # update combo box
        self.combo_device.clear()
        self.combo_device.addItems(avalable_device_names)
        
        # set default device
        default = self.player.get_default_output_device()
        self.player.device = default
        index_current = self.combo_device.findText(default['name'])
        self.combo_device.setCurrentIndex(index_current)

        
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
        self.combo_device.setCurrentIndex(index_designated)
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
        
        # if remove playing item, stop playing
        rows = list({index.row() for index in indexes_sel})
        for row in rows:
            d = self.playlistmodel.get_data(row)
            if d[0] == PlayListModel.playmark:
                self.stop()

        # remove
        self.playlistmodel.remove_selected(indexes_sel)


    def closeEvent(self, event):
        if self.count_closecalled == 0: # for cmd+Q call twice the closeEvent (probably Qt Bug)
            self.playlistmodel.save_csv(PlayListModel.savefile)
        self.count_closecalled += 1
        event.accept()


vvvvv = '''
 ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ><>
    Kelp -- FIR Convolution Player
    penrin(github.com/penrin/Kelp)
<>< ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

Python %s
NumPy %s
PyQt5 %s
''' % (platform.python_version(), ' . . ', QtCore.PYQT_VERSION_STR)

if __name__ == '__main__':
    print(vvvvv)
    
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
    



