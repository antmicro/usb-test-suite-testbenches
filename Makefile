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

TEST_SCRIPT= test-enum
TARGET = valentyusb

WPWD=$(shell sh -c 'pwd -W')
PWD=$(shell pwd)

ifeq ($(OS),Msys)
WPWD=$(shell sh -c 'pwd -W')
PYTHONPATH := $(PWD)/..;$(PYTHONPATH)
else
WPWD=$(shell pwd)
PYTHONPATH := $(PWD)/..:$(PYTHONPATH)
endif

VERILOG_SOURCES = $(WPWD)/dut.v $(WPWD)/tb.v
TOPLEVEL = tb

WRAPPER_SCRIPT = wrappers/generate_$(TARGET).py
MODULE = tests.$(TEST_SCRIPT)

CUSTOM_COMPILE_DEPS = $(PWD)/dut.v

include $(shell cocotb-config --makefiles)/Makefile.inc
include $(shell cocotb-config --makefiles)/Makefile.sim
include wrappers/Makefile.$(TARGET)

export TARGET_CONFIG = configs/$(TARGET)_descriptors.json
export TARGET

$(PWD)/tb.v: $(WPWD)/wrappers/tb_$(TARGET).v
	cp $(WPWD)/wrappers/tb_$(TARGET).v ./tb.v

$(PWD)/dut.v: $(WRAPPER_SCRIPT) $(WPWD)/tb.v
	cd ..
	PYTHONPATH=../litex:../migen:../valentyusb:.. python3 $(WRAPPER_SCRIPT) $(TARGET_OPTIONS)
	mv build/gateware/dut.v .

$(PWD)/usb.vcd: $(PWD)/dut.v
	sed -i "s/dump.vcd/usb.vcd/g" tb.v
	sed -i "s/0, tb/0, usb_d_p, usb_d_n/g" tb.v
	make sim

$(PWD)/usb.pcap: $(PWD)/usb.vcd
	sigrok-cli -i usb.vcd -P 'usb_signalling:signalling=full-speed:dm=usb_d_n:dp=usb_d_p,usb_packet,usb_request' -l 4 -B usb_request=pcap > usb.pcap

decode: $(PWD)/tb.v $(PWD)/usb.pcap

clean/dut: dut.v
	rm dut.v

clean/decode:
	rm usb.vcd usb.pcap tb.v
