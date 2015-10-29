#!/usr/bin/env python

import sys
from PyQt4 import QtCore, QtGui, uic
from pyqtgraph.parametertree import Parameter

import gst, gobject
gobject.threads_init()

import numpy as np



# Gui to Annotator:
#   labeling changes
#   config
#   saving of labels
#   new label keys
#   key presses
# Annotator to Gui:
#   Sensor data
#   Labels



form_class = uic.loadUiType("la.ui")[0]


## Top level class for main window and module instances
class LiveAnnotation(QtGui.QMainWindow, form_class):
    ## Constructor
    def __init__(self, args, parent=None):
        QtGui.QMainWindow.__init__(self,parent)
        self.setupUi(self)

        # create all modules
        self.config = ParameterTreeWidget(self.parameterView)
        self.stream = VideoWidget(self.videoView.winId())
        self.plotter = GraphicsLayoutWidget(self.graphicsLayoutView)
        self.annotator = Annotator()

        # connect elements
        self.btnPlay.clicked.connect(self.stream.play)
        self.btnPause.clicked.connect(self.stream.pause)

        # set all config values
        self.updateConfigurables()



    ## Sets all config values anew (e.g. after changing the config)
    # only use getConfigValue here, to ensure that all values are updated
    def updateConfigurables(self):
        # video config
        print self.config.getConfigValue('Video Source')
        self.stream.updatePipeline(self.config.getConfigValue('Video Source'))


        # plot config


        # annotator config


# Widget managing plotting
class GraphicsLayoutWidget:
    def __init__(self, widget):
        # create plot window
        self.w = widget
        self.plots = []

        self.labels = []
        self.data = np.zeros((0,0)) # a matrix containing data for each dimension per row


    def updateNumberOfPlots(self):
        numDims = len(self.data)
        while len(self.plots) < numDims:
            self.plots.append(self.w.addPlot())
            self.plots[-1].plot()
            self.plots[-1].showGrid(True, True)
            self.w.nextRow()

        self.updatePlotLabels()


    def update(self):
        self.data = self.dataParser.getData()
        self.updateNumberOfPlots()
        for i in range(len(self.plots)):
            self.plots[i].listDataItems()[0].setData(self.data[i,:])
        app.processEvents()  ## force complete redraw for every plot


    def setYLabels(self, labels):
        self.labels = labels
        self.updatePlotLabels()

    def setData(self, data):
        self.data = data

    def updatePlotLabels(self):
        # assign y axis labels (if more/less labels are given, list is truncated accordingly)
        for p,l in zip(self.plots, self.labels):
            p.setLabel('left', l)



# Widget managing video stream
class VideoWidget:
    def __init__(self, winId):
        assert winId
        self.winId = winId

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

    def startRecording(self, path):
        # enable pipeline output to file
        pass

    def stopRecording(self):
        pass

    def updatePipeline(self, source):
        print "create pipeline"

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
        bus.connect("message", self.onMessage)
        bus.connect("sync-message::element", self.onSyncMessage)



# Widget populating and reading configuration
class ParameterTreeWidget:
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


    # recursively go through the tree and search for a parameter with <key>
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



## Container for label information
class LabelMeta:
    ## Constructor
    def __init__(self, name, key, description, toggleMode):
        self.name = name
        self.key = key
        self.description = description
        self.toggleMode = toggleMode


## Class managing the annotation configuration widget
class AnnotationConfigWidget:
    ## Constructor
    def __init__(self):
        pass

    ## Sets the displayed configuration by a list of LabelMeta instances
    def setConfig(self, cfg):
        pass


    ## Returns the (modified) configuration as a list of LabelMeta instances
    def getConfig(self):
        pass


## A tool for annotating a stream of sensor data with labels
class Annotator:
    ## Constructor
    def __init__(self):
        self.labelMapping = [] # list of LabelMeta instances
        self.annotations = [] # list of touples containing label, index, and start/stop flag

    ## Returns the annotations
    def getData(self):
        pass

    ## Returns the key map, the known labels, their description and their toggle mode
    def getMeta(self):
        pass

    ## Set the key map, the known labels, their description and their toggle mode
    def setMeta(self, label, start, count):
        pass

    ## Filters key press / release events and controls the currrent labeling
    def processKeyPress(self, key):
        pass


    #def onAddKey(self):
    #    # get key and class from text forms
    #    key = self.keyEdit.text()
    #    cls = self.classEdit.text()

    #    # add it to the dictionary
    #    self.addKey(key, cls)

    #    # update the table
    #    self.updateTable()


    #def updateTable(self):
    #    self.keyTable.clearContents()
    #    self.keyTable.setRowCount(len(self.keys))

    #    for kv, i in zip(self.keys.iteritems(), range(len(self.keys))):
    #        self.keyTable.setItem(i, 0, QtGui.QTableWidgetItem(kv[0]))



if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    l = LiveAnnotation(sys.argv)
    l.show()
    app.exec_()
