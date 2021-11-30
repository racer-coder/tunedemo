#!/usr/bin/env python3

# Copyright 2021 Scott Smith
#
# This file is part of TuneDemo.
#
# TuneDemo is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# TuneDemo is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with TuneDemo.  If not, see <https://www.gnu.org/licenses/>.

# works on Ubuntu 18.04
# apt install python3-pyqt5


import config

import binascii
import json
import re
import socket
import struct
from PyQt5.QtCore import Qt, QEvent, QModelIndex, pyqtSignal

from PyQt5.QtGui import (
    QPainter,
    QStandardItem,
    QStandardItemModel,
    QValidator,
)
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMdiArea,
    QMdiSubWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


def closure(func, *args, **kwargs):
    return lambda *ev: func(*ev, *args, **kwargs)

# from StackOverflow, but now I forget how I found it
class VerticalLabel(QLabel):
    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.translate(0, self.sizeHint().height())
        painter.rotate(270)
        painter.drawText(0, 0, self.sizeHint().height(), self.sizeHint().width(),
                         self.alignment(), self.text())

    def minimumSizeHint(self):
        return super().minimumSizeHint().transposed()

    def sizeHint(self):
        return super().sizeHint().transposed()

class WidgetTrapClose(QWidget):
    def __init__(self, parent, name):
        super().__init__()
        self.parent = parent
        self.name = name

    def closeEvent(self, event):
        del self.parent.conditionalPages[self.name]
        super().closeEvent(event)

def FormatNumber(num, exp):
    return ("%." + str(max(-exp, 0)) + "f") % num

class ScalarValidator(QValidator):
    def __init__(self, prec):
        super().__init__()
        self.prec = prec

    def validate(self, txt, pos):
        try:
            f = float(txt)
        except:
            return (QValidator.Intermediate, txt, pos)
        if txt == self.fixup(txt):
            return (QValidator.Acceptable, txt, pos)
        return (QValidator.Intermediate, txt, pos)

    def fixup(self, txt):
        try:
            v = float(txt)
        except:
            return "0"
        v = round(v * 10 ** -self.prec) * 10 ** self.prec
        return FormatNumber(v, self.prec)

class VariableButton(QPushButton):
    varChange = pyqtSignal(object)

    def __init__(self, parent_panel, chooser_title, short_name, extra_vars=[]):
        super().__init__(parent_panel.getNiceVariableName(short_name, extra_vars))
        self.parent_panel = parent_panel
        self.chooser_title = chooser_title
        self.short_name = short_name
        self.extra_vars = extra_vars
        self.clicked.connect(self.chooseVar)

    def chooseVar(self, ev):
        name = self.parent_panel.variableChooser(self.chooser_title, self.short_name,
                                                 self.extra_vars)
        if name != self.short_name:
            self.short_name = name
            self.setText(self.parent_panel.getNiceVariableName(name, self.extra_vars))
            self.varChange.emit(name)

class EditPanel(QMainWindow):
    def __init__(self):
        super(EditPanel, self).__init__()

        with open('config.json', 'rt') as f:
            data = json.load(f)
        self.config = config.Config(data['config'])
        self.tune = self.config.Encode(data['tune'])

        layout = QHBoxLayout()
        mainSizer = QSplitter(Qt.Horizontal)

        self.conditional = {}
        self.conditionalPages = {}
        self.menutext = []

        # XXX disable menu items based on expression
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        self.buildTree(tree.invisibleRootItem(), self.config.menu)
        tree.itemDoubleClicked.connect(self.menuPress)
        mainSizer.addWidget(tree)

        self.mdi = QMdiArea()
        mainSizer.addWidget(self.mdi)

        layout.addWidget(mainSizer)
        mainwidget = QWidget()
        mainwidget.setLayout(layout)
        self.setCentralWidget(mainwidget)
        self.setWindowTitle("TuneDemo");

        menuBar = self.menuBar()

        fileMenu = menuBar.addMenu('File')
        act = QAction('Save', self)
        act.triggered.connect(self.save)
        fileMenu.addAction(act)

        ecuMenu = menuBar.addMenu('ECU')
        ecuMenu.addAction(QAction('Store', self))

    def save(self):
        data = self.config.Decode(self.tune)
        with open('config.json', 'wt') as f:
            json.dump(data, f, indent=2)

    def updateConditional(self):
        for v in self.conditional.values():
            en = self.config.EvalConditional(self.tune, v[0])
            if en != v[1]:
                v[1] = en
                if v[2]:
                    v[2].setDisabled(not en)
        for v in self.conditionalPages.values():
            for n, w in v:
                w.setDisabled(not self.conditional[n][1])

    def buildTree(self, root, menus):
        for m in menus:
            if m[0] == 'submenu':
                item = QTreeWidgetItem(root, [self.getTextSubst(m[1])])
                if '$' in m[1]:
                    self.menutext.append((m[1], item))
                self.buildTree(item, m[2:])
            elif m[0] =='page' or m[0] == 'table':
                item = QTreeWidgetItem(root, [self.getTextSubst(m[1])])
                if '$' in m[1]:
                    self.menutext.append((m[1], item))
                item.setData(1, Qt.EditRole, m)
                if m[0] == 'page':
                    for f in m[2:]:
                        var = self.config.all_fields[f[2]]
                        if type(var.conditional) is str:
                            en = self.config.EvalConditional(self.tune, var.conditional)
                            self.conditional[var.short_name] = [var.conditional, en, None]
                elif m[0] == 'table':
                    pass
                if type(m[-1]) is str:
                    en = self.config.EvalConditional(self.tune, m[-1])
                    self.conditional[m[2]] = [m[-1], en, item]
                    item.setDisabled(not en)
            else:
                print("Unhandled field type: ", m[0])

    def menuPress(self, item):
        name = item.data(0, Qt.EditRole)
        newpanel = item.data(1, Qt.EditRole)
        if not newpanel: return
        if newpanel[1] in self.conditionalPages:
            # Bring to foreground
            return
        dia = QMdiSubWindow()
        dia.setWindowTitle(name)
        self.conditionalPages[newpanel[1]] = []
        panel = WidgetTrapClose(self, newpanel[1])
        dia.setWidget(panel)
        self.createDialog(panel, newpanel)
        self.mdi.addSubWindow(dia)
        dia.show()

    def setField(self, txt, fld):
        print("Setting %s to %s" % (fld, txt))
        self.config.all_fields[fld].set(self.tune, self.config, txt)
        self.updateConditional()
        self.updateMenuText(fld)

    def setFieldLineEdit(self, widget, field, conv):
        self.setField(conv(widget.text()), field)

    def updateMenuText(self, fld):
        for txt, item in self.menutext:
            if txt.endswith('$' + fld):
                item.setText(0, self.getTextSubst(txt))

    def getTextSubst(self, txt):
        v = txt.split('$')
        if len(v) > 1 and self.config.all_fields[v[1]].get(self.tune) != '':
            return v[0] + ' - ' + self.config.all_fields[v[1]].get(self.tune)
        else:
            return v[0]

    def addVarsToTree(self, tree, vars, search):
        ret = None
        root_items = {}
        for v, ref in vars:
            if '$' in v:
                v = self.getTextSubst(v)
            v = v.split('::')
            parent = tree.invisibleRootItem()
            if len(v) > 1:
                if v[0] not in root_items:
                    item = QTreeWidgetItem(parent, [v[0]])
                    item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                    root_items[v[0]] = item
                parent = root_items[v[0]]
            item = QTreeWidgetItem(parent, [v[-1]])
            item.setData(1, Qt.EditRole, ref)
            if ref == search:
                ret = item
        if ret:
            tree.setCurrentItem(ret)

    def createDialog(self, gridpanel, newpanel):
        if newpanel[0] == 'page':
            gridsizer = QGridLayout()
            gridpanel.setLayout(gridsizer)
            row = 0
            for f in newpanel[2:]:
                label = QLabel(f[1])
                gridsizer.addWidget(label, row, 0)
                if f[0] == 'select':
                    edit = QComboBox()
                    edit.addItems(f[4])
                    edit.setCurrentText(self.config.all_fields[f[2]].get(self.tune))
                    edit.currentTextChanged.connect(closure(self.setField, f[2]))
                    gridsizer.addWidget(edit, row, 1, 1, 1)
                elif f[0] == 'scalar' or f[0] == 'text':
                    edit = QLineEdit()
                    if f[0] == 'scalar':
                        edit.setText(FormatNumber(self.config.all_fields[f[2]].get(self.tune),
                                                  self.config.all_fields[f[2]].exponent))
                        edit.setValidator(ScalarValidator(self.config.all_fields[f[2]].exponent))
                        edit.editingFinished.connect(closure(self.setFieldLineEdit,
                                                             edit, f[2], float))
                    else:
                        edit.setText(self.config.all_fields[f[2]].get(self.tune))
                        edit.editingFinished.connect(closure(self.setFieldLineEdit,
                                                             edit, f[2], str))
                    gridsizer.addWidget(edit, row, 1, 1, 1)
                elif f[0] == 'varselect':
                    edit = VariableButton(self, 'Variable for ' + f[1],
                                          self.config.all_fields[f[2]].get(self.tune, self.config))
                    edit.varChange.connect(closure(self.setField, f[2]))
                    gridsizer.addWidget(edit, row, 1, 1, 1)
                else:
                    print("Unknown field type", f[0])
                if type(f[-1]) is str:
                    self.conditionalPages[newpanel[1]].append((f[2], label))
                    self.conditionalPages[newpanel[1]].append((f[2], edit))
                    if not self.conditional[f[2]][1]:
                        label.setDisabled(True)
                        edit.setDisabled(True)
                row += 1
        elif newpanel[0] == 'table':
            tbl = self.config.all_tables[newpanel[2]]
            if tbl.TablePtr(self.tune) == 0:
                tbl.setTablePtr(self.tune, self.config.AllocateTable(self.tune, newpanel[2],
                                                                     0, None, [], 0, None, []))
            gridsizer = QGridLayout()
            gridpanel.setLayout(gridsizer)

            gridsizer.addWidget(QLabel(self.getTextSubst(newpanel[1])), 0, 1) # XXX dynamic update
            hunits = QLabel('')
            vunits = VerticalLabel('')
            vunits.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
            gridsizer.addWidget(hunits, 0, 2)
            gridsizer.addWidget(vunits, 1, 0)

            grid = QTableWidget(0, 0)
            self.UpdateGrid(tbl, grid, hunits, vunits)
            grid.setContextMenuPolicy(Qt.ActionsContextMenu)
            axisAction = QAction("Axis", grid)
            axisAction.triggered.connect(closure(self.setAxis, grid, newpanel[2], hunits, vunits))
            grid.addAction(axisAction)
            grid.cellChanged.connect(closure(self.updateCell, grid, newpanel[2]))
            gridsizer.addWidget(grid, 1, 1, 1, 2)

            buttonWidget = QWidget()
            buttonSizer = QHBoxLayout()
            buttonWidget.setLayout(buttonSizer)
            gridsizer.addWidget(buttonWidget, 2, 0, 1, 3)

            tableCombo = QComboBox()
            tableCombo.addItems(['None: A',
                                 'Interpolate: A + (C-A)*B%',
                                 'Add Percent: (100% + A%) * B',
                                 'Add: A + B',
                                 'Switch: A if B else C'])
            buttonSizer.addWidget(tableCombo)

            valueB = VariableButton(self, 'Variable for B',
                                    tbl.InterpolateVar(self.tune, self.config, 0))
            valueB.varChange.connect(lambda name: tbl.SetInterpolateVar(self.tune, self.config,
                                                                        0, name))
            buttonSizer.addWidget(valueB)

            valueC = VariableButton(self, 'Variable for C',
                                    tbl.InterpolateVar(self.tune, self.config, 1))
            valueC.varChange.connect(lambda name: tbl.SetInterpolateVar(self.tune, self.config,
                                                                        1, name))
            buttonSizer.addWidget(valueC)

            tableCombo.currentTextChanged.connect(
                lambda txt: (valueB.setDisabled('B' not in txt.split(':')[1]),
                             valueC.setDisabled('C' not in txt.split(':')[1]),
                             tbl.SetInterpolate(self.tune, tableCombo.currentIndex())))
            tableCombo.setCurrentIndex(tbl.Interpolate(self.tune))
            tableCombo.currentTextChanged.emit(tableCombo.currentText())


    def updateCell(self, row, col, grid, table_name):
        self.config.all_tables[table_name].setData(self.tune, row, col,
                                                   float(grid.item(row, col).text()))

    # extra_vars is a list of tuple(name, short_name)
    def variableChooser(self, title, current, extra_vars):
        dia = QDialog(self)
        dia.setWindowTitle(title)
        diasizer = QVBoxLayout()
        dia.setLayout(diasizer)

        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        self.addVarsToTree(tree,
                           extra_vars + [(v.name, v.short_name)
                                         for v in self.config.all_variables.values()],
                           current)

        diasizer.addWidget(tree)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        diasizer.addWidget(buttons)

        buttons.accepted.connect(dia.accept)
        buttons.rejected.connect(dia.reject)

        ret = dia.exec_()
        if ret:
            return tree.currentItem().data(1, Qt.EditRole)
        return current

    # extra_vars is a list of tuple(name, short_name)
    def getNiceVariableName(self, short_name, extra_vars):
        match = [v[0] for v in extra_vars if v[1] == short_name]
        if match: return match[0]
        if short_name in self.config.all_variables:
            return self.getTextSubst(self.config.all_variables[short_name].name.split('::')[-1])
        return self.config.all_variables[None].name

    def binChange(self, row, col, bins):
        vect = (0, 1) if bins.columnCount() > bins.rowCount() else (1, 0)
        size = max(bins.columnCount(), bins.rowCount())
        val = bins.item(row, col).text()
        vals = [bins.item(vect[0] * i, vect[1] * i) for i in range(size)]
        vals = [v.text() for v in vals if v]
        vals = [v for v in vals if v]
        vals.sort(key=float)
        for i in range(len(vals)):
            bins.item(vect[0] * i, vect[1] * i).setText(vals[i])
        for i in range(len(vals), size):
            bins.item(vect[0] * i, vect[1] * i).setText('')
        i = vals.index(val)
        bins.setCurrentCell(vect[0] * i, vect[1] * i)

    def setAxis(self, ev, grid, table_name, hunits, vunits):
        tbl = self.config.all_tables[table_name]

        dia = QDialog(self)
        dia.setWindowTitle("Axis configuration for " + self.getTextSubst(tbl.name))
        diasizer = QVBoxLayout()
        dia.setLayout(diasizer)

        hbox = QGroupBox("X axis")
        hboxsizer = QGridLayout()
        hbox.setLayout(hboxsizer)
        hboxsizer.addWidget(QLabel("Parameter"), 0, 0)
        xaxis = VariableButton(self, 'Variable for X axis',
                               tbl.AxisShortName(self.config, self.tune, 0))
        hboxsizer.addWidget(xaxis, 0, 1)
        xbins = QTableWidget(1, 24)
        xbins.verticalHeader().hide()
        xbins.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for i in range(24):
            xbins.setItem(0, i, QTableWidgetItem(''))
        for i, b in enumerate(tbl.AxisBins(self.tune, 0)):
            xbins.setItem(0, i,
                          QTableWidgetItem(FormatNumber(b, tbl.AxisExponent(self.tune, 0))))
        xbins.resizeColumnsToContents()
        xbins.resizeRowsToContents()
        xbins.setDisabled(not xaxis.short_name)
        xbins.cellChanged.connect(closure(self.binChange, xbins))
        xbins.setMinimumHeight(xbins.viewportSizeHint().height() + xbins.horizontalScrollBar().sizeHint().height())
        xbins.setMaximumHeight(xbins.viewportSizeHint().height() + xbins.horizontalScrollBar().sizeHint().height())
        hboxsizer.addWidget(xbins, 1, 0, 1, 2)
        diasizer.addWidget(hbox)
        xaxis.varChange.connect(lambda name: xbins.setDisabled(name is None))

        hbox = QGroupBox("Y axis")
        hboxsizer = QGridLayout()
        hbox.setLayout(hboxsizer)
        hboxsizer.addWidget(QLabel("Parameter"), 0, 0)
        yaxis = VariableButton(self, 'Variable for Y axis',
                               tbl.AxisShortName(self.config, self.tune, 1))
        hboxsizer.addWidget(yaxis, 0, 1)
        ybins = QTableWidget(20, 1)
        ybins.horizontalHeader().hide()
        for i in range(20):
            ybins.setItem(i, 0, QTableWidgetItem(''))
        for i, b in enumerate(tbl.AxisBins(self.tune, 1)):
            ybins.setItem(i, 0,
                          QTableWidgetItem(FormatNumber(b, tbl.AxisExponent(self.tune, 1))))
        ybins.resizeColumnsToContents()
        ybins.resizeRowsToContents()
        ybins.setDisabled(not yaxis.short_name)
        ybins.cellChanged.connect(closure(self.binChange, ybins))
        hboxsizer.addWidget(ybins, 1, 0, 1, 2)
        diasizer.addWidget(hbox)
        yaxis.varChange.connect(lambda name: ybins.setDisabled(name is None))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        diasizer.addWidget(buttons)

        buttons.accepted.connect(dia.accept)
        buttons.rejected.connect(dia.reject)

        if dia.exec_():
            interpolate = (tbl.Interpolate(self.tune),
                           tbl.InterpolateVar(self.tune, self.config, 0),
                           tbl.InterpolateVar(self.tune, self.config, 1))

            xitems = [xbins.item(0, c) for c in range(24)]
            xitems = [i.text() for i in xitems if i]
            xitems = [float(i) for i in xitems if i]
            xitems.sort()

            yitems = [ybins.item(r, 0) for r in range(20)]
            yitems = [i.text() for i in yitems if i]
            yitems = [float(i) for i in yitems if i]
            yitems.sort()

            tbl_ptr = self.config.AllocateTable(
                self.tune, table_name,
                0, xaxis.short_name, xitems if xaxis.short_name else [],
                0, yaxis.short_name, yitems if yaxis.short_name else [])

            # XXX PRESERVE OLD DATA, INTERPOLATE?

            tbl.setTablePtr(self.tune, tbl_ptr)

            tbl.SetInterpolate(self.tune, interpolate[0])
            tbl.SetInterpolateVar(self.tune, self.config, 0, interpolate[1])
            tbl.SetInterpolateVar(self.tune, self.config, 1, interpolate[2])

            self.UpdateGrid(tbl, grid, hunits, vunits)

    def UpdateGrid(self, tbl, grid, hunits, vunits):
        hbins = tbl.AxisBins(self.tune, 0)
        w = len(hbins) or 1
        grid.setColumnCount(w)
        if hbins:
            grid.setHorizontalHeaderLabels([FormatNumber(b, tbl.AxisExponent(self.tune, 0))
                                            for b in hbins])
            grid.horizontalHeader().show()
        else:
            grid.horizontalHeader().hide()

        vbins = tbl.AxisBins(self.tune, 1)
        h = len(vbins) or 1
        grid.setRowCount(h)
        if vbins:
            grid.setVerticalHeaderLabels([FormatNumber(b, tbl.AxisExponent(self.tune, 1))
                                          for b in vbins])
            grid.verticalHeader().show()
        else:
            grid.verticalHeader().hide()

        grid.resizeColumnsToContents()
        grid.resizeRowsToContents()

        hunits.setText(self.getNiceVariableName(tbl.AxisShortName(self.config, self.tune, 0),
                                                [('', None)]))
        vunits.setText(self.getNiceVariableName(tbl.AxisShortName(self.config, self.tune, 1),
                                                [('', None)]))

        for i in range(h):
            for j in range(w):
                grid.setItem(i, j, QTableWidgetItem(FormatNumber(tbl.Data(self.tune, i, j),
                                                                 tbl.exponent)))



def main():
    app = QApplication([])  # Create a new app, don't redirect stdout/stderr to a window.
    panel = EditPanel()
    panel.show()
    app.exec_()

main()
