# Generalized version of test-eptri script

from os import environ

import cocotb
from cocotb_usb.harness import get_harness
from cocotb_usb.device import UsbDevice
from cocotb_usb.usb.endpoint import *
from cocotb_usb.usb.pid import *
from cocotb_usb.usb.descriptors import *

descriptorFile = environ['TARGET_CONFIG']
model = UsbDevice(descriptorFile)

@cocotb.test()
def test_control_setup(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    # Device is at address 0 after reset
    yield harness.transaction_setup(0, [0x80, 0x06, 0x00, 0x06, 0x00, 0x00, 0x00, 0x00])
    yield harness.transaction_data_in(0, 0, [])

@cocotb.test()
def test_control_transfer_in(dut):
    harness = get_harness(dut)
    yield harness.reset()

    yield harness.connect()
    DEVICE_ADDRESS = 20
    yield harness.set_device_address(DEVICE_ADDRESS)
    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        getDescriptorRequest(descriptor_type=Descriptor.Types.STRING,
            descriptor_index=0,
            lang_id=0,
            length=10),
        model.stringDescriptorZero.get()
    )

def test_control_transfer_in_lazy(dut):
    """Test that we can transfer data in without immediately draining it"""
    epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)
    epaddr_in = EndpointType.epaddr(0, EndpointType.IN)

    harness = get_harness(dut)
    yield harness.reset()

    yield harness.connect()
    #yield harness.write(harness.csrs['usb_address'], 0)
    # Device is at address 0 after reset

    # Send a SETUP packet without draining it on the device side
    yield harness.host_send_token_packet(PID.SETUP, 0, epaddr_in)
    yield harness.host_send_data_packet(PID.DATA0, [0x80, 0x06, 0x00, 0x06, 0x00, 0x00, 0x0A, 0x00])
    yield harness.host_expect_ack()

    # Set it up so we ACK the final IN packet
    data = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
            0x08, 0x09, 0x0A, 0x0B]
 #   for b in data:
 #       yield harness.write(harness.csrs['usb_in_data'], b)
 #   yield harness.write(harness.csrs['usb_in_ctrl'], 0)

    # Send a few packets while we "process" the data as a slow host
    for i in range(10):
        yield harness.host_send_token_packet(PID.IN, 0, 0)
        yield harness.host_expect_data_packet()

    # Read the data, which should unblock the sending
    #setup_data = yield harness.drain_setup()
    #if len(setup_data) != 10:
    #    raise TestFailure("1. expected setup data to be 10 bytes, but was {} bytes: {}".format(len(setup_data), setup_data))

    # Perform the final "read"
    yield harness.host_recv(PID.DATA1, 0, 0, data)

    # Status stage
    yield harness.transaction_status_out(0, epaddr_out)


    # Set the address.  Again, don't drain the device side yet.
    yield harness.host_send_token_packet(PID.SETUP, 0, epaddr_out)
    yield harness.host_send_data_packet(PID.DATA0, [0x00, 0x05, 11, 0x00, 0x00, 0x00, 0x00, 0x00])
    yield harness.host_expect_ack()

    # Send a few packets while we "process" the data as a slow host
    for i in range(10):
        yield harness.host_send_token_packet(PID.IN, 0, 0)
        yield harness.host_expect_data_packet()

    #setup_data = yield harness.drain_setup()
    #if len(setup_data) != 10:
        #raise TestFailure("2. expected setup data to be 10 bytes, but was {} bytes: {}".format(len(setup_data), data, len(setup_data), len(setup_data) != 10))
    # Note: the `out` buffer hasn't been drained yet

    yield harness.host_send_token_packet(PID.IN, 0, 0)
    yield harness.host_expect_data_packet(PID.DATA1, [])
    yield harness.host_send_ack()

    for i in range(1532, 1541):
        yield harness.host_send_sof(i)

    # Send a SETUP packet to the wrong endpoint
    yield harness.host_send_token_packet(PID.SETUP, 11, epaddr_in)
    yield harness.host_send_data_packet(PID.DATA0, [0x80, 0x06, 0x00, 0x06, 0x00, 0x00, 0x0A, 0x00])
    # yield harness.host_expect_ack()

    #yield harness.write(harness.csrs['usb_address'], 11)

    # Send a SETUP packet without draining it on the device side
    yield harness.host_send_token_packet(PID.SETUP, 11, epaddr_in)
    yield harness.host_send_data_packet(PID.DATA0, [0x80, 0x06, 0x00, 0x06, 0x00, 0x00, 0x0A, 0x00])
    yield harness.host_expect_ack()

    # Set it up so we ACK the final IN packet
    data = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
            0x08, 0x09, 0x0A, 0x0B]
    #for b in data:
    #    yield harness.write(harness.csrs['usb_in_data'], b)
    #yield harness.write(harness.csrs['usb_in_ctrl'], 0)

    # Send a few packets while we "process" the data as a slow host
    for i in range(10):
        yield harness.host_send_token_packet(PID.IN, 11, 0)
        yield harness.host_expect_data_packet()

    # Read the data, which should unblock the sending
    #setup_data = yield harness.drain_setup()
    #if len(setup_data) != 10:
        #raise TestFailure("3. expected setup data to be 10 bytes, but was {} bytes: {}".format(len(setup_data), setup_data))

    # Perform the final send
    yield harness.host_send_token_packet(PID.IN, 11, 0)
    yield harness.host_expect_data_packet(PID.DATA1, data)
    yield harness.host_send_ack()

def test_control_transfer_in_large(dut):
    """Test that we can transfer data in without immediately draining it"""
    epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)
    epaddr_in = EndpointType.epaddr(0, EndpointType.IN)

    harness = get_harness(dut)
    yield harness.reset()

    yield harness.connect()

    DEVICE_ADDRESS = 11
    yield harness.set_device_address(DEVICE_ADDRESS)

    ### Send a packet that's longer than 64 bytes
    string_data = [
        0x4e, 0x3, 0x46, 0x0, 0x6f, 0x0, 0x6d, 0x0,
        0x75, 0x0, 0x20, 0x0, 0x44, 0x0, 0x46, 0x0,
        0x55, 0x0, 0x20, 0x0, 0x42, 0x0, 0x6f, 0x0,
        0x6f, 0x0, 0x74, 0x0, 0x6c, 0x0, 0x6f, 0x0,
        0x61, 0x0, 0x64, 0x0, 0x65, 0x0, 0x72, 0x0,
        0x20, 0x0, 0x76, 0x0, 0x31, 0x0, 0x2e, 0x0,
        0x38, 0x0, 0x2e, 0x0, 0x37, 0x0, 0x2d, 0x0,
        0x38, 0x0, 0x2d, 0x0, 0x67, 0x0, 0x31, 0x0,
        0x36, 0x0, 0x36, 0x0, 0x34, 0x0, 0x66, 0x0,
        0x33, 0x0, 0x35, 0x0, 0x0, 0x0
    ]

    # Send a SETUP packet without draining it on the device side
    yield harness.host_send_token_packet(PID.SETUP, 11, epaddr_in)
    yield harness.host_send_data_packet(PID.DATA0, [0x80, 0x06, 0x02, 0x03, 0x09, 0x04, 0xFF, 0x00])
    yield harness.host_expect_ack()
#    yield harness.drain_setup()

    # Send a few packets while we "process" the data as a slow host
    for i in range(10):
        yield harness.host_send_token_packet(PID.IN, 11, 0)
        yield harness.host_expect_ack()

    datax = PID.DATA1
    sent_data = 0
    for i, chunk in enumerate(grouper_tofit(64, string_data)):
        sent_data = 1
        harness.dut._log.debug("Actual data we're expecting: {}".format(chunk))
        #for b in chunk:
            #yield harness.write(harness.csrs['usb_in_data'], b)
        #yield harness.write(harness.csrs['usb_in_ctrl'], 0)
        recv = cocotb.fork(harness.host_recv(datax, 11, 0, chunk))
        yield recv.join()

        # Send a few packets while we "process" the data as a slow host
        for i in range(10):
            yield harness.host_send_token_packet(PID.IN, 11, 0)
            yield harness.host_expect_nak()

        if datax == PID.DATA0:
            datax = PID.DATA1
        else:
            datax = PID.DATA0
    if not sent_data:
        #yield harness.write(harness.csrs['usb_in_ctrl'], 0)
        recv = cocotb.fork(harness.host_recv(datax, 11, 0, []))
        yield harness.send_data(datax, 0, string_data)
        yield recv.join()

    yield harness.host_send_token_packet(PID.OUT, 11, 0)
    yield harness.host_send_data_packet(PID.DATA0, [])
    yield harness.host_expect_ack()

@cocotb.test()
def test_sof_stuffing(dut):
    harness = get_harness(dut)
    yield harness.reset()

    yield harness.connect()
    yield harness.host_send_sof(0x04ff)
    yield harness.host_send_sof(0x0512)
    yield harness.host_send_sof(0x06e1)
    yield harness.host_send_sof(0x0519)


@cocotb.test(expect_fail=True)
def test_sof_is_ignored(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    DEVICE_ADDRESS = 0x20
    epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)
    epaddr_in = EndpointType.epaddr(0, EndpointType.IN)
    yield harness.set_device_address(DEVICE_ADDRESS)

    data = [0, 1, 8, 0, 4, 3, 0, 0]
    # Send SOF packet
    yield harness.host_send_sof(2)

    # Setup stage
    # ------------------------------------------
    # Send SETUP packet
    yield harness.host_send_token_packet(PID.SETUP, DEVICE_ADDRESS, EndpointType.epnum(epaddr_out))

    # Send another SOF packet
    yield harness.host_send_sof(3)

    # Data stage
    # ------------------------------------------
    # Send DATA packet
    yield harness.host_send_data_packet(PID.DATA1, data)
    yield harness.host_expect_ack()

    # Send another SOF packet
    yield harness.host_send_sof(4)

    # # Status stage
    # # ------------------------------------------
    yield harness.transaction_status_out(DEVICE_ADDRESS, epaddr_out)

@cocotb.test(expect_fail=True)
def test_control_setup_clears_stall(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    addr = 0
    epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)

    d = [0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0, 0]

    # send the data -- just to ensure that things are working
    yield harness.transaction_data_out(addr, epaddr_out, d)

    # send it again to ensure we can re-queue things.
    yield harness.transaction_data_out(addr, epaddr_out, d)

    # stall the endpoint now
    # Promise we won't send data...
    yield harness.transaction_setup(0, [0x80, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00])
    #... then send it anyway
    yield harness.transaction_data_out(0, 0, [1, 2, 3], expected=PID.STALL)

    # do another receive, which should fail
    yield harness.transaction_data_out(addr, epaddr_out, d, expected=PID.STALL)

    # do a setup, which should pass
    yield harness.control_transfer_out(addr, d)

    # finally, do one last transfer, which should succeed now
    # that the endpoint is unstalled.
    yield harness.transaction_data_out(addr, epaddr_out, d)

@cocotb.test()
def test_control_transfer_in_out(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    DEVICE_ADDRESS = 20
    yield harness.set_device_address(DEVICE_ADDRESS)

    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        # Get device descriptor
        getDescriptorRequest(Descriptor.Types.DEVICE,
            descriptor_index=0,
            lang_id=0,
            length=0x40),
        model.deviceDescriptor.get()
    )

    yield harness.set_device_address(11) # This utilizes an OUT control transfer

@cocotb.test()
def test_control_transfer_in_out_in(dut):
    """This transaction is pretty much the first thing any OS will do"""
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    device_address = 0 # After reset
    yield harness.control_transfer_in(
        device_address,
        # Get device descriptor
        getDescriptorRequest(Descriptor.Types.DEVICE,
            descriptor_index=0,
            lang_id=0,
            length=0x40),
        model.deviceDescriptor.get()
    )

    device_address = 11
    yield harness.set_device_address(device_address) # This utilizes an OUT control transfer

    yield harness.control_transfer_in(
        device_address,
        # Get device descriptor
        getDescriptorRequest(Descriptor.Types.DEVICE,
            descriptor_index=0,
            lang_id=0,
            length=0x40),
        model.deviceDescriptor.get()
    )

@cocotb.test()
def test_control_transfer_out_in(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    DEVICE_ADDRESS = 20
    yield harness.set_device_address(DEVICE_ADDRESS) # This utilizes an OUT control transfer

    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        # Get device descriptor
        getDescriptorRequest(Descriptor.Types.DEVICE,
            descriptor_index=0,
            lang_id=0,
            length=0x40),
        model.deviceDescriptor.get()
    )

