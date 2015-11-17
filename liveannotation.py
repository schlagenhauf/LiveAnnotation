#!/usr/bin/env python

import sys
from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import pyqtSlot, pyqtSignal
from pyqtgraph.parametertree import Parameter
import pyqtgraph as pg

import gst, gobject
gobject.threads_init()

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

########## Application GUI

main_form = uic.loadUiType("la.ui")[0]
dialog_form = uic.loadUiType("ad.ui")[0]


## Top level class for main window and module instances
class LiveAnnotation(QtGui.QMainWindow, main_form):
    ## Constructor
    def __init__(self, args, parent=None):
        QtGui.QMainWindow.__init__(self,parent)
        self.setupUi(self)

        # create all modules
        self.config = ParameterTreeWidget(self.parameterView)
        self.stream = VideoWidget(self.videoView.winId())
        self.plotter = GraphicsLayoutWidget(self.graphicsLayoutView)
        self.annotatorConfig = AnnotationConfigWidget(self.frameKeys)
        self.annotator = Annotator()

        # connect elements
        self.btnPlay.clicked.connect(self.stream.play)
        self.btnPause.clicked.connect(self.stream.pause)

        self.annotator.newLabelSignal.connect(self.plotter.onNewClassLabel)
        self.annotatorConfig.keyPressSignal.connect(self.annotator.onShortcutEnable)

        dp.connect(self.plotter.dataSlot)
        dp.connect(self.annotator.dataSlot)

        # set all config values
        self.updateConfigurables()



    ## Sets all config values again (e.g. after changing the config)
    # only use getConfigValue here, to ensure that all values are updated
    def updateConfigurables(self):
        # video config
        self.stream.updatePipeline(self.config.getConfigValue('Video Source'))


## Plottable label container
class PlotLabel:
  def __init__(self, name = 'other', startIdx = 0, endIdx = -1):
    self.name = name
    self.startIdx = startIdx
    self.endIdx = endIdx
    self.linReg = None

  def __str__(self):
    return str((self.name, self.startIdx, self.endIdx))


## Widget managing plotting
class GraphicsLayoutWidget:
    ## Constructor
    def __init__(self, widget):
        # create plot window
        self.w = widget
        self.plotIt = self.w.addPlot()
        self.plotIt.showGrid(True, True)
        self.plots = []

        self.yLabels = [] # names of each sensor dimension
        self.classLabels = [] # list of plotlabel containers
        self.data = np.zeros((0,0)) # a matrix containing data for each dimension per row

        # config
        self.xLimit = 500


    def update(self):
        if self.xLimit > 0 and self.data.shape[1] > self.xLimit:
            self.plotIt.setXRange(self.data.shape[1] - self.xLimit, self.data.shape[1])
        self.__updateNumberOfPlots()
        for i,pl in enumerate(self.plotIt.listDataItems()):
            pl.setData(self.data[i,:])

        app.processEvents()  ## force complete redraw for every plot

        self.__updateClassLabels()


    ## creates new linearRegion objects if necessary and deletes outdated ones
    def __updateClassLabels(self):
        # update class labeling
        for cl in self.classLabels:
          # TODO: add clipping here
          if not cl.linReg:
            cl.linReg = pg.LinearRegionItem([cl.startIdx, cl.endIdx])
            cl.linReg.setZValue(-10)
            #for pl in self.plots:
            #  pl.addItem(cl.linReg)
            self.plotIt.addItem(cl.linReg)

          # update bounds if necessary
          if [cl.startIdx, cl.endIdx] != cl.linReg.getRegion():
              endIdx = self.data.shape[1] if cl.endIdx == -1 else cl.endIdx
              cl.linReg.setRegion([cl.startIdx, endIdx])



    def setYLabels(self, labels):
        self.labels = labels
        self.__updateYLabels()


    ## slot for appending new data
    @pyqtSlot(tuple)
    def dataSlot(self, data):
        ndata = np.array(data[1], ndmin=2).T

        ## check if length of data vector has changed, and pad with zeros if necessary
        if ndata.shape[0] > self.data.shape[0]:
            self.data = np.vstack((self.data, np.zeros((ndata.shape[0] - self.data.shape[0], self.data.shape[1]))))
        elif ndata.shape[0] < self.data.shape[0]:
            ndata = np.vstack((ndata, np.zeros((self.data.shape[0] - ndata.shape[0], 1))))

        # append
        self.data = np.hstack((self.data, ndata))

        self.update()


    ## slot for reacting to newly annotated labels
    @pyqtSlot(tuple)
    def onNewClassLabel(self, data):
      # start a new label area or end a started one
      if data[1]: # label start
        self.classLabels.append(PlotLabel(data[0], data[2], -1)) # create new label that is open to the right

      else: # label end
        # find start of label
        for l in reversed(self.classLabels):
          if l.name == data[0]: # if same label type
            l.endIdx = data[2]
            break

        else:
          print "Error: ending label failed, no corresponding start"

      for l in self.classLabels:
        print l



    def __updateYLabels(self):
        # assign y axis labels (if more/less labels are given, list is truncated accordingly)
        for p,l in zip(self.plots, self.yLabels):
            p.setLabel('left', l)


    def __updateNumberOfPlots(self):
        numDims = self.data.shape[0]

        for pl in self.plotIt.listDataItems():
            self.plotIt.removeItem(pl)

        self.plots = []

        while len(self.plots) < numDims:
            self.plots.append(self.plotIt.plot())

        self.__updateYLabels()



## Widget managing video stream
class VideoWidget:
    ## Constructor
    def __init__(self, winId):
        assert winId
        self.winId = winId


    def play(self):
        self.pipeline.set_state(gst.STATE_PLAYING)


    def pause(self):
        self.pipeline.set_state(gst.STATE_NULL)


    def startRecording(self, path):
        # enable pipeline output to file
        pass


    def stopRecording(self):
        pass


    def updatePipeline(self, source):
        # create pipeline, source and sink
        self.pipeline = gst.Pipeline("videopl")
        self.source = gst.element_factory_make(source, "vsource")
        self.sink = gst.element_factory_make("autovideosink", "outsink")

        # connect them
        self.pipeline.add(self.source, self.sink)
        gst.element_link_many(self.source, self.sink)

        # intercept all bus messages so we can grab the frame
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.__onMessage)
        bus.connect("sync-message::element", self.__onSyncMessage)


    def __onMessage(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.player.set_state(gst.STATE_NULL)
        elif t == gst.MESSAGE_ERROR:
           err, debug = message.parse_error()
           print "Error: %s" % err, debug
           self.player.set_state(gst.STATE_NULL)

    def __onSyncMessage(self, bus, message):
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            imagesink.set_xwindow_id(self.winId)



## Widget populating and reading configuration
class ParameterTreeWidget:
    ## Constructor
    def __init__(self, parameterView):
        defaultParams = [
            {'name': 'General', 'type': 'group', 'children': [
                {'name': 'Config Path', 'type': 'str', 'value': "config.cfg"},
            ]},
            {'name': 'Video', 'type': 'group', 'children': [
                {'name': 'Video Source', 'type': 'list', 'values': {"Test Source": "videotestsrc", "Webcam": "v4l2src", "network": "udp"}, 'value': "Test Source"},
            ]},
        ]

        self.p = Parameter.create(name='params', type='group', children=defaultParams)


        self.t = parameterView # use the ID of the promoted graphicsView
        self.t.setParameters(self.p, showTop=False)
        self.t.show()


    ## recursively go through the tree and search for a parameter with <key>
    # returns None if no fitting value was found
    def getConfigValue(self, key, tree = None):
        if tree is None:
            tree = self.p

        for ch in tree.children():
            if ch.name() == key:
                return ch.value()
            else:
                cv = self.getConfigValue(key, ch)
                if cv is not None:
                    return cv

        return None


    def save(self):
        self.state = self.p.saveState()

    def restore(self):
        add = self.p['Save/Restore functionality', 'Restore State', 'Add missing items']
        rem = self.p['Save/Restore functionality', 'Restore State', 'Remove extra items']
        self.p.restoreState(self.state, addChildren=add, removeChildren=rem)



# Subwindow to add / modify a new label type
class AddEntryDialog(QtGui.QDialog, dialog_form):
  ## Constructor
  def __init__(self, args, parent):
    QtGui.QDialog.__init__(self,parent)
    self.setupUi(self)
    self.parent = parent

    # connect ok / cancel buttons
    self.buttonBox.accepted.connect(self.__onAccept)
    self.buttonBox.rejected.connect(self.__onReject)


  ## Setter for filling in values when modifying
  def setValues(self, lm):
    self.editName.setText(lm.name)
    self.editKeyMap.setText(lm.key.toString())
    self.radioToggle.setChecked(lm.toggleMode)
    self.radioHold.setChecked(not lm.toggleMode)
    self.editDescription.setText(lm.description)


  ## reads out the forms and returns LabelMeta instance
  def __onAccept(self):
    self.lm = LabelMeta(str(self.editName.text()), QtGui.QKeySequence(self.editKeyMap.text()), str(self.editDescription.toPlainText()), self.radioToggle.isChecked())
    self.accept()


  ## just close the window
  def __onReject(self):
    self.close()



## Class managing the annotation configuration widget
class AnnotationConfigWidget(QtCore.QObject):
#class AnnotationConfigWidget:
    keyPressSignal = pyqtSignal(tuple)

    ## Constructor
    def __init__(self, widget):
        super(AnnotationConfigWidget, self).__init__()
        # get access to all elements in the annotation config qframe
        self.widget = widget
        self.tableWidget = widget.findChild(QtGui.QTableWidget, "keyTable")
        widget.findChild(QtGui.QPushButton, "btnAddKey").clicked.connect(self.__onAddKey)
        widget.findChild(QtGui.QPushButton, "btnModKey").clicked.connect(self.__onModKey)
        widget.findChild(QtGui.QPushButton, "btnDelKey").clicked.connect(self.__onDelKey)

        self.annotatorConfig = {}
        self.syncLists()
        # listen to keypress events and send signals


    ## Sets the displayed configuration by a list of LabelMeta instances
    def setConfig(self, cfg):
        pass


    ## Returns the (modified) configuration as a list of LabelMeta instances
    def getConfig(self):
        pass


    ## Synchronizes the internal list with the displayed table
    def syncLists(self):
        # save sort column and order for sorting afterwards
        sortCol = self.tableWidget.horizontalHeader().sortIndicatorSection()
        sortOrd = self.tableWidget.horizontalHeader().sortIndicatorOrder()

        # clear table and reinsert all items
        self.tableWidget.clearContents()
        self.tableWidget.setRowCount(len(self.annotatorConfig))
        for i,tup in enumerate(self.annotatorConfig.itervalues()):
            v = tup[0]
            self.tableWidget.setItem(i,0,QtGui.QTableWidgetItem(v.name))
            self.tableWidget.setItem(i,1,QtGui.QTableWidgetItem(v.key.toString()))
            if v.toggleMode:
                self.tableWidget.setItem(i,2,QtGui.QTableWidgetItem("Toggle"))
            else:
                self.tableWidget.setItem(i,2,QtGui.QTableWidgetItem("Hold"))
            self.tableWidget.setItem(i,3,QtGui.QTableWidgetItem(v.description))

        # sort table again
        self.tableWidget.sortItems(sortCol, sortOrd)

        # update key map
        self.shortcuts = []
        for v,s in self.annotatorConfig.itervalues():
            self.shortcuts.append(QtGui.QShortcut(v.key, self.widget, lambda: self.__onShortcutEnable(v.key)))


    ## pseudo slot for key presses. translates key press into label and status
    def __onShortcutEnable(self, keySeq):
        for label, state in self.annotatorConfig.itervalues():
            if label.key == keySeq:
                self.annotatorConfig[label.name] = (label, not state)
                self.keyPressSignal.emit((label.name, not state))


    def __onAddKey(self):
        # open dialog window
        content = None
        dialog = AddEntryDialog(args = [], parent=self.widget)
        dialog.setModal(True)
        if dialog.exec_(): # if dialog closes with accept()
            lm = dialog.lm
            #print lm.name + ' ' + lm.key + ' ' + lm.description + ' ' + str(lm.toggleMode)
            if self.annotatorConfig.has_key(lm.key):
              self.annotatorConfig[lm.name] = (lm, self.annotatorConfig[lm.name][1])
            else:
              self.annotatorConfig[lm.name] = (lm, False)
            self.syncLists()


    def __onDelKey(self):
        # get currently selected item and delete it
        pass


    def __onModKey(self):
        # get currently selected item and open the additem dialog
        row = self.tableWidget.currentRow()
        label = self.tableWidget.item(row,0).text()
        lmOld = self.annotatorConfig[label]
        # open dialog window
        dialog = AddEntryDialog(args = [], parent=self.widget)
        dialog.setModal(True)
        dialog.setValues(lmOld)
        if dialog.exec_():
            lmNew = dialog.lm
            self.annotatorConfig[lmNew.name] = lmNew
            self.syncLists()


    def __updateTableWidget(self):
        self.tableWidget.clearContents()
        self.tableWidget.setRowCount(len(self.keys))

        for kv, i in zip(self.keys.iteritems(), range(len(self.keys))):
            self.tableWidget.setItem(i, 0, QtGui.QTableWidgetItem(kv[0]))



########## Application Logic


## Container for label information
class LabelMeta:
    ## Constructor
    def __init__(self, name = "", key = None, description = "", toggleMode = True):
        self.name = name
        self.key = key
        self.description = description
        self.toggleMode = toggleMode


## A tool for annotating a stream of sensor data with labels
class Annotator(QtCore.QObject):
  newLabelSignal = pyqtSignal(tuple)

  ## Constructor
  def __init__(self):
    super(Annotator, self).__init__()
    self.labelMapping = [] # list of LabelMeta instances
    self.annotations = [] # list of touples containing label, index, and start/stop flag
    self.data = np.zeros((0,0))


  def connectSignals(self, annotatorConfig):
    # set slot for key presses
    annotatorConfig.keyPressSignal.connect(self.__onShortcutEnable)


  ## Slot for receiving data
  @pyqtSlot(tuple)
  def dataSlot(self, data):
    ndata = np.array(data[1], ndmin=2).T

    ## check if length of data vector has changed, and pad with zeros if necessary
    if ndata.shape[0] > self.data.shape[0]:
      self.data = np.vstack((self.data, np.zeros((ndata.shape[0] - self.data.shape[0], self.data.shape[1]))))
    elif ndata.shape[0] < self.data.shape[0]:
      ndata = np.vstack((ndata, np.zeros((self.data.shape[0] - ndata.shape[0], 1))))

    # append
    self.data = np.hstack((self.data, ndata))


  ## Slot for key presses
  @pyqtSlot(tuple)
  def onShortcutEnable(self, data):
    # trigger corresponding label
    if self.data.shape[1] != 0:
      anno = (data[0], data[1], self.data.shape[1])
      self.annotations.append(anno)
      self.newLabelSignal.emit(anno)
      print 'New label: ' + str(anno)

    else:
      print 'Error: No sensor data!'



  ## Returns the annotations
  def getAnnotationData(self):
      pass



if __name__ == '__main__':
  app = QtGui.QApplication(sys.argv)
  l = LiveAnnotation(sys.argv)
  l.show()
  dp.start(100)
  retVal = app.exec_()
  dp.stop()
  sys.exit(retVal)
