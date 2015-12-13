#!/usr/bin/env python

import sys
import pickle
import inspect
import time
from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import pyqtSlot, pyqtSignal
from pyqtgraph.parametertree import Parameter
import pyqtgraph as pg

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, GstVideo, GdkX11
GObject.threads_init()
Gst.init(None)

import numpy as np

import dataparser as dp


# Gui to Annotator:
#   labeling changes
#   config
#   saving of labels
#   new label keys
#   key presses
# Annotator to Gui:
#   Sensor data
#   Labels

### TODOS ###
# - stop label when corresponding shortcut is deleted
# - fix performance issue
# - enable configuration
# - add status string under video / plotter
# - get video with compression to work
# - "null pointer passed" error at shutdown

# Application GUI

main_form = uic.loadUiType("la.ui")[0]
dialog_form = uic.loadUiType("ad.ui")[0]


# Interface for all modules that have adjustable values
class Configurable():
    # Set default values

    def configure(self):
        pass

    # Set values from the config module
    def configure(self, config):
        pass


# Top level class for main window and module instances
class LiveAnnotation(QtGui.QMainWindow, main_form):

    def __init__(self, args, parent=None):
        QtGui.QMainWindow.__init__(self, parent)
        self.setupUi(self)

        # create all modules
        self.plotter = GraphicsLayoutWidget(self.graphicsLayoutView)

        dp.start(1000 / 50)
        dp.connect(self.plotter.dataSlot)


# Plottable label container
class Label:

    def __init__(self, name='other', startIdx=0, endIdx=-1):
        self.name = name
        self.startIdx = startIdx
        self.endIdx = endIdx

    def __str__(self):
        return str((self.name, self.startIdx, self.endIdx))


class PlotLabel(Label):

    def __init__(self, name='other', startIdx=0, endIdx=-1):
        Label.__init__(self, name, startIdx, endIdx)
        self.linReg = []


# Widget managing plotting
class GraphicsLayoutWidget(Configurable):
    def __init__(self, widget):  # create plot window self.w = widget
        print "bla_ctor"
        self.plots = []
        self.w = widget

        self.yLabels = []  # names of each sensor dimension
        self.annotations = []  # list of plotlabel containers
        # a matrix containing data for each dimension per row
        self.data = np.zeros((0, 0))

        self.statusLabel = self.w.parent().findChild(QtGui.QLabel, "labelPlotStatus")

        # config
        self.xLimit = 300
        self.rate = 50

        self.lastTime = time.time()
        self.deltaTime = 0

    def update(self):
        numSamples = self.data.shape[1]

        self.__updateNumberOfPlots()

        for i, pl in enumerate(self.plots):
            pl.listDataItems()[0].setData(self.data[i, :])
            if self.xLimit < numSamples:
                pl.setXRange(numSamples - self.xLimit, numSamples)


        self.__updateClassLabels()

        app.processEvents()  # force complete redraw for every plot

        # calculate delta t
        thisTime = time.time()
        newDeltaTime = thisTime - self.lastTime
        meanDeltaTime = (self.deltaTime + newDeltaTime) / 2
        self.deltaTime = newDeltaTime
        self.lastTime = thisTime
        self.statusLabel.setText("Cycle Time: {:.2f} ms / {:.2f} Hz".format(meanDeltaTime * 1000, 1 / meanDeltaTime))


    def configure(self, config):
        self.xLimit = config.getConfigValue('XLimit')
        self.rate = config.getConfigValue('Data Sample Rate')

    def quit(self):
        for p in self.plots:
            self.w.removeItem(p)

    # creates new linearRegion objects if necessary and deletes outdated ones
    def __updateClassLabels(self):
        for cl in self.annotations:
            if not cl.linReg:
                for pl in self.plots:
                    linReg = pg.LinearRegionItem([cl.startIdx, cl.endIdx])
                    linReg.setZValue(-10)
                    pl.addItem(linReg)
                    cl.linReg.append(linReg)

            # update bounds if necessary
            if [cl.startIdx, cl.endIdx] != cl.linReg[0].getRegion():
                endIdx = self.data.shape[1] if cl.endIdx == -1 else cl.endIdx
                for lr in cl.linReg:
                    lr.setRegion([cl.startIdx, endIdx])

        self.__setStatusLabel()

    def __setStatusLabel(self):
        numSamples = self.data.shape[1]
        visibleSamples = self.xLimit if numSamples > self.xLimit else numSamples
        #self.statusLabel.setText('Samples: ' + str(numSamples) + ' [' + str(visibleSamples) + ' visible]')

    def setYLabels(self, labels):
        self.labels = labels
        self.__updateYLabels()

    # slot for appending new data
    @pyqtSlot(tuple)
    def dataSlot(self, data):
        ndata = np.array(data[1], ndmin=2).T

        # check if length of data vector has changed, and pad with zeros if
        # necessary
        if ndata.shape[0] > self.data.shape[0]:
            self.data = np.vstack((self.data, np.zeros(
                (ndata.shape[0] - self.data.shape[0], self.data.shape[1]))))
        elif ndata.shape[0] < self.data.shape[0]:
            ndata = np.vstack(
                (ndata, np.zeros((self.data.shape[0] - ndata.shape[0], 1))))

        # append
        self.data = np.hstack((self.data, ndata))

        self.update()

    # slot for reacting to newly annotated labels
    @pyqtSlot(tuple)
    def onShortcutEnable(self, data):
        numSamples = self.data.shape[1]

        # trigger corresponding label
        if numSamples == 0:
            print 'Error: No sensor data!'
            return

        # start a new label area or end a started one
        if data[1]:  # label start
            # create new label that is open to the right
            self.annotations.append(PlotLabel(data[0], numSamples, -1))

        else:  # label end
            # find start of label
            for l in reversed(self.annotations):
                if l.name == data[0]:  # if same label type
                    l.endIdx = numSamples
                    break

            else:
                print "Error: ending label failed, no corresponding start"

        print "Plotter: Num Annotations: " + str(len(self.annotations)) + ", Num Plots: " + str(len(self.plots))
        for pl in self.plots:
            print "\tNumber of plot elements: " + str(len(pl.items))
            #print inspect.getmembers(pl.listDataItems()[0])



    def __updateYLabels(self):
        # assign y axis labels (if more/less labels are given, list is
        # truncated accordingly)
        for p, l in zip(self.plots, self.yLabels):
            p.setLabel('left', l)

    def __updateNumberOfPlots(self):
        numDims = self.data.shape[0]
        while len(self.plots) < numDims:
            self.plots.append(self.w.addPlot())
            self.plots[-1].plot()
            self.plots[-1].showGrid(True, True)
            self.w.nextRow()

        self.__updateYLabels()



if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    l = LiveAnnotation(sys.argv)
    l.show()
    retVal = app.exec_()
    sys.exit(retVal)
