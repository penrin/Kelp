import os
import csv
from PyQt5 import QtWidgets, QtGui, QtCore

class PlayListModel(QtCore.QAbstractTableModel):
    
    savefile = os.path.dirname(__file__) + '/playlist.csv'
    playmark = '>'

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.header = ['', 'Source', 'FIR', 'SG', 'FG', 'Peak']
        self.data = self.import_csv(PlayListModel.savefile)
        
        if not self.data:
            self.data = self.import_csv('playlist_test.csv') # <-- delete in the future

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.data)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.header)

    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole:
            row, col = index.row(), index.column()
            return self.data[row][col]

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
        if not index.isValid(): # if not children
            flags |= QtCore.Qt.ItemIsDropEnabled
        return flags
    
    def supportedDropActions(self):
        return QtCore.Qt.CopyAction | QtCore.Qt.MoveAction

    def setData(self, index, value, role):
        if (role == QtCore.Qt.EditRole) or (role == QtCore.Qt.DisplayRole):
            row, col = index.row(), index.column()
            self.data[row][col] = str(value)
            #self.dataChanged.emit(index, index)
            return True
        return False
        
    def insertRows(self, row, count, index=QtCore.QModelIndex()):
        print('insert', row, count)
        first, last = row, row + count - 1
        self.beginInsertRows(index, first, last)
        empty = ['', '', '', '', '', '']
        new = [empty for _ in range(count)]
        self.data[:row] += new
        self.endInsertRows()
        return True
        
    def removeRows(self, row, count, index=QtCore.QModelIndex()):
        print('remove', row, count)
        first, last = row, row + count - 1
        self.beginRemoveRows(index, first, last)
        del self.data[row:row+count]
        self.endRemoveRows()
        return True
    
    def dropMimeData(self, data, action, row, col, parent):
        if row == -1:
            row = self.rowCount()
        # Always move the entire row, and avoid column "shifting"
        return super().dropMimeData(data, action, row, 0, parent)

    def get_data(self, row):
        return self.data[row]

    def remove_selected(self, indexes_sel):
        rows_sel = list({index.row() for index in indexes_sel})
        for row in sorted(rows_sel, reverse=True):
            self.removeRows(row, 1)
            
    def set_playmark(self, row):
        if 0 <= row and row < self.rowCount():
            self.data[row][0] = PlayListModel.playmark
            index = self.createIndex(row, 0)
            self.dataChanged.emit(index, index)
        
    def clear_playmark(self):
        for i in range(self.rowCount()):
            if self.data[i][0] == PlayListModel.playmark:
                self.data[i][0] = ''
                index = self.createIndex(i, 0)
                self.dataChanged.emit(index, index)

    def save_csv(self, fname):
        try:        
            with open(fname, 'w') as f:
                writer = csv.writer(f, delimiter=',')
                writer.writerow(self.header)
                for d in self.data:
                    writer.writerow(d)
                print('save:', fname)
        except Exception as e:
            print('save_csv:', e)
    
    def import_csv(self, fname):
        try:
            with open(fname, 'r') as f:
                reader = csv.reader(f, delimiter=',')
                data = [row for row in reader]

                L = len(data[0])
                for d in data[1:]:
                    if len(d) != L:
                        return []
                    d[0] = ''
                    
                if data[0] != self.header:
                    return []
                print('import_csv:', fname)
                return data[1:]
        except Exception as e:
            print('import_csv:', e)
        
        return []

    
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




class PlayListView(QtWidgets.QTableView):

    def __init__(self, playlistmodel, parent=None):
        super().__init__(parent)
        
        # set model
        self.setModel(playlistmodel)
        
        # appearance
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)

        hh = self.horizontalHeader()
        hh.setMinimumSectionSize(15)
        hh.resizeSection(0, 10)
        hh.resizeSection(1, 400)    
        hh.resizeSection(2, 400)    
        hh.resizeSection(3, 40)    
        hh.resizeSection(4, 40)    
        hh.resizeSection(4, 40)    
        hh.setStretchLastSection(True)
        hh.setDefaultAlignment(QtCore.Qt.AlignLeft)
        self.verticalHeader().setDefaultSectionSize(21) # default row height
        

        # selection
        self.setSelectionBehavior(self.SelectRows)

        # drag and drop to reorder row items
        self.setDragDropMode(self.InternalMove)
        self.setDragDropOverwriteMode(False)

        # draw line across the entire row
        self.setStyle(DrawLineStyle())


   
