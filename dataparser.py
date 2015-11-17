import sys, select
from PyQt4 import QtCore, QtGui

class Signal(QtCore.QObject):
    newData = QtCore.pyqtSignal(tuple)

signal = Signal()
source = None
fromFile = False
if len(sys.argv) > 1:
    print 'Reading sensor data from file.'
    source = open(sys.argv[1], 'r')
    fromFile = True
else:
    source = sys.stdin
timer = None


## Creates a QTimer that polls the source for data
def start(period):
    global timer
    timer = QtCore.QTimer()
    timer.timeout.connect(processData)
    timer.start(period)


## Stop polling for data
def stop():
    timer = []


# get all available data from the source and emit signals
def processData():
    # get data
    while fromFile or select.select([sys.stdin], [], [], 0)[0]:
        line = source.readline()
        if line:
            # read space separated data fields
            fields = line.split(' ')
            nums = [float(i) for i in fields[1:]]
            data = (fields[0], nums)

            # emit signal
            signal.newData.emit(data)
        else:
            break


## Connect function to signal
def connect(callback):
    signal.newData.connect(callback)
