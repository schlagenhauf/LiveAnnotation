#!/usr/bin/env python

import sys
from PyQt4 import QtCore, QtGui, uic
import pyqtgraph as pg
from pyqtgraph.ptime import time
from pyqtgraph.parametertree import Parameter, ParameterTree, ParameterItem, registerParameterType
import pyqtgraph.parametertree.parameterTypes as pTypes




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
        self.pmtree = ParameterTreeWidget(self.parameterView)

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


class ParameterTreeWidget:
    def __init__(self, parameterView):
        params = [
            {'name': 'Basic parameter data types', 'type': 'group', 'children': [
                {'name': 'Integer', 'type': 'int', 'value': 10},
                {'name': 'Float', 'type': 'float', 'value': 10.5, 'step': 0.1},
                {'name': 'String', 'type': 'str', 'value': "hi"},
                {'name': 'List', 'type': 'list', 'values': [1,2,3], 'value': 2},
                {'name': 'Named List', 'type': 'list', 'values': {"one": 1, "two": 2, "three": 3}, 'value': 2},
                {'name': 'Boolean', 'type': 'bool', 'value': True, 'tip': "This is a checkbox"},
                {'name': 'Color', 'type': 'color', 'value': "FF0", 'tip': "This is a color button"},
                {'name': 'Subgroup', 'type': 'group', 'children': [
                    {'name': 'Sub-param 1', 'type': 'int', 'value': 10},
                    {'name': 'Sub-param 2', 'type': 'float', 'value': 1.2e6},
                ]},
                {'name': 'Text Parameter', 'type': 'text', 'value': 'Some text...'},
                {'name': 'Action Parameter', 'type': 'action'},
            ]},
            {'name': 'Numerical Parameter Options', 'type': 'group', 'children': [
                {'name': 'Units + SI prefix', 'type': 'float', 'value': 1.2e-6, 'step': 1e-6, 'siPrefix': True, 'suffix': 'V'},
                {'name': 'Limits (min=7;max=15)', 'type': 'int', 'value': 11, 'limits': (7, 15), 'default': -6},
                {'name': 'DEC stepping', 'type': 'float', 'value': 1.2e6, 'dec': True, 'step': 1, 'siPrefix': True, 'suffix': 'Hz'},

            ]},
            {'name': 'Save/Restore functionality', 'type': 'group', 'children': [
                {'name': 'Save State', 'type': 'action'},
                {'name': 'Restore State', 'type': 'action', 'children': [
                    {'name': 'Add missing items', 'type': 'bool', 'value': True},
                    {'name': 'Remove extra items', 'type': 'bool', 'value': True},
                ]},
            ]},
            {'name': 'Extra Parameter Options', 'type': 'group', 'children': [
                {'name': 'Read-only', 'type': 'float', 'value': 1.2e6, 'siPrefix': True, 'suffix': 'Hz', 'readonly': True},
                {'name': 'Renamable', 'type': 'float', 'value': 1.2e6, 'siPrefix': True, 'suffix': 'Hz', 'renamable': True},
                {'name': 'Removable', 'type': 'float', 'value': 1.2e6, 'siPrefix': True, 'suffix': 'Hz', 'removable': True},
            ]},
            ComplexParameter(name='Custom parameter group (reciprocal values)'),
            ScalableGroup(name="Expandable Parameter Group", children=[
                {'name': 'ScalableParam 1', 'type': 'str', 'value': "default param 1"},
                {'name': 'ScalableParam 2', 'type': 'str', 'value': "default param 2"},
            ]),
        ]

        self.p = Parameter.create(name='params', type='group', children=params)

        self.p.param('Save/Restore functionality', 'Save State').sigActivated.connect(self.save)
        self.p.param('Save/Restore functionality', 'Restore State').sigActivated.connect(self.restore)

        self.t = parameterView # use the ID of the promoted graphicsView
        self.t.setParameters(self.p, showTop=False)
        self.t.show()
        self.t.resize(400,400)


    def save(self):
        self.state = self.p.saveState()

    def restore(self):
        add = self.p['Save/Restore functionality', 'Restore State', 'Add missing items']
        rem = self.p['Save/Restore functionality', 'Restore State', 'Remove extra items']
        self.p.restoreState(self.state, addChildren=add, removeChildren=rem)


class ComplexParameter(pTypes.GroupParameter):
    def __init__(self, **opts):
        opts['type'] = 'bool'
        opts['value'] = True
        pTypes.GroupParameter.__init__(self, **opts)

        self.addChild({'name': 'A = 1/B', 'type': 'float', 'value': 7, 'suffix': 'Hz', 'siPrefix': True})
        self.addChild({'name': 'B = 1/A', 'type': 'float', 'value': 1/7., 'suffix': 's', 'siPrefix': True})
        self.a = self.param('A = 1/B')
        self.b = self.param('B = 1/A')
        self.a.sigValueChanged.connect(self.aChanged)
        self.b.sigValueChanged.connect(self.bChanged)

    def aChanged(self):
        self.b.setValue(1.0 / self.a.value(), blockSignal=self.bChanged)

    def bChanged(self):
        self.a.setValue(1.0 / self.b.value(), blockSignal=self.aChanged)


class ScalableGroup(pTypes.GroupParameter):
    def __init__(self, **opts):
        opts['type'] = 'group'
        opts['addText'] = "Add"
        opts['addList'] = ['str', 'float', 'int']
        pTypes.GroupParameter.__init__(self, **opts)

    def addNew(self, typ):
        val = {
            'str': '',
            'float': 0.0,
            'int': 0
        }[typ]
        self.addChild(dict(name="ScalableParam %d" % (len(self.childs)+1), type=typ, value=val, removable=True, renamable=True))



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
        """
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
        """


    def setSource(self, source):
        pass




if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    la = LiveAnnotatorWin(sys.argv)
    la.show()
    app.exec_()
