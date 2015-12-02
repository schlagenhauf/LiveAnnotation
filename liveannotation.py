#!/usr/bin/env python

import sys, pickle
from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import pyqtSlot, pyqtSignal
from pyqtgraph.parametertree import Parameter
import pyqtgraph as pg

#import gst, gobject
#gobject.threads_init()
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
    self.stream = VideoWidget(self.videoView)
    self.plotter = GraphicsLayoutWidget(self.graphicsLayoutView)
    self.annotatorConfig = AnnotationConfigWidget(self.frameKeys)
    self.annotator = Annotator()

    # connect elements
    #self.annotator.newLabelSignal.connect(self.plotter.onNewClassLabel)
    self.annotatorConfig.keyPressSignal.connect(self.annotator.onShortcutEnable)
    self.annotatorConfig.keyPressSignal.connect(self.plotter.onShortcutEnable)

    dp.start(1000 / 50)
    dp.connect(self.plotter.dataSlot)
    dp.connect(self.annotator.dataSlot)

    # set all config values
    self.updateConfigurables()


  def closeEvent(self, event):
    dp.stop()
    self.annotatorConfig.quit()
    self.plotter.quit()
    self.annotator.quit()

    event.accept()


  ## Sets all config values again (e.g. after changing the config)
  # only use getConfigValue here, to ensure that all values are updated
  def updateConfigurables(self):
    # video config
    self.stream.updatePipeline(self.config.getConfigValue('Video Source'))



## Plottable label container
class Label:
  def __init__(self, name = 'other', startIdx = 0, endIdx = -1):
    self.name = name
    self.startIdx = startIdx
    self.endIdx = endIdx

  def __str__(self):
    return str((self.name, self.startIdx, self.endIdx))


class PlotLabel(Label):
  def __init__(self, name = 'other', startIdx = 0, endIdx = -1):
    Label.__init__(self, name, startIdx, endIdx)
    self.linReg = []




## Widget managing plotting
class GraphicsLayoutWidget:
  ## Constructor
  def __init__(self, widget): # create plot window self.w = widget
    self.plots = []
    self.w = widget

    self.yLabels = [] # names of each sensor dimension
    self.annotations = [] # list of plotlabel containers
    self.data = np.zeros((0,0)) # a matrix containing data for each dimension per row

    self.statusLabel = self.w.parent().findChild(QtGui.QLabel, "labelPlotStatus")

    # config
    self.xLimit = 300
    self.rate = 50


  def update(self):
    numSamples = self.data.shape[1]

    self.__updateNumberOfPlots()

    for i,pl in enumerate(self.plots):
      pl.listDataItems()[0].setData(self.data[i,:])
      if self.xLimit < numSamples:
        pl.setXRange(numSamples - self.xLimit, numSamples)

    self.__updateClassLabels()

    app.processEvents()  ## force complete redraw for every plot


  def quit(self):
    for p in self.plots:
      self.w.removeItem(p)


  ## creates new linearRegion objects if necessary and deletes outdated ones
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
    self.statusLabel.setText('Samples: ' + str(numSamples) + ' [' + str(visibleSamples) + ' visible]')


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
  def onShortcutEnable(self, data):
    numSamples = self.data.shape[1]

    # trigger corresponding label
    if numSamples == 0:
      print 'Error: No sensor data!'
      return


    # start a new label area or end a started one
    if data[1]: # label start
      self.annotations.append(PlotLabel(data[0], numSamples, -1)) # create new label that is open to the right

    else: # label end
      # find start of label
      for l in reversed(self.annotations):
        if l.name == data[0]: # if same label type
          l.endIdx = numSamples
          break

      else:
        print "Error: ending label failed, no corresponding start"



  def __updateYLabels(self):
    # assign y axis labels (if more/less labels are given, list is truncated accordingly)
      for p,l in zip(self.plots, self.yLabels):
        p.setLabel('left', l)


  def __updateNumberOfPlots(self):
    numDims = self.data.shape[0]
    while len(self.plots) < numDims:
      self.plots.append(self.w.addPlot())
      self.plots[-1].plot()
      self.plots[-1].showGrid(True, True)
      self.w.nextRow()

    self.__updateYLabels()



## Widget managing video stream
class VideoWidget:
  ## Constructor
  def __init__(self, widget):
    self.widget = widget
    self.widget.parent().findChild(QtGui.QPushButton, "btnRec").clicked.connect(self.__onRec)
    self.widget.parent().findChild(QtGui.QPushButton, "btnPlay").clicked.connect(self.__onPlay)
    self.widget.parent().findChild(QtGui.QPushButton, "btnPause").clicked.connect(self.__onPause)
    self.isRunning = False
    self.isRecording = False
    self.fileOutPath = ""


  def __onPlay(self):
    if not self.isRunning:
      self.pl.set_state(Gst.State.PLAYING)
      self.isRunning = True


  def __onPause(self):
    if self.isRunning:
      self.pl.set_state(Gst.State.NULL)
      self.isRunning = False


  def __onRec(self):
    if not self.isRecording:
      self.isRecording = True
    else:
      self.isRecording = False


  def updatePipeline(self, source):
    # create pipeline and elements
    self.pl = Gst.Pipeline("pipeline")

    self.source = Gst.ElementFactory.make(source, None)
    self.tee = Gst.ElementFactory.make("tee", None)
    self.screenQueue = Gst.ElementFactory.make("queue", None)
    self.screenSink = Gst.ElementFactory.make("autovideosink", None)
    self.screenSink.set_property('async-handling', 'true')

    self.fileQueue = Gst.ElementFactory.make("queue", None)
    self.videoConvert = Gst.ElementFactory.make("videoconvert", None)
    self.enc = Gst.ElementFactory.make("x264enc", None)
    self.mux = Gst.ElementFactory.make("mp4mux", None)
    self.fileSink = Gst.ElementFactory.make("filesink", None)
    self.fileSink.set_property('location', r'outvideo.raw')
    #self.fileSink.set_property('async', '0')
    self.fileSink.set_property('sync', 'true')


    # add elements to pipeline and connect them

    self.pl.add(self.source)
    self.pl.add(self.tee)
    self.pl.add(self.screenQueue)
    self.pl.add(self.screenSink)
    self.pl.add(self.fileQueue)
    self.pl.add(self.videoConvert)
    self.pl.add(self.enc)
    self.pl.add(self.mux)
    self.pl.add(self.fileSink)

    self.source.link(self.tee)

    self.teeScreenPad = self.tee.get_request_pad("src_%u")
    self.queueScreenPad = self.screenQueue.get_static_pad("sink")
    self.teeFilePad = self.tee.get_request_pad("src_%u")
    self.queueFilePad = self.fileQueue.get_static_pad("sink")

    self.teeScreenPad.link(self.queueScreenPad)
    self.screenQueue.link(self.screenSink)

    self.teeFilePad.link(self.queueFilePad)
    self.fileQueue.link(self.videoConvert)
    self.videoConvert.link(self.enc)
    self.enc.link(self.mux)
    self.mux.link(self.fileSink)


    # intercept sync messages so we can set in which window to draw in
    bus = self.pl.get_bus()
    bus.add_signal_watch()
    bus.enable_sync_message_emission()
    bus.connect("message::eos", self.__onEos)
    bus.connect("message::error", self.__onError)
    bus.connect("sync-message::element", self.__onSyncMessage)


  def __onEos(self, bus, message):
    self.pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, 0)
    self.pl.set_state(Gst.State.NULL)


  def __onError(self, bus, message):
    err, debug = message.parse_error()
    print "Error: %s" % err, debug
    self.pl.set_state(Gst.State.NULL)


  def __onSyncMessage(self, bus, message):
    if message.get_structure().get_name() == "prepare-window-handle":
      imagesink = message.src
      imagesink.set_property("force-aspect-ratio", True)
      imagesink.set_window_handle(self.widget.winId())


  @staticmethod
  def linkMulti(elements):
    assert(len(elements) > 1)
    for a,b in zip(elements, elements[1:]):
      a.link(b)




## Widget populating and reading configuration
class ParameterTreeWidget:
  ## Constructor
  def __init__(self, parameterView):
    defaultParams = [
      {'name': 'General', 'type': 'group', 'children': [
        {'name': 'Config Path', 'type': 'str', 'value': "config.cfg"},
        {'name': 'Save Key Maps', 'type': 'bool', 'value': True},
        {'name': 'Key Map Save File', 'type': 'str', 'value': "keymap.cfg"},
        {'name': 'Data Output Target', 'type': 'list', 'values': {"File": "file", "Standard Output": "stdout"}, 'value': "Standard Output"},
        {'name': 'Data Output Filename', 'type': 'str', 'value': "annotated_data.txt"},
      ]},
      {'name': 'Video', 'type': 'group', 'children': [
        {'name': 'Video Source', 'type': 'list', 'values': {"Test Source": "videotestsrc", "Webcam": "v4l2src", "network": "udp"}, 'value': "Test Source", 'children': [
          {'name': 'Network Source IP', 'type': 'str', 'value': "127.0.0.1"},
          ]},
        {'name': 'Sample Rate', 'type': 'float', 'value': 5e1, 'siPrefix': True, 'suffix': 'Hz'},
        ]},
      {'name': 'Annotation', 'type': 'group', 'children': [
        {'name': 'Sample Rate', 'type': 'float', 'value': 5e1, 'siPrefix': True, 'suffix': 'Hz'},
        {'name': 'Displayed Samples (0 for all)', 'type': 'int', 'value': 500},
      ]},
    ]

    ### MORE PARAMS TO BE IMPLEMENTED
    # - output video file path
    # - overwrite / append / create new output video file
    # - custom Gstreamer source string


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

    self.listenForKeyPress = False

    # connect ok / cancel buttons
    self.btnRecShortcut.released.connect(self.__onRecKey)
    self.buttonBox.accepted.connect(self.__onAccept)
    self.buttonBox.rejected.connect(self.__onReject)


  ## Setter for filling in values when modifying
  def setValues(self, lm):
    self.editName.setText(lm.name)
    self.editKeyMap.setText(lm.key.toString())
    self.radioToggle.setChecked(lm.toggleMode)
    self.radioHold.setChecked(not lm.toggleMode)
    self.editDescription.setText(lm.description)


  ## Records a modifier + key shortcut
  def __onRecKey(self):
    # prompt the user to enter a shortcut
    self.editKeyMap.setText("Press key...")

    # enable keypress event listener
    self.listenForKeyPress = True

  def keyPressEvent(self, e):
    if self.listenForKeyPress and e.key() not in (QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift):
      modifiers = QtGui.QApplication.keyboardModifiers()
      keyMods = ''
      if modifiers & QtCore.Qt.ControlModifier: keyMods += 'Ctrl+'
      if modifiers & QtCore.Qt.AltModifier: keyMods += 'Alt+'
      if modifiers & QtCore.Qt.ShiftModifier: keyMods += 'Shift+'
      keySeq = QtGui.QKeySequence(e.key())
      keySeq = QtGui.QKeySequence(keyMods + keySeq.toString())

      self.editKeyMap.setText(keySeq.toString())

      self.listenForKeyPress = False



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
      try:
        f = open("shortcuts.cfg", "rb")
        self.annotatorConfig = pickle.load(f)
      except Exception:
        print "Error loading shortcut file"

      self.syncLists()
      # listen to keypress events and send signals

      self.saveShortcutsOnExit = True


    def quit(self):
      if self.saveShortcutsOnExit:
        # serialize config
        f = open("shortcuts.cfg", "wb")
        pickle.dump(self.annotatorConfig, f, pickle.HIGHEST_PROTOCOL)


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
                self.keyPressSignal.emit((label.name, state))


    def __onAddKey(self):
        # open dialog window
        content = None
        dialog = AddEntryDialog(args = [], parent=self.widget)
        dialog.setModal(True)
        if dialog.exec_(): # if dialog closes with accept()
            lm = dialog.lm
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
    self.outFilePath = 'annotationOut.txt'


  def quit(self):
    # write annotation data
    self.writeAnnotatedData()


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
  @pyqtSlot(tuple) # tuple = (name, on / off)
  def onShortcutEnable(self, data):
    numSamples = self.data.shape[1]

    # trigger corresponding label
    if numSamples == 0:
      print 'Error: No sensor data!'
      return


    # start a new label area or end a started one
    if data[1]: # label start
      self.annotations.append(Label(data[0], numSamples, -1)) # create new label that is open to the right

    else: # label end
      # find start of label
      for l in reversed(self.annotations):
        if l.name == data[0]: # if same label type
          l.endIdx = numSamples
          break

      else:
        print "Error: ending label failed, no corresponding start (annotator)"

    #self.newLabelSignal.emit((self.annotations[-1].name) # tuple = (name, start or end, index)

    print "num annots: " + str(len(self.annotations)) + " , tuple: " + str(data)
    print 'New label: ' + str(self.annotations[-1])



  def writeAnnotatedData(self):
    if not self.annotations:
      return


    print "annotation is written"

    # create "empty" labels
    outLabels = ["other" for i in range(self.data.shape[1])]

    # apply annotation
    for a in self.annotations:
      for i in range(a.startIdx, a.endIdx):
        outLabels[i] = a.name

    # create final output data
    outData = ""
    for i in range(self.data.shape[1]):
      nums = self.data[:,i].tolist()
      outData += outLabels[i] + ' ' + ' '.join(map(str, nums)) + '\n'

    print "numData: " + str(self.data.shape[1]) + "lenOutData: " + str(len(outData))

    # open file and write
    outFile = open(self.outFilePath, 'w')
    outFile.write(outData)
    outFile.close()




if __name__ == '__main__':
  app = QtGui.QApplication(sys.argv)
  l = LiveAnnotation(sys.argv)
  l.show()
  retVal = app.exec_()
  sys.exit(retVal)
