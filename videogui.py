#!/usr/bin/env python


from PyQt4 import QtGui
from PyQt4 import QtCore
import video
import sys
import pygst
pygst.require("0.10")
import gst

"""
class VideoApp(QtGui.QMainWindow, design.Ui_MainWindow):
    def __init__(self):
        # QT Init
        super(self.__class__, self).__init__()
        self.setupUi(self)

        self.btnStart.clicked.connect(self.OnStart)
        self.btnStop.clicked.connect(self.OnStop)
        self.btnQuit.clicked.connect(self.OnQuit)

        # GStreamer init

        self.pipeline = gst.Pipeline("videocap")
        self.videosrc = gst.element_factory_make("v4l2src", "videosrc")
        self.pipeline.add(self.videosrc)
        self.sink = gst.element_factory_make("autovideosink", "sink")
        self.pipeline.add(self.sink)
        self.videosrc.link(self.sink)

        # Get frames
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        #bus.connect("message", self.OnMessage)
        bus.enable_sync_message_emission()
        #bus.connect("sync-message::element", self.OnSyncMessage)


    def OnMessage(self, bus, message):
        print message.structure.get_name()
        #t = message.type
        #if t == gst.MESSAGE_EOS:
        #    self.player.set_state(gst.STATE_NULL)
        #elif t == gst.MESSAGE_ERROR:
        #   err, debug = message.parse_error()
        #   print "Error: %s" % err, debug
        #   self.player.set_state(gst.STATE_NULL)

    def OnSyncMessage(self, bus, message):
        message_name = message.structure.get_name()
        print message_name
        #if message_name == "prepare-xwindow-id":
        #    win_id = self.windowId
        #    assert win_id
        #    imagesink = message.src
        #    imagesink.set_property("force-aspect-ratio", True)
        #    imagesink.set_xwindow_id(win_id)

    def OnStart(self, widget):
        print("play")
        self.pipeline.set_state(gst.STATE_PLAYING)

    def OnStop(self, widget):
        print("stop")
        self.pipeline.set_state(gst.STATE_READY)

    def OnQuit(self, widget):
        print("quit")
        sys.exit(1)
"""


class VideoApp(QtGui.QMainWindow, video.Ui_MainWindow):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)

        self.cameraWindow = QtGui.QWidget()
        self.cameraWindow.setGeometry(QtCore.QRect(530, 20, 256, 192))
        self.cameraWindow.setObjectName("cameraWindow")
        self.cameraWindow.setAttribute(0, 1); # AA_ImmediateWidgetCreation == 0
        #self.cameraWindow.setAttribute(3, 1); # AA_NativeWindow == 3

        self.wId = self.graphicsView.winId()
        self.camera = Vid(self.wId)
        #self.camera.startPrev()

        self.btnStart.clicked.connect(self.OnStart)
        self.btnStop.clicked.connect(self.OnStop)
        self.btnQuit.clicked.connect(self.OnQuit)

    def OnStart(self, widget):
        print("play")
        self.camera.startPrev()

    def OnStop(self, widget):
        print("stop")
        self.camera.pausePrev()

    def OnQuit(self, widget):
        print("quit")
        sys.exit(1)

class Vid:
    def __init__(self, windowId):
        self.player = gst.Pipeline("player")
        self.source = gst.element_factory_make("v4l2src", "vsource")
        self.sink = gst.element_factory_make("autovideosink", "outsink")
        self.source.set_property("device", "/dev/video0")
        #self.scaler = gst.element_factory_make("videoscale", "vscale")
        self.fvidscale = gst.element_factory_make("videoscale", "fvidscale")
        self.fvidscale_cap = gst.element_factory_make("capsfilter", "fvidscale_cap")
        self.fvidscale_cap.set_property('caps', gst.caps_from_string('video/x-raw-yuv, width=256, height=192'))
        self.windowId = windowId
        print windowId

        self.player.add(self.source, self.fvidscale, self.fvidscale_cap, self.sink)
        gst.element_link_many(self.source,self.fvidscale, self.fvidscale_cap, self.sink)

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)


    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.player.set_state(gst.STATE_NULL)
        elif t == gst.MESSAGE_ERROR:
           err, debug = message.parse_error()
           print "Error: %s" % err, debug
           self.player.set_state(gst.STATE_NULL)

    def on_sync_message(self, bus, message):
        print "bla2"
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            print "bla"
            win_id = self.windowId
            assert win_id
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            imagesink.set_xwindow_id(win_id)

    def startPrev(self):
        self.player.set_state(gst.STATE_PLAYING)

    def pausePrev(self):
        self.player.set_state(gst.STATE_NULL)



def main():
    app = QtGui.QApplication(sys.argv)
    form = VideoApp()
    form.show()
    app.exec_()


if __name__ == '__main__':  # if we're running file directly and not importing it
    main()  # run the main function
