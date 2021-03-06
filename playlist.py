import os
import glob
import csv
import copy
from PyQt5 import QtWidgets, QtGui, QtCore
import numpy as np


class PlayListModel(QtCore.QAbstractTableModel):
    
    reordered = QtCore.pyqtSignal()
    selectedItemMoved = QtCore.pyqtSignal(list, list)
    playingItemReplaced = QtCore.pyqtSignal()
    playingItemRemoved = QtCore.pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)

        self.playmark = '>'
        self.errormark = 'x'
        self.header = ['', 'Source', 'FIR', 'SG', 'FG', 'Peak']
        self.display_keys = [
                'playmark',
                'disp_src',
                'disp_fir',
                'gain_src_db',
                'gain_fir_db',
                'peak_db'
                ]
        
        self.savefile = os.path.dirname(__file__) + '/playlist.csv'
        self.save_keys = [
                'path2src',
                'path2fir',
                'gain_src_db',
                'gain_fir_db',
                'peak_db'
                ]
        
        self.data = self.import_csv(self.savefile)
        if not self.data:
            self.data = [] 

    
    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.data)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.header)

    def data(self, index, role):

        if role == QtCore.Qt.DisplayRole:
            row, col = index.row(), index.column()
            
            if col > 2: # 2 is self.header.index('SG') - 1
                val = self.data[row][self.display_keys[col]]
                if val != '':
                    val = '%.1f' % val
                return val
            return self.data[row][self.display_keys[col]]

        #if role == QtCore.Qt.TextAlignmentRole and index.column() > 2:
        #    return QtCore.Qt.AlignRight


        # peak over 0 dBFS -> Red & Italic
        if role == QtCore.Qt.ForegroundRole and index.column() == 5:
            peak_db = self.data[index.row()][self.display_keys[5]]
            if peak_db > 0:
                return QtGui.QColor('red')
        elif role == QtCore.Qt.FontRole and index.column() == 5:
            peak_db = self.data[index.row()][self.display_keys[5]]
            if peak_db > 0:
                font = QtGui.QFont()
                font.setItalic(True)
                return font
        

    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            # The QTableView wants a header text
            if orientation == QtCore.Qt.Horizontal:
                # BE CAREFUL about IndexError
                return self.header[section]
            else:
                return '' # There is no vertical header

    def flags(self, index):
        flags = QtCore.Qt.NoItemFlags
        flags |= QtCore.Qt.ItemIsEnabled
        flags |= QtCore.Qt.ItemIsSelectable
        #flags |= QtCore.Qt.ItemIsEditable
        flags |= QtCore.Qt.ItemIsDragEnabled
        
        #if index.column() in [3, 4]: # gain_src and gain_fir
        #    flags |= QtCore.Qt.ItemIsEditable

        if not index.isValid(): # if not children
            flags |= QtCore.Qt.ItemIsDropEnabled
        return flags
    
    def supportedDropActions(self):
        return QtCore.Qt.CopyAction | QtCore.Qt.MoveAction
    
    def insertRows(self, row, count, index=QtCore.QModelIndex()):
        print('insertRows called') # do nothing
        return True
    
    def removeRows(self, row, count, index=QtCore.QModelIndex()):
        print('removeRows called') # do nothing
        return True

    def reorder_selected(self, mimedata, row_target):
        self.reordered.emit()
        if row_target == -1:
            row_target = self.rowCount()
            
        # decode mime data
        mimetype = 'application/x-qabstractitemmodeldatalist'
        if not mimetype in mimedata.formats():
            return
        encoded = mimedata.data(mimetype)
        data = []
        item = {}
        stream = QtCore.QDataStream(encoded)
        while not stream.atEnd():
            row = stream.readInt32()
            col = stream.readInt32()
            map_items = stream.readInt32()
            for i in range(map_items):
                key = stream.readInt32()
                value = QtCore.QVariant()
                stream >> value
                item[QtCore.Qt.ItemDataRole(key)] = value
            data.append([row, col, item])
        
        # reorder
        rows_sel = list({d[0] for d in data})
        print('reorder', rows_sel, 'at', row_target)
        
        data_sel = []
        for row in sorted(rows_sel, reverse=True):
            data_sel.append(self.data.pop(row))
            if row < row_target:
                row_target -= 1
        self.data[:row_target] += reversed(data_sel)
        
        # re-select moved items
        first = row_target
        last = row_target + len(data_sel)
        rows_reselect = [i for i in range(first, last)]
        self.selectedItemMoved.emit(rows_reselect, [])
        return

    def dropMimeData(self, data, action, row, col, parent):
        if action == QtCore.Qt.MoveAction:
            # move action
            self.reorder_selected(data, row)
            return True

        return super().dropMimeData(data, action, row, col, parent)

    def get_data(self, row):
        return self.data[row]
 
    def set_playmark(self, row):
        if 0 <= row and row < self.rowCount():
            self.data[row]['playmark'] = self.playmark
            index = self.index(row, 0)
            self.dataChanged.emit(index, index)

    def set_errormark(self, row):
        if 0 <= row and row < self.rowCount():
            self.data[row]['playmark'] = self.errormark
            index = self.index(row, 0)
            self.dataChanged.emit(index, index)
        
        
    def clear_playmark(self):
        for i in range(self.rowCount()):
            if self.data[i]['playmark'] == self.playmark:
                self.data[i]['playmark'] = ''
                index = self.index(i, 0)
                self.dataChanged.emit(index, index)

    def get_row_playing(self):
        for row in range(self.rowCount()):
            if self.data[row]['playmark'] == self.playmark:
                return row
        return -1

    def save_csv(self, fname):
        try:        
            with open(fname, 'w') as f:
                writer = csv.writer(f, delimiter=',')
                writer.writerow(self.save_keys)
                for d in self.data:
                    d_save = [d[key] for key in self.save_keys]
                    writer.writerow(d_save)
                print('save:', fname)
        except Exception as e:
            print('save_csv:', e)
            
    
    def import_csv(self, fname):
        try:
            with open(fname, 'r') as f:
                reader = csv.reader(f, delimiter=',')
                csv_data = [row for row in reader]

                key_list = []
                for d in csv_data[0]:
                    key_list.append(d.strip(' '))

                data_imported = []
                for csv_d in csv_data[1:]:
                    d = {}
                    for col, key in enumerate(key_list):
                        d[key] = csv_d[col]

                    if d['gain_src_db'] == '':
                        d['gain_src'] = ''
                    else:
                        d['gain_src_db'] = float(d['gain_src_db'])
                        d['gain_src'] = 10 ** (d['gain_src_db'] / 20)

                    if d['gain_fir_db'] == '':
                        d['gain_fir'] = ''
                    else:
                        d['gain_fir_db'] = float(d['gain_fir_db'])
                        d['gain_fir'] = 10 ** (d['gain_fir_db'] / 20)

                    d['peak_db'] = float(d['peak_db'])
                    d['peak'] = 10 ** (d['peak_db'] / 20)

                    d['playmark'] = ''
                    d['disp_src'] = self.dispname(d['path2src'])
                    d['disp_fir'] = self.dispname(d['path2fir'])
                    data_imported.append(d)


                print('import_csv:', fname)
                return data_imported
        except Exception as e:
            print('import_csv error:', e)
        
        return []
    
    
    def rollback_savepoint(self):
        new_data = self.import_csv(self.savefile)

        # delete current data
        self.playingItemRemoved.emit()
        index = QtCore.QModelIndex()
        self.beginRemoveRows(index, 0, self.rowCount())
        del self.data[:]
        self.endRemoveRows()
        
        # add new data
        self.insert_data(new_data)
        

    def dispname(self, name):
        # format filename for display
        if name:
            name_split = name.split('/')
            fmtname = ''
            for dirname in name_split[:-1]:
                if dirname:
                    fmtname += '/' + dirname[0]
            fmtname += '/' + name_split[-1]
            return fmtname
        else:
            return ''

    def catch_urls(self, urls, indexes_sel):

        # search recursive
        found = []
        for url in urls:
            if os.path.isfile(url):
                found += [url]
            else:
                if url[-1] != '/':
                    url += '/'
                found += glob.glob(url + '/**', recursive=True)

        # screening
        urls_csv = []
        urls_wav = []
        urls_npy = []
        for url in found:
            if not os.path.isfile(url):
                continue
            _, ext = os.path.splitext(url)
            if ext == '.csv':
                urls_csv.append(url)
            elif ext == '.wav':
                urls_wav.append(url)
            elif ext == '.npy':
                urls_npy.append(url)
        
        
        # read csv priority and return
        if urls_csv:
            for url in urls_csv:
                new_data = self.import_csv(url)
                self.insert_data(new_data)
        
        # replace if there are selections and
        # only one file (wav or npy) is dropped
        elif indexes_sel and len(urls_wav) + len(urls_npy) == 1:
            ret = self._replace(urls_wav, urls_npy, indexes_sel)
            if ret:
                self.reset_peak(indexes_sel)
        
        # add all combination if no selection
        else:
            self._add_all_combinations(urls_wav, urls_npy) 
        return


    def _replace(self, urls_wav, urls_npy, indexes_sel):
        
        # ignore if multiple files are dropped
        if len(urls_wav) + len(urls_npy) != 1:
            return False

        rows_sel = list({index.row() for index in indexes_sel})
        if urls_wav:
            for row in rows_sel:
                self.data[row]['path2src'] = urls_wav[0]
                self.data[row]['disp_src'] = self.dispname(urls_wav[0])
                self.data[row]['gain_src'] = 1
                self.data[row]['gain_src_db'] = 0
        elif urls_npy:
            for row in rows_sel:
                self.data[row]['path2fir'] = urls_npy[0]
                self.data[row]['disp_fir'] = self.dispname(urls_npy[0])
                self.data[row]['gain_fir'] = 1
                self.data[row]['gain_fir_db'] = 0
        
        # detect playing item replacement and emit signal
        # (Then the slot side shoud stop playing)
        for row in rows_sel:
            if self.data[row]['playmark'] == self.playmark:
                self.playingItemReplaced.emit()
                print('replace the item being playing')
        
        # update view
        if urls_wav:
            col = self.display_keys.index('disp_src')
        if urls_npy:
            col = self.display_keys.index('disp_fir')

        topLeft = self.index(min(rows_sel), col)
        bottomRight = self.index(max(rows_sel), 5)
        self.dataChanged.emit(topLeft, bottomRight)
        return True


    def _add_all_combinations(self, urls_wav, urls_npy):
        new_data = []
        if len(urls_wav) > 0 and len(urls_npy) == 0:
            for url in urls_wav:
                d = {
                    'playmark': '',
                    'path2src': url,
                    'disp_src': self.dispname(url),
                    'gain_src': 1,
                    'gain_src_db': 0,
                    'path2fir': '',
                    'disp_fir': '',
                    'gain_fir': '',
                    'gain_fir_db': '',
                    'peak': 0,
                    'peak_db': -np.inf
                    }
                new_data.append(d)

        elif len(urls_wav) == 0 and len(urls_npy) > 0:
            for url in urls_npy:
                d = {
                    'playmark': '',
                    'path2src': '',
                    'disp_src': '',
                    'gain_src': '',
                    'gain_src_db': '',
                    'path2fir': url,
                    'disp_fir': self.dispname(url),
                    'gain_fir': 1,
                    'gain_fir_db': 0,
                    'peak': 0,
                    'peak_db': -np.inf
                    }
                new_data.append(d)

        elif len(urls_wav) > 0 and len(urls_npy) > 0:
            for url_wav in urls_wav:
                for url_npy in urls_npy:
                    d = {
                        'playmark': '',
                        'path2src': url_wav,
                        'disp_src': self.dispname(url_wav),
                        'gain_src': 1,
                        'gain_src_db': 0,
                        'path2fir': url_npy,
                        'disp_fir': self.dispname(url_npy),
                        'gain_fir': 1,
                        'gain_fir_db': 0,
                        'peak': 0,
                        'peak_db': -np.inf
                        }
                    new_data.append(d)
        self.insert_data(new_data)
        return


    def insert_data(self, new_data, row=-1, index=QtCore.QModelIndex()):
        if len(new_data) == 0:
            return True
        if row < 0:
            row = self.rowCount()
        count = len(new_data)
        first, last = row, row + count - 1
        self.beginInsertRows(index, first, last)
        self.data[:row] += new_data
        self.endInsertRows()
        self.reordered.emit()        
        return True
    
    def remove_data(self, row, index=QtCore.QModelIndex()):
        if self.data[row]['playmark'] == self.playmark:
            self.playingItemRemoved.emit()
        print('remove_row:', row)
        self.beginRemoveRows(index, row, row)
        del self.data[row]
        self.endRemoveRows()
        return True

    def clear_fir(self, rows):
        for row in rows:
            self.data[row]['path2fir'] = ''
            self.data[row]['disp_fir'] = ''
            self.data[row]['gain_fir'] = ''
            self.data[row]['gain_fir_db'] = ''
            self.data[row]['peak'] = 0
            self.data[row]['peak_db'] = -np.inf
            if self.data[row]['playmark'] == self.playmark:
                self.playingItemReplaced.emit()
        topLeft = self.index(min(rows), 2)
        bottomRight = self.index(max(rows), 5)
        self.dataChanged.emit(topLeft, bottomRight)

    def remove_selected(self, indexes_sel):
        # remove FIRs if selected items have both source and FIR.
        # remove rows if selected items have either source or FIR.
        rows_sel = list({index.row() for index in indexes_sel})
        
        # rows which have FIR
        rows_own_fir = [r for r in rows_sel if self.data[r]['path2fir'] != '']

        # selected items have FIR
        if rows_own_fir:
            self.clear_fir(rows_own_fir)            
            for row in sorted(rows_own_fir, reverse=True):
                if self.data[row]['path2src'] == '':
                    self.remove_data(row)

        # selected items have no FIR
        else:
            for row in sorted(rows_sel, reverse=True):
                self.remove_data(row)
    
    def sort(self, col, order):
        '''
        if col == 0:
            self.reordered.emit() # hide indicator
            return
        '''
        key = self.display_keys[col]
        descend = (order == QtCore.Qt.DescendingOrder)
        #self.data.sort(key=lambda x: x[key], reverse=descending)
        
        key = self.display_keys[col]
        arr = [self.data[i][key] for i in range(self.rowCount())]
        arr_sorted = sorted(enumerate(arr), key=lambda x:x[1], reverse=descend)
        index_sort = [i[0] for i in arr_sorted]
        self.data = [self.data[i] for i in index_sort]

        topLeft = self.index(0, 0)
        bottomRight = self.index(self.rowCount(), self.columnCount())
        self.dataChanged.emit(topLeft, bottomRight)
        
        if descend:
            print('sort: %s, descending' % key)
        else:
            print('sort: %s, ascending' % key)
        
        self.selectedItemMoved.emit([], index_sort)
        
    def reset_peak(self, indexes_sel):
        for index in indexes_sel:
            row, col = index.row(), index.column()
            if col != 5:
                continue
            self.data[row]['peak'] = 0
            self.data[row]['peak_db'] = -np.inf
            self.dataChanged.emit(index, index)
    
    def toggle_gain_01(self, index):
        row, col = index.row(), index.column()
        
        key_db = self.display_keys[col]
        if key_db == 'gain_src_db':
            key_lin = 'gain_src'
        else:
            key_lin = 'gain_fir'

        gain_db = self.data[row][key_db]
        if gain_db != '':
            if gain_db == -np.inf:
                self.data[row][key_lin] = 1.
                self.data[row][key_db] = 0.
                self.dataChanged.emit(index, index)
                return

            elif gain_db == 0:
                self.data[row][key_lin] = 0.
                self.data[row][key_db] = -np.inf
                self.data[row]['peak'] = 0.
                self.data[row]['peak_db'] = -np.inf
            else:
                self.data[row][key_lin] = 1.
                self.data[row][key_db] = 0.
                self.data[row]['peak_db'] -= gain_db
                self.data[row]['peak'] = 10 ** (self.data[row]['peak_db'] / 20)
                
            self.dataChanged.emit(index, index)
            index_peak = self.index(row, 5)
            self.dataChanged.emit(index_peak, index_peak)

        

    def adjust_gain(self, step, index, indexes_sel):

        # adjust target
        row_point = index.row()
        rows_sel = list({idx.row() for idx in indexes_sel})

        if row_point in rows_sel:
            rows_target = rows_sel
        else:
            rows_target = [row_point]

        col_target = index.column()
        
        # key
        key_db = self.display_keys[col_target]
        if key_db == 'gain_src_db':
            key_lin = 'gain_src'
        else:
            key_lin = 'gain_fir'
        
        # adjust
        for row in rows_target:
            gain_db = self.data[row][key_db]
            if gain_db == '':
                return

            if gain_db == -np.inf and step > 0:
                self.data[row][key_db] = -80.
                self.data[row][key_lin] = 10 ** (self.data[row][key_db] / 20)
                #self.data[row]['peak'] = 0
                #self.data[row]['peak_db'] = -np.inf
            else:
                self.data[row][key_db] += step
                self.data[row][key_lin] = 10 ** (self.data[row][key_db] / 20)
                self.data[row]['peak_db'] += step
                self.data[row]['peak'] = 10 ** (self.data[row]['peak_db'] / 20)

            # update view
            topLeft = self.index(row, col_target)
            bottomRight = self.index(row, 5)
            self.dataChanged.emit(topLeft, bottomRight)




    
class DrawLineStyle(QtWidgets.QProxyStyle):

    def drawPrimitive(self, element, option, painter, widget=None):
        """
        Draw a line across the entire row rather than just the column
        we're hovering over.  This may not always work depending on global
        style - for instance I think it won't work on OSX.
        """
        if element == self.PE_IndicatorItemViewItemDrop and not option.rect.isNull():
            option_new = QtWidgets.QStyleOption(option)
            option_new.rect.setLeft(0)
            if widget:
                option_new.rect.setRight(widget.width())
            option = option_new
        super().drawPrimitive(element, option, painter, widget)


class CustomDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, tableview):
        super(CustomDelegate, self).__init__()
        
        self.grid_pen = QtGui.QPen(
                QtGui.QColor('silver'), 0, tableview.gridStyle()
                )


    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        if index.column() == 2:
            old_pen = painter.pen()
            painter.setPen(self.grid_pen)
            painter.drawLine(option.rect.topRight(), option.rect.bottomRight())
            painter.setPen(old_pen)


class PlayListView(QtWidgets.QTableView):

    start_playing = QtCore.pyqtSignal(int)

    def __init__(self, playlistmodel, parent=None):
        super().__init__(parent)
        
        # set model
        self.setModel(playlistmodel)
        self.playlistmodel = playlistmodel
        
        # appearance
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)

        hh = self.horizontalHeader()
        hh.setMinimumSectionSize(15)
        hh.resizeSection(0, 24)
        hh.resizeSection(1, 300)
        hh.resizeSection(2, 300)
        hh.resizeSection(3, 48)
        hh.resizeSection(4, 48)
        hh.resizeSection(4, 40)
        hh.setStretchLastSection(True)
        hh.setDefaultAlignment(QtCore.Qt.AlignLeft)
        self.verticalHeader().setDefaultSectionSize(21) # default row height
        

        # selection
        self.setSelectionBehavior(self.SelectRows)
        self.setSelectionMode(self.ExtendedSelection)

        # drag and drop to reorder row items
        self.setDragDropMode(self.InternalMove)
        self.setDragDropOverwriteMode(False)

        # draw line across the entire row
        self.setStyle(DrawLineStyle())

        # draw grid between FIR and SG
        self.setShowGrid(False)
        self.setItemDelegate(CustomDelegate(self))

        # sort
        self.setSortingEnabled(True)
        hh.setSortIndicator(-1, QtCore.Qt.AscendingOrder)
        self.playlistmodel.reordered.connect(self.hideSortIndicator)
        self.playlistmodel.selectedItemMoved.connect(self.move_selection)
        
        # double clicked
        self.doubleClicked.connect(self.double_click_action)

        # mouse wheel for gain adjust
        self.wheel_angle = 0
    
    
    def dragEnterEvent(self, event):
        print('dragEnterEvent')
        data = event.mimeData()
        if data.hasUrls():
            event.acceptProposedAction()
        elif 'application/x-qabstractitemmodeldatalist' in data.formats():
            event.acceptProposedAction()
        else:
            event.ignore()
        
    def dropEvent(self, event):
        print('dropEvent')

        data = event.mimeData()
        if data.hasUrls():
            urls = [url.path() for url in event.mimeData().urls()]
            
            indexes_sel = self.selectedIndexes()
            self.playlistmodel.catch_urls(urls, indexes_sel)
            event.accept()
            
        elif 'application/x-qabstractitemmodeldatalist' in data.formats():
            self.clearSelection()
            
        return super().dropEvent(event)


    def wheelEvent(self, event):
        
        # gain adjustment
        index = self.indexAt(event.pos())
        if (index.column() in [3, 4]) and index.row() >= 0:
            #self.wheel_angle += event.pixelDelta().y()
            self.wheel_angle += event.angleDelta().y()
            step, self.wheel_angle = divmod(self.wheel_angle, 120)
            if step != 0:
                if event.modifiers() == QtCore.Qt.ControlModifier:
                    step *= 0.1 # fine step
                indexes_sel = self.selectedIndexes()
                self.playlistmodel.adjust_gain(step, index, indexes_sel)
                event.accept()
            return
        
        return super().wheelEvent(event)
    

    def hideSortIndicator(self):
        self.horizontalHeader().setSortIndicator(-1, QtCore.Qt.AscendingOrder)
        print('hideSortIndicator')
        
    def move_selection(self, rows_sel=[], index_sort=[]):
        if index_sort:
            rows_sel_old = {index.row() for index in self.selectedIndexes()}
            rows_sel = [index_sort.index(i) for i in list(rows_sel_old)]
        if rows_sel:
            self.clearSelection()
            
            # select indexes
            '''
            for row in rows_sel:
                self.selectRow(row)
            '''
            indexes = []
            num_col = self.playlistmodel.columnCount()
            for row in rows_sel:
                for col in range(num_col):
                    indexes.append(self.playlistmodel.index(row, col))
            
            flag = QtCore.QItemSelectionModel.Select
            for index in indexes:
                self.selectionModel().select(index, flag)
            
            print('set_selected:', rows_sel)


    def double_click_action(self, index):
        col = index.column()
        
        if col <= 2:
            self.start_playing.emit(index.row())

        # source gain
        elif col == 3:
            self.playlistmodel.toggle_gain_01(index)
        
        # FIR gain
        elif col == 4:
            self.playlistmodel.toggle_gain_01(index)
        
        # reset peak
        elif col == 5:
            self.playlistmodel.reset_peak([index])


