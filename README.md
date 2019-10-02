# usb-test-suite-testbenches

This repository contains test and wrapper scripts for USB IP cores implemented using cocotb and [cocotb_usb](https://github.com/antmicro/usb-test-suite-cocotb-usb).

## Setup
You can use [parent repository](https://github.com/antmicro/usb-test-suite-build) to ensure correct folder structure is maintained.

### Prerequisites
* Migen
* LiteX
* LiteDRAM

* iverilog
* python3 and pip
* cocotb
* cocotb_usb package

## Usage
Execution is controlled by Makefile. To execute tests with default values, use:

```
make sim
```
Test output is saved to `results.xml` file. Signal states are stored in `dump.vcd`.

Basic options that can be set:
* `TEST_SCRIPT` - name of script from the *tests* directory to be executed, without `.py` extension.
* `TARGET` - IP core to be tested. Currently `valentyusb` and `usb1device` are supported.
* `TARGET_OPTIONS` - if some can be used in the wrapper script.

Other makefile targets:
* `decode` - export USB transactions to a `usb.pcap` file to be viewed i.e. in Wireshark

