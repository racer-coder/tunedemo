# TuneDemo

This is an example of what a GUI for an engine management system could
include.  The main focus is around configurable tables.

* Every table can have any variable configured on either axis.  It is
  up to the EMS to provide a comprehensive list of variables, but
  ideally the output of any table should be available as a variable.

* Up to 24x20 tables are supproted in the GUI but it can easily be
  extended.  The in memory footprint limit is 255x255, but memory
  requirements go up drastically and the benfit diminishes with larger
  tables.  For comparison, Link G4+ supports up to 22x20 for the fuel
  and ignition tables, up to 16x11 for most dynamic tables (boost
  target, etc), and even smaller for some other fixed tables (I
  believe lambda is 14x10).

* Each table can optionally be linked to other values through
  interpolation or basic arithmetic.  For example, interpolated tables
  can be created by linking the interpolation value and the other
  table (0% = use table A, 100% = use table C, or anything inbetween.)
  Table outputs can just be added together, or you can use one table
  to add as a % to another table.

* Tables are dynamically allocated inside the tune.  In the demo there
  are 9000 bytes set aside for tables, and they are represented
  "reasonably" compactly - 2 bytes per bin, 12 bytes of overhead, plus
  data for the used dimensions only.  The demo supports 12-bit data
  fields for tables, making them even more compact than 2 byte tables.
  A 22x20 table can fit in 756 bytes, while a 16x13 table fits in 382
  bytes.  2 bytes are used in the main tune to point to the dynamic
  table.

* Basic math blocks are supported as well.  Up to 4 variables can be
  referenced in the equation, and as long as the output is listed as a
  variable, it can be used as an axis in any table.

* The configuration and tune are stored together in one file, to avoid
  the need to make project directories, to ease working off line, and
  to ease sharing maps.

* In memory, the tune is stored in the binary format, so
  encoding/decoding is already handled.  There is no undo support yet,
  or ability to communicate with real hardware.

A basic demo is in config.json; it includes flex fuel support using an
ethanol sensor and engine coolant temp compensation, all done using
user configurable tables (i.e. the EMS has no notion of flex fuel or
compensations).  I'm not saying this is ideal, but it goes to show
what is capable using a GUI to configure.

To run the demo, you need python3 and PyQt5.  On Ubuntu 18.04, you can
run:
`apt install python3-pyqt5`
`./tunedemo.py`

The configuration/tune file `config.json` will be loaded and
displayed.  Updates can be saved using the `File/Save` menu.  The
included file `variables.json` is a more human readable version of the
configuration; it does not include any tune data.

For those that just want to see it without installing it:

![Screenshot of flex fuel / ECT compensation tune](/screenshot.png)
