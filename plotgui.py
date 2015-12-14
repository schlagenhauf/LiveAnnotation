#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Update a simple plot as rapidly as possible to measure speed.
"""

from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
import pyqtgraph as pg
from pyqtgraph.ptime import time
import sys

"""
import plot as plotui

class PlotApp(QtGui.QMainWindow, plotui.Ui_MainWindow):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)

        self.cameraWindow = QtGui.QWidget()
        self.cameraWindow.setGeometry(QtCore.QRect(530, 20, 256, 192))
        self.cameraWindow.setObjectName("plotWindow")

        self.wId = self.graphicsView.winId()

        self.btnStart.clicked.connect(self.OnStart)
        self.btnStop.clicked.connect(self.OnStop)
        self.btnQuit.clicked.connect(self.OnQuit)

    def OnStart(self, widget):
        self.camera.startPrev()

    def OnStop(self, widget):
        self.camera.pausePrev()

    def OnQuit(self, widget):
        sys.exit(1)
"""



# create plot window
app = QtGui.QApplication([])
p = pg.plot()
p.setWindowTitle('GR Data Plot')
p.setRange(QtCore.QRectF(0, -10, 300, 20))
curve = p.plot()


# create plotting data
data = []
cursor = 0


# define update callback
def update():
    global cursor, curve, p, data

    # get line from pipe
    line = sys.stdin.readline()
    if line:
        # read space separated floats
        nums = [float(i) for i in line.split(' ')[1:]]
        data.append(nums[0])
        while len(data) > 300:
            data.pop(0)
        cursor += 1

    curve.setData(np.array(data))

    app.processEvents()  ## force complete redraw for every plot

# register update callback with timer
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(0)


# execute QT app
#form = PlotApp()
#form.show()
app.exec_()
