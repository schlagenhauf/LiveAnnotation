#!/usr/bin/env python



from PyQt4 import QtGui
import design
import sys
import pygst
pygst.require("0.10")
import gst


class GStreamerApp(QtGui.QMainWindow, design.Ui_MainWindow):
    def __init__(self):
        # QT Init
        super(self.__class__, self).__init__()
        self.setupUi(self)

        self.btnStart.clicked.connect(self.OnStart)
        self.btnStop.clicked.connect(self.OnStop)
        self.btnQuit.clicked.connect(self.OnQuit)

        # GStreamer init

        self.pipeline = gst.Pipeline("mypipeline")
        self.audiotestsrc = gst.element_factory_make("audiotestsrc", "audio")
        self.audiotestsrc.set_property("freq", 440)
        self.pipeline.add(self.audiotestsrc)
        self.sink = gst.element_factory_make("alsasink", "sink")
        self.pipeline.add(self.sink)
        self.audiotestsrc.link(self.sink)

    def OnStart(self, widget):
        print("play")
        self.pipeline.set_state(gst.STATE_PLAYING)

    def OnStop(self, widget):
        print("stop")
        self.pipeline.set_state(gst.STATE_READY)

    def OnQuit(self, widget):
        print("quit")
        sys.exit(1)


def main():
    app = QtGui.QApplication(sys.argv)
    form = GStreamerApp()
    form.show()
    app.exec_()


if __name__ == '__main__':  # if we're running file directly and not importing it
    main()  # run the main function
