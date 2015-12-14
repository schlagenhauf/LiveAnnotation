#!/usr/bin/env python

from PyQt4 import QtCore, QtGui, uic
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui


import pyqtgraph.parametertree.parameterTypes as pTypes
from pyqtgraph.parametertree import Parameter, ParameterTree, ParameterItem, registerParameterType

import sys



form_class = uic.loadUiType("pmtree.ui")[0]

class ParameterTreeWin(QtGui.QMainWindow, form_class):
    def __init__(self, args, parent=None):
        QtGui.QMainWindow.__init__(self,parent)
        self.setupUi(self)

        self.pt = ParameterTreeWidget(self.parameterView)

        # connect elements
        #self.btnPlay.clicked.connect(self.vid.play)

class ParameterTreeWidget:
    def __init__(self, winId):
        params = [
            {'name': 'Basic parameter data types', 'type': 'group', 'children': [
                {'name': 'Integer', 'type': 'int', 'value': 10},
                {'name': 'Float', 'type': 'float', 'value': 10.5, 'step': 0.1},
                {'name': 'String', 'type': 'str', 'value': "hi"},
                {'name': 'List', 'type': 'list', 'values': [1,2,3], 'value': 2},
                {'name': 'Named List', 'type': 'list', 'values': {"one": 1, "two": "twosies", "three": [3,3,3]}, 'value': 2},
                {'name': 'Boolean', 'type': 'bool', 'value': True, 'tip': "This is a checkbox"},
                {'name': 'Color', 'type': 'color', 'value': "FF0", 'tip': "This is a color button"},
                {'name': 'Gradient', 'type': 'colormap'},
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
        self.p.sigTreeStateChanged.connect(self.change)
        self.p.param('Save/Restore functionality', 'Save State').sigActivated.connect(self.save)
        self.p.param('Save/Restore functionality', 'Restore State').sigActivated.connect(self.restore)

        self.t = ParameterTree(winId)
        self.t.setParameters(self.p, showTop=False)
        #self.t.setWindowTitle('pyqtgraph example: Parameter Tree')


    def change(self, param, changes):
        print("tree changes:")
        for param, change, data in changes:
            path = self.p.childPath(param)
            if path is not None:
                childName = '.'.join(path)
            else:
                childName = param.name()
            print('  parameter: %s'% childName)
            print('  change:    %s'% change)
            print('  data:      %s'% str(data))
            print('  ----------')

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


## test save/restore
#s = p.saveState()
#p.restoreState(s)


if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    pmt = ParameterTreeWin(sys.argv)
    pmt.show()
    app.exec_()
