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


### TODOS ###
# - fix performance issue (fixed?)
# - enable configuration (WIP)
# - stream video over network
# - add status string under video / plotter (determine what is needed / useful)
# - "null pointer passed" error at shutdown (gone? now "thread destroyed while still running")


# Application GUI

main_form = uic.loadUiType("la.ui")[0]
dialog_form = uic.loadUiType("ad.ui")[0]


# Top level class for main window and module instances
class LiveAnnotation(QtGui.QMainWindow, main_form):

    def __init__(self, args, parent=None):
        QtGui.QMainWindow.__init__(self, parent)
        self.setupUi(self)

        # create all modules
        self.config = ParameterTreeWidget(self.parameterView)
        self.stream = VideoWidget(self.videoView)
        self.plotter = GraphicsLayoutWidget(self.graphicsLayoutView)
        self.annotatorConfig = AnnotationConfigWidget(self.frameKeys)
        self.annotator = Annotator()

        # connect elements
        # self.annotator.newLabelSignal.connect(self.plotter.onNewClassLabel)
        self.annotatorConfig.keyPressSignal.connect(
            self.annotator.onShortcutEnable)
        self.annotatorConfig.keyPressSignal.connect(
            self.plotter.onShortcutEnable)

        dp.obj.start(1000 / 50)
        dp.obj.connect(self.plotter.dataSlot)
        dp.obj.connect(self.annotator.dataSlot)

        # set all config values
        self.connect(self.tabWidget, QtCore.SIGNAL(
            'currentChanged(int)'), self.updateConfigurables)
        self.updateConfigurables()

    # hand key presses to the annotationConfig widget
    def keyPressEvent(self, e):
        self.annotatorConfig.keyPressEvent(e)

    # hand key releases to the annotationConfig widget
    def keyReleaseEvent(self, e):
        self.annotatorConfig.keyReleaseEvent(e)

    def closeEvent(self, event):
        dp.obj.stop()
        self.annotatorConfig.quit()
        self.plotter.quit()
        self.annotator.quit()

        event.accept()

    # Sets all config values again (e.g. after changing the config)
    # only use getValue here, to ensure that all values are updated
    def updateConfigurables(self):
        print 'Reconfiguring all modules'
        self.stream.configure(self.config)
        self.plotter.configure(self.config)
        self.annotatorConfig.configure(self.config)
        self.stream.configure(self.config)
        self.annotator.configure(self.config)
        dp.obj.stop()
        dp.obj.start(1000 / self.config.getValue("Data Sample Rate"))
        dp.obj.connect(self.plotter.dataSlot)
        dp.obj.connect(self.annotator.dataSlot)


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
class GraphicsLayoutWidget:

    def __init__(self, widget):  # create plot window self.w = widget
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
        self.meanHorizonSize = [0 for i in range(0, 50)]

        self.skipCounter = 0

        # set timer for update
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(1000 / 20)

    def update(self):
        numSamples = self.data.shape[1]

        # delete labels that are not visible anymore
        self.annotations = [l for l in self.annotations if l.endIdx > (
            numSamples - self.xLimit) or l.endIdx == -1]

        self.__updateNumberOfPlots()

        for i, pl in enumerate(self.plots):
            pl.listDataItems()[0].setData(self.data[i, :])
            if self.xLimit < numSamples:
                pl.setXRange(numSamples - self.xLimit, numSamples)

        self.__updateClassLabels()

        # app.processEvents()  # force complete redraw for every plot

        # calculate delta t
        thisTime = time.time()
        newDeltaTime = thisTime - self.lastTime
        self.meanHorizonSize.append(newDeltaTime)
        del self.meanHorizonSize[0]
        self.lastTime = thisTime
        meanDeltaTime = sum(self.meanHorizonSize) / len(self.meanHorizonSize)
        self.statusLabel.setText("Cycle Time: {:.2f} ms / {:.2f} Hz, DataParser Period: {:.2f} ms, Number of Data Points: {}".format(
            meanDeltaTime * 1000, 1 / meanDeltaTime, dp.obj.meanDeltaTime * 1000, self.data.shape[1]))

    def configure(self, config):
        self.xLimit = config.getValue('PlottedSamples')
        self.rate = config.getValue('PlotterRefreshRate')
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(1000 / self.rate)

    def quit(self):
        for p in self.plots:
            self.w.removeItem(p)

    # creates new linearRegion objects if necessary and deletes outdated ones
    def __updateClassLabels(self):
        for cl in self.annotations:
            if not cl.linReg:
                for pl in self.plots:
                    #linReg = pg.LinearRegionItem([cl.startIdx, cl.endIdx])
                    linReg = QtGui.QGraphicsRectItem(
                        cl.startIdx, -10, cl.endIdx - cl.startIdx, 20)
                    linReg.setPen(QtGui.QColor(255, 0, 0))
                    brush = QtGui.QBrush(QtCore.Qt.SolidPattern)
                    brush.setColor(QtGui.QColor(128, 128, 128, 100))
                    linReg.setBrush(brush)

                    pl.addItem(linReg)
                    cl.linReg.append(linReg)

            # update bounds if necessary
            # if [cl.startIdx, cl.endIdx] != cl.linReg[0].getRegion():
            if [cl.startIdx, cl.endIdx] != [cl.linReg[0].rect().x, cl.linReg[0].rect().width]:
                endIdx = self.data.shape[1] if cl.endIdx == -1 else cl.endIdx
                for lr in cl.linReg:
                    #lr.setRegion([cl.startIdx, endIdx])
                    lr.setRect(cl.startIdx, -10, endIdx - cl.startIdx, 20)

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

    # slot for reacting to newly annotated labels
    @pyqtSlot(tuple)
    def onShortcutEnable(self, data):
        numSamples = self.data.shape[1]

        # trigger corresponding label
        if numSamples == 0:
            print 'Plotter Error: No sensor data!'
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

    def __updateNumberOfPlots(self):
        numDims = self.data.shape[0]
        while len(self.plots) < numDims:
            self.plots.append(self.w.addPlot())
            self.plots[-1].plot()
            self.plots[-1].showGrid(True, True)
            self.w.nextRow()


# GStreamer video secording and display Wrapper
class VideoWrapper:

    def __init__(self, targetWin):
        self.pl = None
        self.isRunning = False
        self.isRecording = False
        self.isReady = True

        self.targetWin = targetWin
        #self.winId = self.targetWin.winId()
        #print winId
        self.fileOutPath = ""
        self.source = "videotestsrc"

    # If not already running / ready / not recording, create a new pipeline
    # and start it
    def play(self):
        #if self.isRunning or not self.isReady or self.isRecording:
        if self.isRunning or not self.isReady:
            return

        self.isRunning = True
        self.__updatePipeline()
        self.pl.set_state(Gst.State.PLAYING)
        print "Start playing"

    #
    # If currently running, stop the pipeline and set to not ready
    def stop(self):
        if self.isRunning:
            self.isRunning = False
            self.isReady = False
            self.isRecording = False
            self.pl.send_event(Gst.Event.new_eos())
        print "Stop playing"

    # Turns the recording on or off, depending on the previous state. Only
    # allowed when running
    def toggleRec(self):
        print "Toggle Recording, is now: " + str("on" if not self.isRecording else "off")
        #if not self.isRunning or not self.isReady:
        if not self.isReady:
            return

        if not self.isRecording:
            self.isRecording = True
            self.__updatePipeline()
        else:
            self.isRecording = False
            if self.pl:
                self.isReady = False
                self.pl.send_event(Gst.Event.new_eos())
                print "\tSent EOS"
            else:
                self.isReady = True
                print "\tStopped recording, but stream was not playing anyway"


    def getStateStr(self):
        state = "Running, " if self.isRunning else "Halted, "
        state += "Ready, " if self.isReady else "Not Ready, "
        state += "Recording, " if self.isRecording else "Not Recording, "
        return state

    def setSource(self, source):
        self.source = source
        #self.__updatePipeline()

    def setIP(self, ip):
        self.ip = ip

    def setFramerate(self, framerate):
        self.framerate = framerate

    # Creates / updates the GStreamer pipeline according to the currently set
    # state
    def __updatePipeline(self):
        print "Updating Pipeline, isReady: {}, isRunning: {}, isRecording: {} ".format(self.isReady, self.isRunning, self.isRecording)
        if self.pl:
            self.pl.set_state(Gst.State.NULL)
            self.pl = []

        pipeString = ""
        if self.isRecording:
        #    pipeString = self.source + \
        #        " ! tee name=t t. ! queue ! videoconvert ! x264enc ! mp4mux ! filesink location=outvid01 async=0 t. ! queue ! autovideosink"
            pipeString = "videotestsrc ! tee name=t t. ! queue ! videoconvert ! x264enc ! mp4mux ! filesink location=outvid01 async=0 t. ! queue ! autovideosink"
        else:
            pipeString = self.source + " ! autovideosink"

        print "\tPipeline String: " + pipeString
        self.pl = Gst.parse_launch(pipeString)

        # intercept sync messages so we can set in which window to draw in
        bus = self.pl.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message::eos", self.__onEos)
        bus.connect("message::error", self.__onError)
        bus.connect("sync-message::element", self.__onSyncMessage)

        if self.isRunning:
            self.pl.set_state(Gst.State.PLAYING)
        else:
            self.pl.set_state(Gst.State.NULL)

        print "\tWinID: " + str(self.targetWin.winId())

    # GStreamer Callback for end of stream messages
    def __onEos(self, bus, message):
        print "Received EOS"
        self.pl.set_state(Gst.State.NULL)

        # if we got here by stopping the recording, update the pipeline and
        # start again
        #if self.isRunning:
        #    self.__updatePipeline()
        #    self.play()
        #else:
        #    self.pl = None
        self.pl = None

        self.isReady = True

    # GStreamer Callback for error messages
    def __onError(self, bus, message):
        err, debug = message.parse_error()
        print "Error: %s" % err, debug
        self.pl.set_state(Gst.State.NULL)
        self.isRunning = False
        self.isRecording = False
        self.isReady = True

    # GStreamer Callback for sync messages, sent when autovideosink wants to
    # draw to an x window
    def __onSyncMessage(self, bus, message):
        if message.get_structure().get_name() == "prepare-window-handle":
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            imagesink.set_window_handle(self.targetWin.winId())


# Widget managing video stream
class VideoWidget:

    def __init__(self, widget):
        self.widget = widget
        self.widget.parent().findChild(QtGui.QPushButton,
                                       "btnRec").clicked.connect(self.__onRec)
        self.widget.parent().findChild(QtGui.QPushButton,
                                       "btnPlay").clicked.connect(self.__onPlay)
        self.widget.parent().findChild(QtGui.QPushButton,
                                       "btnPause").clicked.connect(self.__onPause)
        self.statusLabel = self.widget.parent().findChild(
            QtGui.QLabel, "labelVideoStatus")

        self.wrapper = VideoWrapper(self.widget)

    # Play button callback
    def __onPlay(self):
        self.wrapper.play()
        self.__updateStatusLabel()

    # Pause button callback
    def __onPause(self):
        self.wrapper.stop()
        self.__updateStatusLabel()

    # Record button callback
    def __onRec(self):
        self.wrapper.toggleRec()
        self.__updateStatusLabel()

    # Configurable member
    def configure(self, config):
        self.fileOutPath = config.getValue('VideoOutputFile')
        self.filePolicy = config.getValue('VideoOutputFilePolicy')
        self.wrapper.setSource(config.getValue('GStreamerVideoSource'))
        self.wrapper.setIP(config.getValue('NetworkSourceIP'))
        self.wrapper.setFramerate(config.getValue('VideoFrameRate'))

    # Sets the status label text with the current module status
    def __updateStatusLabel(self):
        self.statusLabel.setText(self.wrapper.getStateStr())


# Widget populating and reading configuration
class ParameterTreeWidget(QtCore.QObject):

    def __init__(self, parameterView):
        super(ParameterTreeWidget, self).__init__()
        defaultParams = [
            {'name': 'General', 'type': 'group', 'children': [
                {'name': 'General Config File Path', 'type': 'str', 'value': "config.cfg"},
            ]},
            {'name': 'Video', 'type': 'group', 'children': [
                {'name': 'GStreamer Video Source', 'type': 'list', 'values': {"Test Source": "videotestsrc", "Webcam": "v4l2src", "network": "udp"}, 'value': "videotestsrc", 'children': [
                    {'name': 'Network Source IP', 'type': 'str', 'value': "127.0.0.1"},
                ]},
                {'name': 'Video Frame Rate', 'type': 'float', 'value': 5e1, 'siPrefix': True, 'suffix': 'Hz'},
                {'name': 'Video Output File', 'type': 'str', 'value': "outvideo.mp4"},
                {'name': 'Video Output File Policy', 'type': 'list', 'values' : {"Overwrite" : "overwrite", "Append" : "append", "Enumerate" : "enumerate"}, 'value' : "overwrite"},
            ]},
            {'name': 'Annotation', 'type': 'group', 'children': [
                {'name': 'Data Sample Rate', 'type': 'float', 'value': 5e1, 'siPrefix': True, 'suffix': 'Hz'},
                {'name': 'Concurrent Labels', 'type': 'bool', 'value': False},
                {'name': 'Save Annotator Key Mapping', 'type': 'bool', 'value': True},
                {'name': 'Annotator Key Mapping Save File', 'type': 'str', 'value': "keymap.cfg"},
                {'name': 'Annotator Data Output Target', 'type': 'list', 'values': {
                    "File": "file", "Standard Output": "stdout"}, 'value': "file"},
                {'name': 'Data Output Filename', 'type': 'str', 'value': "annotated_data.txt"},
            ]},
            {'name': 'Plotting', 'type': 'group', 'children': [
                {'name': 'Plotted Samples', 'type': 'int', 'value': 500},
                {'name': 'Plotter Refresh Rate', 'type': 'float', 'value': 2e1, 'siPrefix': True, 'suffix': 'Hz'},
            ]},
        ]


        # MORE PARAMS TO BE IMPLEMENTED
        # - output video file path
        # - overwrite / append / create new output video file
        # - custom Gstreamer source string

        self.p = Parameter.create(
            name='params', type='group', children=defaultParams)


        """
        def flatten(param):
            items = []
            for ch in param.children():
                items.extend(flatten(ch).items())

            items.extend({param.name() : param.value()}.items())
            return dict(items)
        """


        self.t = parameterView  # use the ID of the promoted graphicsView
        self.t.setParameters(self.p, showTop=False)
        self.t.show()

    # recursively go through the tree and search for a parameter with <key>
    # returns None if no value was found
    def getValue(self, key, tree=None):
        if tree is None:
            tree = self.p

        for ch in tree.children():
            if ch.name() == key or ch.name().replace(" ", "") == key:
                return ch.value()
            else:
                cv = self.getValue(key, ch)
                if cv is not None:
                    return cv

        if tree is self.p:
            print "Warning: Requested config value \"" + key + "\" not found. Returning None!"
        return None

    def save(self):
        self.state = self.p.saveState()

    def restore(self):
        add = self.p['Save/Restore functionality',
                     'Restore State', 'Add missing items']
        rem = self.p['Save/Restore functionality',
                     'Restore State', 'Remove extra items']
        self.p.restoreState(self.state, addChildren=add, removeChildren=rem)


# Subwindow to add / modify a new label type
class AddEntryDialog(QtGui.QDialog, dialog_form):

    def __init__(self, args, parent):
        QtGui.QDialog.__init__(self, parent)
        self.setupUi(self)
        self.parent = parent

        self.listenForKeyPress = False

        # connect ok / cancel buttons
        self.btnRecShortcut.released.connect(self.onRecKey)
        self.buttonBox.accepted.connect(self.onAccept)
        self.buttonBox.rejected.connect(self.onReject)
        #self.connect(buttonBox, QtCore.SIGNAL("accepted()"), self.onAccept, QtCore.SLOT("accept()"))

    # Setter for filling in values when modifying
    def setValues(self, lm):
        self.editName.setText(lm.name)
        self.editKeyMap.setText(lm.key.toString())
        self.radioToggle.setChecked(lm.toggleMode)
        self.radioHold.setChecked(not lm.toggleMode)
        self.editDescription.setText(lm.description)

    # Records a modifier + key shortcut
    def onRecKey(self):
        # prompt the user to enter a shortcut
        self.editKeyMap.setText("Press key...")

        # enable keypress event listener
        self.listenForKeyPress = True

    def keyPressEvent(self, e):
        if self.listenForKeyPress and e.key() not in (QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift):
            modifiers = QtGui.QApplication.keyboardModifiers()
            keyMods = ''
            if modifiers & QtCore.Qt.ControlModifier:
                keyMods += 'Ctrl+'
            if modifiers & QtCore.Qt.AltModifier:
                keyMods += 'Alt+'
            if modifiers & QtCore.Qt.ShiftModifier:
                keyMods += 'Shift+'
            keySeq = QtGui.QKeySequence(e.key())
            keySeq = QtGui.QKeySequence(keyMods + keySeq.toString())

            self.editKeyMap.setText(keySeq.toString())

            self.listenForKeyPress = False

    # reads out the forms and returns LabelMeta instance
    def onAccept(self):
        if not str(self.editName.text()).isalnum():
            errdiag = QtGui.QErrorMessage()
            errdiag.showMessage("Invalid label name. Only alphanumerical characters are allowed.")

        else:
            self.lm = LabelMeta(str(self.editName.text()), QtGui.QKeySequence(self.editKeyMap.text(
            )), str(self.editDescription.toPlainText()), self.radioToggle.isChecked())
            self.accept()

    # just close the window
    def onReject(self):
        self.close()


# Container for label information
class LabelMeta:

    def __init__(self, name="", key=None, description="", toggleMode=True):
        self.name = name
        self.key = key
        self.description = description
        self.toggleMode = toggleMode
        self.state = False

    def __str__(self):
        return "Name: " + self.name + ", Key: " + str(self.key.toString()) + ", Descr: " + self.description


# Class managing the annotation configuration widget
class AnnotationConfigWidget(QtGui.QWidget):
    # class AnnotationConfigWidget:
    keyPressSignal = pyqtSignal(tuple)

    # Constructor
    def __init__(self, widget):
        super(AnnotationConfigWidget, self).__init__()
        super(QtGui.QWidget, self).__init__()

        # get access to all elements in the annotation config qframe
        self.widget = widget
        self.tableWidget = widget.findChild(QtGui.QTableWidget, "keyTable")
        widget.findChild(QtGui.QPushButton, "btnAddKey").clicked.connect(
            self.__onAddKey)
        widget.findChild(QtGui.QPushButton, "btnModKey").clicked.connect(
            self.__onModKey)
        widget.findChild(QtGui.QPushButton, "btnDelKey").clicked.connect(
            self.__onDelKey)

        self.annotatorConfig = {}
        self.simultaneousLabels = True
        self.loadConfig("shortcuts.cfg")

        self.syncLists()

        self.saveShortcutsOnExit = True

    def configure(self, config):
        self.saveKeyMapping = config.getValue('SaveAnnotatorKeyMapping')

    # loads the annotation config from a binary file
    def loadConfig(self, path):
        try:
            f = open(path, "rb")
            self.annotatorConfig = pickle.load(f)
            print "Existing shortcuts loaded:"
            for a in self.annotatorConfig.itervalues():
                print "\t" + str(a)
        except Exception:
            print "Error loading shortcut file"

    def saveConfig(self, path):
        # serialize config
        f = open(path, "wb")
        pickle.dump(self.annotatorConfig, f, pickle.HIGHEST_PROTOCOL)
        print "Saved shortcuts:"
        for a in self.annotatorConfig.itervalues():
            print a

    def quit(self):
        if self.saveShortcutsOnExit:
            # turn all labels off
            for k, v in self.annotatorConfig.iteritems():
                self.annotatorConfig[k].state = False

            self.saveConfig("shortcuts.cfg")

    def keyPressEvent(self, e):
        if e.key() in (QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift):
            return  # filter out modifier events

        # filter keypresses generated by auto repeat
        if e.isAutoRepeat():
            return

        keySeq = AnnotationConfigWidget.assembleKeySequence(
            e.key(), QtGui.QApplication.keyboardModifiers())

        # search list of keymaps for this combination
        for a in self.annotatorConfig.itervalues():
            if a.key.toString() == keySeq.toString():
                if a.toggleMode:
                    a.state = not a.state  # toggle mode, thus toggle
                    self.keyPressSignal.emit((a.name, a.state))  # send out new label state
                else:
                    if not a.state:  # if previous state was "off"
                        # send out new label state
                        self.keyPressSignal.emit((a.name, not a.state))
                    a.state = True  # hold mode, turn on / let it stay on
            elif a.key.toString() != keySeq.toString() and not self.simultaneousLabels:
                # if only one label at a time is allowed, stop all other labels
                if a.state:
                    a.state = False
                    self.keyPressSignal.emit((a.name, a.state))  # send out new label state

    def keyReleaseEvent(self, e):
        if e.key() in (QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift):
            return  # filter out modifier events

        if e.isAutoRepeat():
            return

        keySeq = AnnotationConfigWidget.assembleKeySequence(
            e.key(), QtGui.QApplication.keyboardModifiers())

        # search list of keymaps for this combination
        for a in self.annotatorConfig.itervalues():
            if a.key == keySeq:
                if not a.toggleMode:
                    if a.state:  # if previous state was "on"
                        # send out new label state
                        self.keyPressSignal.emit((a.name, not a.state))
                    a.state = False  # hold mode, turn on / let it stay on

    @staticmethod
    def assembleKeySequence(key, mods):
        keyMods = ''
        if mods & QtCore.Qt.ControlModifier:
            keyMods += 'Ctrl+'
        if mods & QtCore.Qt.AltModifier:
            keyMods += 'Alt+'
        if mods & QtCore.Qt.ShiftModifier:
            keyMods += 'Shift+'
        keySeq = QtGui.QKeySequence(key)
        keySeq = QtGui.QKeySequence(keyMods + keySeq.toString())
        return keySeq

    # Synchronizes the internal list with the displayed table and updates
    # shotcuts
    def syncLists(self):
        # save sort column and order for sorting afterwards
        sortCol = self.tableWidget.horizontalHeader().sortIndicatorSection()
        sortOrd = self.tableWidget.horizontalHeader().sortIndicatorOrder()

        # clear table and reinsert all items
        self.tableWidget.clearContents()
        self.tableWidget.setRowCount(len(self.annotatorConfig))
        for i, v in enumerate(self.annotatorConfig.itervalues()):
            self.tableWidget.setItem(i, 0, QtGui.QTableWidgetItem(v.name))
            self.tableWidget.setItem(
                i, 1, QtGui.QTableWidgetItem(v.key.toString()))
            if v.toggleMode:
                self.tableWidget.setItem(
                    i, 2, QtGui.QTableWidgetItem("Toggle"))
            else:
                self.tableWidget.setItem(i, 2, QtGui.QTableWidgetItem("Hold"))
            self.tableWidget.setItem(
                i, 3, QtGui.QTableWidgetItem(v.description))

        # sort table again
        self.tableWidget.sortItems(sortCol, sortOrd)

    def __onAddKey(self):
        # open dialog window
        dialog = AddEntryDialog(args=[], parent=self.widget)
        dialog.setModal(True)
        if dialog.exec_():  # if dialog closes with accept()
            lm = dialog.lm
            if self.annotatorConfig.has_key(lm.key):
                print "Label already exists. Use \"Modify\" to change an existing item."
                return
            else:
                self.annotatorConfig[lm.name] = lm

            self.syncLists()

    def __onDelKey(self):
        # get currently selected item and delete it
        row = self.tableWidget.currentRow()

        # check if there is an item selected
        if row == -1:
            return

        # get label
        label = str(self.tableWidget.item(row, 0).text())

        # stop annotation if the label is currently active
        if self.annotatorConfig[label].state:
            self.keyPressSignal.emit((label, not self.annotatorConfig[label].state))  # send out new label state

        # delete table widget item and dict item
        del(self.annotatorConfig[label])
        self.syncLists()



    def __onModKey(self):
        # get currently selected item and open the additem dialog
        row = self.tableWidget.currentRow()

        # check if there is an item selected
        if row == -1:
            return

        label = str(self.tableWidget.item(row, 0).text())
        lmOld = self.annotatorConfig[label]

        # open dialog window
        dialog = AddEntryDialog(args=[], parent=self.widget)
        dialog.setModal(True)
        dialog.setValues(lmOld)
        if dialog.exec_():
            dialog.lm.state = lmOld.state
            del(self.annotatorConfig[label])
            self.annotatorConfig[dialog.lm.name] = dialog.lm
            self.syncLists()

    def __updateTableWidget(self):
        self.tableWidget.clearContents()
        self.tableWidget.setRowCount(len(self.keys))

        for kv, i in zip(self.keys.iteritems(), range(len(self.keys))):
            self.tableWidget.setItem(i, 0, QtGui.QTableWidgetItem(kv))


# Application Logic


# A tool for annotating a stream of sensor data with labels
class Annotator(QtCore.QObject):
    newLabelSignal = pyqtSignal(tuple)

    # Constructor
    def __init__(self):
        super(Annotator, self).__init__()
        self.annotations = []  # list of touples containing label, index, and start/stop flag
        self.data = np.zeros((0, 0))
        self.outFilePath = 'annotationOut.txt'

    def configure(self, config):
        self.allowMultiLabel = config.getValue('ConcurrentLabels')
        self.sampleRate = config.getValue('DataSampleRate')
        self.saveKeyMaps = config.getValue('SaveAnnotatorKeyMapping')
        self.output = config.getValue('AnnotatorDataOutputTarget')
        self.outFilePath = config.getValue('DataOutputFilename')

    def quit(self):
        # write annotation data
        self.writeAnnotatedData()

    # Slot for receiving data
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

    # Slot for key presses
    @pyqtSlot(tuple)  # tuple = (name, on / off)
    def onShortcutEnable(self, data):
        numSamples = self.data.shape[1]


        # trigger corresponding label
        if numSamples == 0:
            print 'Annotator Error: No sensor data!'
            return

        # start a new label area or end a started one
        if data[1]:  # label start
            # create new label that is open to the right
            self.annotations.append(Label(data[0], numSamples, -1))

        else:  # label end
            # find start of label
            for l in reversed(self.annotations):
                if l.name == data[0]:  # if same label type
                    l.endIdx = numSamples
                    print 'New label: ' + str(l)
                    break

            else:
                print "Annotator Error: ending label failed, no corresponding start"

    def writeAnnotatedData(self):
        if not self.annotations:
            return

        # create "empty" labels
        outLabels = ["other" for i in range(self.data.shape[1])]

        # apply annotation
        for a in self.annotations:
            for i in range(a.startIdx, a.endIdx):
                outLabels[i] = a.name

        # create final output data
        outData = ""
        for i in range(self.data.shape[1]):
            nums = self.data[:, i].tolist()
            outData += outLabels[i] + ' ' + ' '.join(map(str, nums)) + '\n'

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
