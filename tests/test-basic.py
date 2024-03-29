# BSD 3-Clause License
#
# Copyright (c) 2018, Luke Valenty
# Copyright (c) 2019 - 2021, Antmicro <www.antmicro.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Generalized version of test-eptri script

from os import environ

import cocotb
from cocotb.utils import get_sim_time
from cocotb_usb.harness import get_harness
from cocotb_usb.device import UsbDevice
from cocotb_usb.usb.endpoint import EndpointType
from cocotb_usb.usb.pid import PID
from cocotb_usb.descriptors import (Descriptor, getDescriptorRequest,
                                    FeatureSelector, USBDeviceRequest,
                                    setFeatureRequest)

descriptorFile = environ['TARGET_CONFIG']
model = UsbDevice(descriptorFile)


@cocotb.test()
def test_control_setup(dut):
    harness = get_harness(dut)
    harness.max_packet_size = model.deviceDescriptor.bMaxPacketSize0
    yield harness.reset()
    yield harness.wait(1e3, units="us")

    yield harness.port_reset(10e3)
    yield harness.connect()
    yield harness.wait(1e3, units="us")
    # After waiting (bus inactivity) let's start with SOF
    yield harness.host_send_sof(0x01)
    # Device is at address 0 after reset
    yield harness.transaction_setup(
        0,
        setFeatureRequest(FeatureSelector.ENDPOINT_HALT,
                          USBDeviceRequest.Type.ENDPOINT, 0))
    harness.packet_deadline = get_sim_time("us") + harness.MAX_PACKET_TIME
    yield harness.transaction_data_in(0, 0, [])


@cocotb.test()
def test_control_transfer_in(dut):
    harness = get_harness(dut)
    harness.max_packet_size = model.deviceDescriptor.bMaxPacketSize0
    yield harness.reset()
    yield harness.wait(1e3, units="us")

    yield harness.port_reset(10e3)
    yield harness.connect()
    yield harness.wait(1e3, units="us")
    # After waiting (bus inactivity) let's start with SOF
    yield harness.host_send_sof(0x01)
    DEVICE_ADDRESS = 20
    yield harness.set_device_address(DEVICE_ADDRESS)
    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        getDescriptorRequest(descriptor_type=Descriptor.Types.DEVICE,
                             descriptor_index=0,
                             lang_id=0,
                             length=18), model.deviceDescriptor.get())


@cocotb.test(expect_fail=True)
def test_invalid_request(dut):
    """Request invalid descriptor (Device with index 1)"""
    harness = get_harness(dut)
    harness.max_packet_size = model.deviceDescriptor.bMaxPacketSize0
    yield harness.reset()
    yield harness.wait(1e3, units="us")

    yield harness.port_reset(10e3)
    yield harness.connect()
    yield harness.wait(1e3, units="us")
    # After waiting (bus inactivity) let's start with SOF
    yield harness.host_send_sof(0x01)
    DEVICE_ADDRESS = 20
    yield harness.set_device_address(DEVICE_ADDRESS)
    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        getDescriptorRequest(descriptor_type=Descriptor.Types.DEVICE,
                             descriptor_index=1,
                             lang_id=0,
                             length=18), model.deviceDescriptor.get())


@cocotb.test(skip=True)  # Doesn't set STALL as expected
def test_control_setup_clears_stall(dut):
    harness = get_harness(dut)
    harness.max_packet_size = model.deviceDescriptor.bMaxPacketSize0
    yield harness.reset()
    yield harness.wait(1e3, units="us")

    yield harness.port_reset(10e3)
    yield harness.connect()
    yield harness.wait(1e3, units="us")
    # After waiting (bus inactivity) let's start with SOF
    yield harness.host_send_sof(0x01)

    addr = 13
    yield harness.set_device_address(addr)
    yield harness.set_configuration(1)
    yield harness.wait(1e2, units="us")

    epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)

    d = [0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0, 0]

    # send the data -- just to ensure that things are working
    yield harness.transaction_data_out(addr, epaddr_out, d)

    # send it again to ensure we can re-queue things.
    yield harness.transaction_data_out(addr, epaddr_out, d)

    # Set endpoint HALT explicitly
    yield harness.transaction_setup(
        addr,
        setFeatureRequest(FeatureSelector.ENDPOINT_HALT,
                          USBDeviceRequest.Type.ENDPOINT, 0))
    harness.packet_deadline = get_sim_time("us") + harness.MAX_PACKET_TIME
    yield harness.transaction_data_in(addr, 0, [])
    # do another receive, which should fail
    harness.retry = True
    harness.packet_deadline = get_sim_time("us") + 1e3  # try for a ms
    while harness.retry:
        yield harness.host_send_token_packet(PID.IN, addr, 0)
        yield harness.host_expect_stall()
        if get_sim_time("us") > harness.packet_deadline:
            raise cocotb.result.TestFailure("Did not receive STALL token")

    # do a setup, which should pass
    yield harness.get_device_descriptor(response=model.deviceDescriptor.get())

    # finally, do one last transfer, which should succeed now
    # that the endpoint is unstalled.
    yield harness.get_device_descriptor(response=model.deviceDescriptor.get())
