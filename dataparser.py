import sys, select, time
from PyQt4 import QtCore, QtGui

class DataParser(QtCore.QObject):
    newData = QtCore.pyqtSignal(tuple)

    def __init__(self):
        super(DataParser, self).__init__()
        self.source = None
        self.fromFile = False
        self.lastProcTime = None
        self.period = 0
        self.deltaTimes = [0 for i in range(0,50)]
        self.meanDeltaTime = 0

        if len(sys.argv) > 1:
            print 'Reading sensor data from file.'
            self.source = open(sys.argv[1], 'r')
            self.fromFile = True
        else:
            self.source = sys.stdin
        self.timer = None


    ## Creates a QTimer that polls the source for data
    def start(self, locPeriod):
        self.period = locPeriod
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.processData)
        self.timer.start(self.period)


    ## Stop polling for data
    def stop(self):
        self.timer = []


    # get all available data from the source and emit signals
    def processData(self):
        # get data
        while self.fromFile or select.select([sys.stdin], [], [], 0)[0]:
            if self.lastProcTime is not None:
              newDeltaTime = time.time() - self.lastProcTime
              self.deltaTimes.append(newDeltaTime)
              del self.deltaTimes[0]
              self.meanDeltaTime = sum(self.deltaTimes) / len(self.deltaTimes)

            self.lastProcTime = time.time()

            line = self.source.readline()
            if line:
                # read space separated data fields
                fields = line.split(' ')
                nums = [float(i) for i in fields[1:]]
                data = (fields[0], nums)

                # emit signal
                self.newData.emit(data)
            else:
                print "Warning: No sample collected in this time frame. Getting out of sync."

            break


    ## Connect function to signal
    def connect(self, callback):
        self.newData.connect(callback)

thread = QtCore.QThread()
obj = DataParser()
obj.moveToThread(thread)
thread.start()
