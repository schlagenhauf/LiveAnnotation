#!/usr/bin/env python

import sys
from PyQt4 import QtCore, QtGui, uic
import pyqtgraph as pg
from pyqtgraph.ptime import time
from pyqtgraph.parametertree import Parameter, ParameterTree, ParameterItem, registerParameterType


import numpy as np

import pygst
pygst.require("0.10")
import gobject
gobject.threads_init()
import gst

form_class = uic.loadUiType("la.ui")[0]


class LiveAnnotatorWin(QtGui.QMainWindow, form_class):
    def __init__(self, args, parent=None):
        QtGui.QMainWindow.__init__(self,parent)
        self.setupUi(self)

        self.vid = VideoWidget(self.videoView.winId())
        self.vid.setSource("videotestsource")
        self.plt = PlotWidget(self.plotView)
        self.plt.setSource(sys.stdin)

        # connect elements
        self.btnPlay.clicked.connect(self.vid.play)
        self.btnPause.clicked.connect(self.vid.pause)
        self.btnAddKey.clicked.connect(self.onAddKey)


        # dictionary for key bindings
        self.keys = {}


    def addKey(self, key, cls):
        self.keys[key] = cls;


    def onAddKey(self):
        # get key and class from text forms
        key = self.keyEdit.text()
        cls = self.classEdit.text()

        # add it to the dictionary
        self.addKey(key, cls)

        # update the table
        self.updateTable()


    def updateTable(self):
        self.keyTable.clearContents()
        self.keyTable.setRowCount(len(self.keys))

        for kv, i in zip(self.keys.iteritems(), range(len(self.keys))):
            self.keyTable.setItem(i, 0, QtGui.QTableWidgetItem(kv[0]))
            self.keyTable.setItem(i, 1, QtGui.QTableWidgetItem(kv[1]))





class VideoWidget:
    def __init__(self, winId):
        self.winId = winId
        assert self.winId

        self.pipeline = gst.Pipeline("videopl")
        self.source = gst.element_factory_make("videotestsrc", "vsource")
        #self.source = gst.element_factory_make("v4l2src", "vsource")
        self.sink = gst.element_factory_make("autovideosink", "outsink")
        #self.source.set_property("device", "/dev/video0")

        self.pipeline.add(self.source, self.sink)
        gst.element_link_many(self.source, self.sink)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.onMessage)
        bus.connect("sync-message::element", self.onSyncMessage)


    def onMessage(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.player.set_state(gst.STATE_NULL)
        elif t == gst.MESSAGE_ERROR:
           err, debug = message.parse_error()
           print "Error: %s" % err, debug
           self.player.set_state(gst.STATE_NULL)

    def onSyncMessage(self, bus, message):
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            imagesink.set_xwindow_id(self.winId)

    def play(self):
        self.pipeline.set_state(gst.STATE_PLAYING)

    def pause(self):
        self.pipeline.set_state(gst.STATE_NULL)

    def setSource(self, source):
        pass


class ParameterTree:
    def __init__(self):
        pass


class PlotWidget:
    def __init__(self, plotWidget):
        # create plot window
        self.plt = plotWidget
        self.plt.setWindowTitle('GR Data Plot')
        #self.plt.setRange(QtCore.QRectF(0, -10, 300, 20))
        self.curve = self.plt.plot()

        # create plotting data
        self.data = []
        self.cursor = 0

        # create timer to update plot
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(0)



    def update(self):
        # get line from pipe
        line = sys.stdin.readline()
        if line:
            # read space separated floats
            nums = [float(i) for i in line.split(' ')[1:]]
            self.data.append(nums[0])
            while len(self.data) > 300:
                self.data.pop(0)
            self.cursor += 1

            self.curve.setData(np.array(self.data))

            app.processEvents()  ## force complete redraw for every plot


    def setSource(self, source):
        pass




if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    la = LiveAnnotatorWin(sys.argv)
    la.show()
    app.exec_()
