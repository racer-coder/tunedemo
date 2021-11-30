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



import struct

class Variable:
    def __init__(self, name, short_name, can_set, units, offset, encoding, exponent):
        self.name = name
        self.short_name = short_name
        self.can_set = can_set
        self.units = units
        self.offset = offset
        self.encoding = encoding
        self.exponent = exponent

class Scalar:
    def __init__(self, name, short_name, units, offset, encoding, exponent, conditional = None):
        self.name = name
        self.short_name = short_name
        self.units = units
        self.offset = offset
        self.encoding = encoding
        self.exponent = exponent
        self.conditional = conditional

        self.format = {
            2: 'H',
        }[encoding]

    def get(self, tune):
        return struct.unpack_from(self.format, tune, self.offset)[0] * 10 ** self.exponent

    def set(self, tune, conf, val):
        val *= 10 ** -self.exponent
        if self.format != 'f':
            val = int(val)
        struct.pack_into(self.format, tune, self.offset, val)

    def decode(self, tune, conf):
        return self.get(tune)

    def encode(self, tune, conf, val):
        self.set(tune, conf, val)

class Select:
    def __init__(self, name, short_name, offset, choices, conditional = None):
        self.name = name
        self.short_name = short_name
        self.offset = offset
        self.choices = choices
        self.conditional = conditional

    def get(self, tune):
        return self.choices[struct.unpack_from('B', tune, self.offset)[0]]

    def set(self, tune, conf, val):
        struct.pack_into('B', tune, self.offset, self.choices.index(val))

    def decode(self, tune, conf):
        return self.get(tune)

    def encode(self, tune, conf, val):
        self.set(tune, conf, val)

class VarSelect:
    def __init__(self, name, short_name, offset, conditional = None):
        self.name = name
        self.short_name = short_name
        self.offset = offset
        self.conditional = conditional

    def get(self, tune, conf):
        return conf.variables[struct.unpack_from('B', tune, self.offset)[0]]

    def set(self, tune, conf, val):
        struct.pack_into('B', tune, self.offset, conf.variables.index(val))

    def decode(self, tune, conf):
        return self.get(tune, conf)

    def encode(self, tune, conf, val):
        self.set(tune, conf, val)

class Text:
    def __init__(self, name, short_name, offset, length, conditional = None):
        self.name = name
        self.short_name = short_name
        self.offset = offset
        self.length = length
        self.conditional = conditional

    def get(self, tune):
        s = struct.unpack_from('%ds' % self.length, tune, self.offset)[0]
        return s.decode().split('\0')[0]

    def set(self, tune, conf, val):
        struct.pack_into('%ds' % self.length, tune, self.offset, val.encode())

    def decode(self, tune, conf):
        return self.get(tune)

    def encode(self, tune, conf, val):
        self.set(tune, conf, val)

class Table:
    def __init__(self, name, short_name, units, offset, encoding, exponent, conditional = None):
        self.name = name
        self.short_name = short_name
        self.units = units
        self.offset = offset
        self.encoding = encoding
        self.exponent = exponent
        self.conditional = conditional

    def Interpolate(self, tune):
        if not self.TablePtr(tune):
            return 0
        return struct.unpack_from('B', tune, self.TablePtr(tune))[0]

    def SetInterpolate(self, tune, intrp):
        if not self.TablePtr(tune):
            raise
        struct.pack_into('B', tune, self.TablePtr(tune), intrp)

    def InterpolateVar(self, tune, config, var):
        if not self.TablePtr(tune):
            return 0
        return config.variables[struct.unpack_from('B', tune, self.TablePtr(tune) + 1 + var)[0]]

    def SetInterpolateVar(self, tune, config, var, intrp):
        if not self.TablePtr(tune):
            raise
        struct.pack_into('B', tune, self.TablePtr(tune) + 1 + var, config.variables.index(intrp))

    def TablePtr(self, tune):
        return struct.unpack_from("H", tune, self.offset)[0]

    def setTablePtr(self, tune, ptr):
        struct.pack_into('H', tune, self.offset, ptr)

    def TableLen(self, tune):
        if not self.TablePtr(tune):
            return 0
        w = self.AxisNBins(tune, 0)
        h = self.AxisNBins(tune, 1)
        xsize = 4 + 4 + 2 * w
        ysize = 4 + 2 * h
        dsize = int(abs(self.encoding) * max(w, 1) * max(h, 1) + 1.9) & -2
        return xsize + ysize + dsize

    def AxisNBins(self, tune, axis):
        if not self.TablePtr(tune):
            return 0
        return struct.unpack_from('B', tune, self.AxisPtr(tune, axis))[0]

    def AxisPtr(self, tune, axis):
        ptr = self.TablePtr(tune)
        if axis:
            ptr += 4 + 2 * self.AxisNBins(tune, 0)
        return ptr + 4

    def AxisBins(self, tune, axis):
        if not self.TablePtr(tune):
            return []
        ptr = self.AxisPtr(tune, axis)
        nbins = self.AxisNBins(tune, axis)
        exp = 10 ** self.AxisExponent(tune, axis)
        return [exp * b for b in struct.unpack_from('%dh' % nbins, tune, ptr + 4)]

    def AxisExponent(self, tune, axis):
        if not self.TablePtr(tune):
            return 0
        return struct.unpack_from('b', tune, self.AxisPtr(tune, axis) + 1)[0]

    def AxisShortName(self, config, tune, axis):
        if self.AxisNBins(tune, axis) == 0: return None
        return config.variables[struct.unpack_from('H', tune, self.AxisPtr(tune, axis) + 2)[0]]

    def DataPtr(self, tune, r, c):
        w = self.AxisNBins(tune, 0)
        h = self.AxisNBins(tune, 1)
        ptr = self.TablePtr(tune) + 12 + 2 * (w + h)
        w = w or 1
        rem = int(8 * abs(self.encoding))
        ptr = ptr * 8 + rem * (r * w + c)
        bit = ptr % 8
        ptr >>= 3
        return (ptr, bit, rem)

    def Data(self, tune, r, c):
        if not self.TablePtr(tune):
            return 0
        ptr, bit, rem = self.DataPtr(tune, r, c)
        val = 0
        shift = 0
        while rem > 0:
            val |= (tune[ptr] >> bit) << shift
            shift += 8 - bit
            rem -= 8 - bit
            bit = 0
            ptr += 1
        span = 1 << int(abs(self.encoding) * 8)
        val &= span - 1
        if self.encoding < 0 and (val & (span >> 1)):
            val -= span
        return val * 10 ** self.exponent

    def setData(self, tune, r, c, val):
        if not self.TablePtr(tune):
            return
        span = 1 << int(abs(self.encoding) * 8)
        val = int(round(val * 10 ** -self.exponent)) & (span - 1)
        ptr, bit, rem = self.DataPtr(tune, r, c)
        while rem > 0:
            tune[ptr] = (tune[ptr] & ((1 << bit) - 1)) | (val << bit)
            val >>= 8 - bit
            rem -= 8 - bit
            bit = 0
            ptr += 1

    def decode_axis(self, tune, conf, axis):
        if self.AxisNBins(tune, axis) == 0: return None
        return [self.AxisShortName(conf, tune, axis),
                self.AxisExponent(tune, axis),
                *self.AxisBins(tune, axis)]

    def decode_data(self, tune):
        w = self.AxisNBins(tune, 0) or 1
        h = self.AxisNBins(tune, 1) or 2
        return [[self.Data(tune, r, c) for c in range(w)]
                for r in range(h)]

    def decode(self, tune, conf):
        if not self.TablePtr(tune):
            return None
        return {
            'interpolate': self.Interpolate(tune),
            'interpolate-B': self.InterpolateVar(tune, conf, 0),
            'interpolate-C': self.InterpolateVar(tune, conf, 1),
            'x-axis': self.decode_axis(tune, conf, 0),
            'y-axis': self.decode_axis(tune, conf, 1),
            'data': self.decode_data(tune)
            }

    def encode(self, tune, conf, val):
        if val is None:
            return
        tbl = conf.AllocateTable(tune, self.short_name,
                                 val['x-axis'][1] if val['x-axis'] else 0,
                                 val['x-axis'][0] if val['x-axis'] else None,
                                 val['x-axis'][2:] if val['x-axis'] else [],
                                 val['y-axis'][1] if val['y-axis'] else 0,
                                 val['y-axis'][0] if val['y-axis'] else None,
                                 val['y-axis'][2:] if val['y-axis'] else [])
        self.setTablePtr(tune, tbl)
        self.SetInterpolate(tune, val['interpolate'])
        self.SetInterpolateVar(tune, conf, 0, val['interpolate-B'])
        self.SetInterpolateVar(tune, conf, 1, val['interpolate-C'])
        w = self.AxisNBins(tune, 0) or 1
        h = self.AxisNBins(tune, 1) or 2
        for r in range(h):
            for c in range(w):
                self.setData(tune, r, c, val['data'][r][c])


class_map = {
    'scalar': Scalar,
    'select': Select,
    'table': Table,
    'text': Text,
    'varselect': VarSelect,
}

class Config:
    def __init__(self, variables):
        self.conf = variables
        self.menu = variables['fields']
        self.table_offset = variables['table_offset']
        self.total_size = variables['total_size']
        self.variables = [v[1] for v in variables['variables']] # index to short_name
        self.all_variables = {} # map short_name to Variable
        self.all_tables = {} # map short_name to Table
        self.all_fields = {} # map short_name to Table, Scalar, Select, or Text

        for v in variables['variables']:
            c = Variable(*v)
            self.all_variables[c.short_name] = c

        for m in variables['fields']:
            self.ProcessMenu(m)

    def Decode(self, tune):
        return {'config': self.conf,
                'tune': dict([(f.short_name, f.decode(tune, self))
                              for f in self.all_fields.values()])}

    def Encode(self, data):
        tune = bytearray(self.total_size)
        for name, val in data.items():
            self.all_fields[name].encode(tune, self, val)
        return tune

    def ProcessMenu(self, menu):
        if menu[0] == 'submenu' or menu[0] == 'page':
            for m in menu[2:]:
                self.ProcessMenu(m)
        else:
            c = class_map[menu[0]](*menu[1:])
            self.all_fields[c.short_name] = c
            if menu[0] == 'table':
                self.all_tables[c.short_name] = c

    def EvalConditional(self, tune, cond):
        class M:
            def __init__(self, conf, tune):
                self.conf = conf
                self.tune = tune

            def __getitem__(self, x):
                return self.conf.all_fields[x].get(self.tune)
        return eval(cond, {}, M(self, tune))

    def GetFreeTableSpace(self, tune):
        used = [(t.TablePtr(tune), t.TableLen(tune))
                for t in self.all_tables.values()
                if t.TableLen(tune) != 0]
        used.sort()
        used = [(self.table_offset, 0)] + used + [(self.total_size, 0)]
        print("GetFreeTableSpace", used)
        return [(a[0] + a[1], b[0])
                for a, b in zip(used[:-1], used[1:])
                if a[0] + a[1] != b[0]]

    def TotalFreeTableSpace(self, tune):
        return sum([e-b for b, e in self.GetFreeTableSpace(tune)])

    def AllocateTable(self, tune, table_name, xexp, xvar_name, xbins, yexp, yvar_name, ybins):
        xsize = 8 + 2 * len(xbins)
        ysize = 4 + 2 * len(ybins)
        dsize = int(abs(self.all_tables[table_name].encoding) *
                    max(len(xbins), 1) * max(len(ybins), 1) + 1.9) & -2
        tsize = xsize + ysize + dsize
        ret = bytearray(tsize)
        struct.pack_into("BBBBBbH%dh" % len(xbins), ret, 0,
                         0, 0, 0, 0,
                         len(xbins), xexp, self.variables.index(xvar_name),
                         *[int(round(b * 10 ** -xexp)) for b in xbins])
        struct.pack_into("BbH%dh" % len(ybins), ret, xsize,
                         len(ybins), yexp, self.variables.index(yvar_name),
                         *[int(round(b * 10 ** -yexp)) for b in ybins])
        for b, e in self.GetFreeTableSpace(tune):
            if e - b >= tsize:
                print("Allocated table %s at %d-%d" % (table_name, b, b+tsize))
                tune[b : b+tsize] = ret
                return b
        return None # not enough memory available
