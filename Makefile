###############################################################################
# Copyright (c) 2013, 2018 Potential Ventures Ltd
# Copyright (c) 2013 SolarFlare Communications Inc
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of Potential Ventures Ltd,
#       SolarFlare Communications Inc nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL POTENTIAL VENTURES LTD BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
###############################################################################

# Default to verilog
TOPLEVEL_LANG ?= verilog

WPWD=$(shell sh -c 'pwd -W')
PWD=$(shell pwd)

ifeq ($(OS),Msys)
WPWD=$(shell sh -c 'pwd -W')
PYTHONPATH := $(PWD)/..;$(PYTHONPATH)
else
WPWD=$(shell pwd)
PYTHONPATH := $(PWD)/..:$(PYTHONPATH)
endif

VERILOG_SOURCES = $(WPWD)/dut.v $(WPWD)/tb.v $(WPWD)/../tinyfpga/common/*.v
TOPLEVEL = tb
#MODULE = test-eptri
MODULE = test-enum
#MODULE = test-dummyusb

CUSTOM_COMPILE_DEPS = $(PWD)/dut.v

include $(shell cocotb-config --makefiles)/Makefile.inc
include $(shell cocotb-config --makefiles)/Makefile.sim

#$(PWD)/dut.v: generate_valentyusb.py
#	cd ..
#	PYTHONPATH=../litex:../migen:../litedram:../valentyusb:.. python3 generate_valentyusb.py eptri
#	mv build/gateware/dut.v .

$(PWD)/dut.v: generate_tinyfpgabl.py
	cd ..
	PYTHONPATH=../litex:../migen:../litedram:../tinyfpga:.. python3 generate_tinyfpgabl.py eptri
	mv build/gateware/dut.v .

#$(PWD)/dut.v: generate_verilog.py ../valentyusb/usbcore/cpu/dummyusb.py
#	cd ..
#	PYTHONPATH=../../litex:../../migen:../../litedram:.. python3 generate_verilog.py dummy
#	mv build/gateware/dut.v .
#	mv build/gateware/*.init .
