# Tests for the Fomu Tri-Endpoint
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, NullTrigger, Timer
from cocotb.result import TestFailure, TestSuccess, ReturnValue

from cocotb_usb.host import UsbTestValenty
from cocotb_usb.utils import grouper_tofit
from cocotb_usb.usb.endpoint import *
from cocotb_usb.usb.pid import *

dut_csrs = 'csr.csv'

@cocotb.test()
def iobuf_validate(dut):
    """Sanity test that the Wishbone bus actually works"""
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()

    USB_PULLUP_OUT = harness.csrs['usb_pullup_out']
    val = yield harness.read(USB_PULLUP_OUT)
    dut._log.info("Value at start: {}".format(val))
    if dut.usb_pullup != 0:
        raise TestFailure("USB pullup didn't start at zero")

    yield harness.write(USB_PULLUP_OUT, 1)

    val = yield harness.read(USB_PULLUP_OUT)
    dut._log.info("Memory value: {}".format(val))
    if val != 1:
        raise TestFailure("USB pullup is not set!")
    raise TestSuccess("iobuf validated")

@cocotb.test()
def test_control_setup(dut):
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()
    yield harness.connect()
    # We write to address 0, because we just want to test that the control
    # circuitry works.  Normally you wouldn't do this.
    yield harness.write(harness.csrs['usb_address'], 0)
    yield harness.transaction_setup(0, [0x80, 0x06, 0x00, 0x06, 0x00, 0x00, 0x00, 0x00])
    yield harness.transaction_data_in(0, 0, [])

@cocotb.test()
def test_control_transfer_in(dut):
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()

    yield harness.connect()
    yield harness.write(harness.csrs['usb_address'], 20)
    yield harness.control_transfer_in(
        20,
        # Get descriptor, Index 0, Type 03, LangId 0000, wLength 10?
        [0x80, 0x06, 0x00, 0x06, 0x00, 0x00, 0x0A, 0x00],
        # 12 byte descriptor, max packet size 8 bytes
        [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
            0x08, 0x09, 0x0A, 0x0B],
    )

@cocotb.test()
def test_control_transfer_in_lazy(dut):
    """Test that we can transfer data in without immediately draining it"""
    epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)
    epaddr_in = EndpointType.epaddr(0, EndpointType.IN)

    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()

    yield harness.connect()
    yield harness.write(harness.csrs['usb_address'], 0)

    # Send a SETUP packet without draining it on the device side
    yield harness.host_send_token_packet(PID.SETUP, 0, epaddr_in)
    yield harness.host_send_data_packet(PID.DATA0, [0x80, 0x06, 0x00, 0x06, 0x00, 0x00, 0x0A, 0x00])
    yield harness.host_expect_ack()

    # Set it up so we ACK the final IN packet
    data = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
            0x08, 0x09, 0x0A, 0x0B]
    for b in data:
        yield harness.write(harness.csrs['usb_in_data'], b)
    yield harness.write(harness.csrs['usb_in_ctrl'], 0)

    # Send a few packets while we "process" the data as a slow host
    for i in range(10):
        yield harness.host_send_token_packet(PID.IN, 0, 0)
        yield harness.host_expect_nak()

    # Read the data, which should unblock the sending
    setup_data = yield harness.drain_setup()
    if len(setup_data) != 10:
        raise TestFailure("1. expected setup data to be 10 bytes, but was {} bytes: {}".format(len(setup_data), setup_data))

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
        yield harness.host_expect_nak()

    setup_data = yield harness.drain_setup()
    if len(setup_data) != 10:
        raise TestFailure("2. expected setup data to be 10 bytes, but was {} bytes: {}".format(len(setup_data), data, len(setup_data), len(setup_data) != 10))
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

    yield harness.write(harness.csrs['usb_address'], 11)

    # Send a SETUP packet without draining it on the device side
    yield harness.host_send_token_packet(PID.SETUP, 11, epaddr_in)
    yield harness.host_send_data_packet(PID.DATA0, [0x80, 0x06, 0x00, 0x06, 0x00, 0x00, 0x0A, 0x00])
    yield harness.host_expect_ack()

    # Set it up so we ACK the final IN packet
    data = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
            0x08, 0x09, 0x0A, 0x0B]
    for b in data:
        yield harness.write(harness.csrs['usb_in_data'], b)
    yield harness.write(harness.csrs['usb_in_ctrl'], 0)

    # Send a few packets while we "process" the data as a slow host
    for i in range(10):
        yield harness.host_send_token_packet(PID.IN, 11, 0)
        yield harness.host_expect_nak()

    # Read the data, which should unblock the sending
    setup_data = yield harness.drain_setup()
    if len(setup_data) != 10:
        raise TestFailure("3. expected setup data to be 10 bytes, but was {} bytes: {}".format(len(setup_data), setup_data))

    # Perform the final send
    yield harness.host_send_token_packet(PID.IN, 11, 0)
    yield harness.host_expect_data_packet(PID.DATA1, data)
    yield harness.host_send_ack()


@cocotb.test()
def test_control_transfer_in_large(dut):
    """Test that we can transfer data in without immediately draining it"""
    epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)
    epaddr_in = EndpointType.epaddr(0, EndpointType.IN)

    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()

    yield harness.connect()
    yield harness.write(harness.csrs['usb_address'], 0)

    # Set address to 11
    yield harness.control_transfer_out(
        0,
        # Set address (to 11)
        [0x00, 0x05, 11, 0x00, 0x00, 0x00, 0x00, 0x00],
        # 18 byte descriptor, max packet size 8 bytes
        None,
    )
    yield harness.write(harness.csrs['usb_address'], 11)

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
    yield harness.drain_setup()

    # Send a few packets while we "process" the data as a slow host
    for i in range(10):
        yield harness.host_send_token_packet(PID.IN, 11, 0)
        yield harness.host_expect_nak()

    datax = PID.DATA1
    sent_data = 0
    for i, chunk in enumerate(grouper_tofit(64, string_data)):
        sent_data = 1
        harness.dut._log.debug("Actual data we're expecting: {}".format(chunk))
        for b in chunk:
            yield harness.write(harness.csrs['usb_in_data'], b)
        yield harness.write(harness.csrs['usb_in_ctrl'], 0)
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
        yield harness.write(harness.csrs['usb_in_ctrl'], 0)
        recv = cocotb.fork(harness.host_recv(datax, 11, 0, []))
        yield harness.send_data(datax, 0, string_data)
        yield recv.join()

    yield harness.host_send_token_packet(PID.OUT, 11, 0)
    yield harness.host_send_data_packet(PID.DATA0, [])
    yield harness.host_expect_ack()


@cocotb.test()
def test_sof_stuffing(dut):
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()

    yield harness.connect()
    yield harness.host_send_sof(0x04ff)
    yield harness.host_send_sof(0x0512)
    yield harness.host_send_sof(0x06e1)
    yield harness.host_send_sof(0x0519)

@cocotb.test()
def test_sof_is_ignored(dut):
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()
    yield harness.connect()

    addr = 0x20
    epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)
    epaddr_in = EndpointType.epaddr(0, EndpointType.IN)
    yield harness.write(harness.csrs['usb_address'], addr)

    data = [0, 1, 8, 0, 4, 3, 0, 0]
    @cocotb.coroutine
    def send_setup_and_sof():
        # Send SOF packet
        yield harness.host_send_sof(2)

        # Setup stage
        # ------------------------------------------
        # Send SETUP packet
        yield harness.host_send_token_packet(PID.SETUP, addr, EndpointType.epnum(epaddr_out))

        # Send another SOF packet
        yield harness.host_send_sof(3)

        # Data stage
        # ------------------------------------------
        # Send DATA packet
        yield harness.host_send_data_packet(PID.DATA1, data)
        yield harness.host_expect_ack()

        # Send another SOF packet
        yield harness.host_send_sof(4)

    # Indicate that we're ready to receive data to EP0
    # harness.write(harness.csrs['usb_in_ctrl'], 0)

    xmit = cocotb.fork(send_setup_and_sof())
    yield harness.expect_setup(epaddr_out, data)
    yield xmit.join()

    # # Status stage
    # # ------------------------------------------
    yield harness.set_response(epaddr_out, EndpointResponse.ACK)
    yield harness.transaction_status_out(addr, epaddr_out)

@cocotb.test()
def test_control_setup_clears_stall(dut):
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()
    yield harness.connect()

    addr = 28
    epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)
    yield harness.write(harness.csrs['usb_address'], addr)

    d = [0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0, 0]

    # Send the data -- just to ensure that things are working
    yield harness.transaction_data_out(addr, epaddr_out, d)

    # Send it again to ensure we can re-queue things.
    yield harness.transaction_data_out(addr, epaddr_out, d)

    # STALL the endpoint now
    yield harness.write(harness.csrs['usb_enable_out0'], 0)
    yield harness.write(harness.csrs['usb_enable_out1'], 0)
    yield harness.write(harness.csrs['usb_enable_in0'], 0)
    yield harness.write(harness.csrs['usb_enable_in1'], 0)

    # Do another receive, which should fail
    yield harness.transaction_data_out(addr, epaddr_out, d, expected=PID.STALL)

    # Do a SETUP, which should pass
    yield harness.write(harness.csrs['usb_enable_out0'], 1)
    yield harness.control_transfer_out(addr, d)

    # Finally, do one last transfer, which should succeed now
    # that the endpoint is unstalled.
    yield harness.transaction_data_out(addr, epaddr_out, d)

@cocotb.test()
def test_control_transfer_in_nak_data(dut):
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()
    yield harness.connect()

    addr = 22
    yield harness.write(harness.csrs['usb_address'], addr)
    # Get descriptor, Index 0, Type 03, LangId 0000, wLength 64
    setup_data = [0x80, 0x06, 0x00, 0x03, 0x00, 0x00, 0x40, 0x00]
    in_data = [0x04, 0x03, 0x09, 0x04]

    epaddr_in = EndpointType.epaddr(0, EndpointType.IN)
    # yield harness.clear_pending(epaddr_in)

    yield harness.write(harness.csrs['usb_address'], addr)

    # Setup stage
    # -----------
    yield harness.transaction_setup(addr, setup_data)

    # Data stage
    # -----------
    yield harness.set_response(epaddr_in, EndpointResponse.NAK)
    yield harness.host_send_token_packet(PID.IN, addr, epaddr_in)
    yield harness.host_expect_nak()

    yield harness.set_data(epaddr_in, in_data)
    yield harness.set_response(epaddr_in, EndpointResponse.ACK)
    yield harness.host_send_token_packet(PID.IN, addr, epaddr_in)
    yield harness.host_expect_data_packet(PID.DATA1, in_data)
    yield harness.host_send_ack()

# @cocotb.test()
# def test_control_transfer_in_nak_status(dut):
#     harness = UsbTestValenty(dut, dut_csrs)
#     yield harness.reset()
#     yield harness.connect()

#     addr = 20
#     setup_data = [0x00, 0x06, 0x00, 0x06, 0x00, 0x00, 0x0A, 0x00]
#     out_data = [0x00, 0x01]

#     epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)
#     epaddr_in = EndpointType.epaddr(0, EndpointType.IN)
#     yield harness.clear_pending(epaddr_out)
#     yield harness.clear_pending(epaddr_in)

#     # Setup stage
#     # -----------
#     yield harness.transaction_setup(addr, setup_data)

#     # Data stage
#     # ----------
#     yield harness.set_response(epaddr_out, EndpointResponse.ACK)
#     yield harness.transaction_data_out(addr, epaddr_out, out_data)

#     # Status stage
#     # ----------
#     yield harness.set_response(epaddr_in, EndpointResponse.NAK)

#     yield harness.host_send_token_packet(PID.IN, addr, epaddr_in)
#     yield harness.host_expect_nak()

#     yield harness.host_send_token_packet(PID.IN, addr, epaddr_in)
#     yield harness.host_expect_nak()

#     yield harness.set_response(epaddr_in, EndpointResponse.ACK)
#     yield harness.host_send_token_packet(PID.IN, addr, epaddr_in)
#     yield harness.host_expect_data_packet(PID.DATA1, [])
#     yield harness.host_send_ack()
#     yield harness.clear_pending(epaddr_in)


@cocotb.test()
def test_control_transfer_in(dut):
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()
    yield harness.connect()

    yield harness.clear_pending(EndpointType.epaddr(0, EndpointType.OUT))
    yield harness.clear_pending(EndpointType.epaddr(0, EndpointType.IN))
    yield harness.write(harness.csrs['usb_address'], 20)
    yield harness.host_send_sof(0)

    yield harness.control_transfer_in(
        20,
        # Get descriptor, Index 0, Type 03, LangId 0000, wLength 10?
        [0x80, 0x06, 0x00, 0x06, 0x00, 0x00, 0x0A, 0x00],
        # 12 byte descriptor, max packet size 8 bytes
        [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
            0x08, 0x09, 0x0A, 0x0B],
    )

@cocotb.test()
def test_control_transfer_in_out(dut):
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()
    yield harness.connect()

    yield harness.clear_pending(EndpointType.epaddr(0, EndpointType.OUT))
    yield harness.clear_pending(EndpointType.epaddr(0, EndpointType.IN))
    yield harness.write(harness.csrs['usb_address'], 20)

    yield harness.control_transfer_in(
        20,
        # Get device descriptor
        [0x80, 0x06, 0x00, 0x01, 0x00, 0x00, 0x40, 00],
        # 18 byte descriptor, max packet size 8 bytes
        [0x12, 0x01, 0x10, 0x02, 0x02, 0x00, 0x00, 0x40,
            0x09, 0x12, 0xB1, 0x70, 0x01, 0x01, 0x01, 0x02,
            00, 0x01],
    )

    yield harness.control_transfer_out(
        20,
        # Set address (to 11)
        [0x00, 0x05, 0x0B, 0x00, 0x00, 0x00, 0x00, 0x00],
        # 18 byte descriptor, max packet size 8 bytes
        None,
    )


@cocotb.test()
def test_control_transfer_in_out_in(dut):
    """This transaction is pretty much the first thing any OS will do"""
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()
    yield harness.connect()

    yield harness.clear_pending(EndpointType.epaddr(0, EndpointType.OUT))
    yield harness.clear_pending(EndpointType.epaddr(0, EndpointType.IN))
    yield harness.write(harness.csrs['usb_address'], 0)

    yield harness.control_transfer_in(
        0,
        # Get device descriptor
        [0x80, 0x06, 0x00, 0x01, 0x00, 0x00, 0x40, 00],
        # 18 byte descriptor, max packet size 8 bytes
        [0x12, 0x01, 0x10, 0x02, 0x02, 0x00, 0x00, 0x40,
         0x09, 0x12, 0xB1, 0x70, 0x01, 0x01, 0x01, 0x02,
         00, 0x01],
    )

    yield harness.control_transfer_out(
        0,
        # Set address (to 11)
        [0x00, 0x05, 11, 0x00, 0x00, 0x00, 0x00, 0x00],
        # 18 byte descriptor, max packet size 8 bytes
        None,
    )

    yield harness.write(harness.csrs['usb_address'], 11)

    yield harness.control_transfer_in(
        11,
        # Get device descriptor
        [0x80, 0x06, 0x00, 0x01, 0x00, 0x00, 0x40, 00],
        # 18 byte descriptor, max packet size 8 bytes
        [0x12, 0x01, 0x10, 0x02, 0x02, 0x00, 0x00, 0x40,
         0x09, 0x12, 0xB1, 0x70, 0x01, 0x01, 0x01, 0x02,
         00, 0x01],
    )

@cocotb.test()
def test_control_transfer_out_in(dut):
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()
    yield harness.connect()

    yield harness.clear_pending(EndpointType.epaddr(0, EndpointType.OUT))
    yield harness.clear_pending(EndpointType.epaddr(0, EndpointType.IN))
    yield harness.write(harness.csrs['usb_address'], 0)

    yield harness.control_transfer_out(
        0,
        # Set address (to 20)
        [0x00, 0x05, 20, 0x00, 0x00, 0x00, 0x00, 0x00],
        # 18 byte descriptor, max packet size 8 bytes
        None,
    )

    yield harness.write(harness.csrs['usb_address'], 20)

    yield harness.control_transfer_in(
        20,
        # Get device descriptor
        [0x80, 0x06, 0x00, 0x01, 0x00, 0x00, 0x40, 00],
        # 18 byte descriptor, max packet size 8 bytes
        [0x12, 0x01, 0x10, 0x02, 0x02, 0x00, 0x00, 0x40,
            0x09, 0x12, 0xB1, 0x70, 0x01, 0x01, 0x01, 0x02,
            00, 0x01],
    )

# @cocotb.test()
# def test_control_transfer_out_nak_data(dut):
#     harness = UsbTestValenty(dut, dut_csrs)
#     yield harness.reset()
#     yield harness.connect()

#     addr = 20
#     setup_data = [0x80, 0x06, 0x00, 0x06, 0x00, 0x00, 0x0A, 0x00]
#     out_data = [
#         0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
#         0x08, 0x09, 0x0A, 0x0B,
#     ]

#     epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)
#     yield harness.clear_pending(epaddr_out)

#     # Setup stage
#     # -----------
#     yield harness.transaction_setup(addr, setup_data)

#     # Data stage
#     # ----------
#     yield harness.set_response(epaddr_out, EndpointResponse.NAK)
#     yield harness.host_send_token_packet(PID.OUT, addr, epaddr_out)
#     yield harness.host_send_data_packet(PID.DATA1, out_data)
#     yield harness.host_expect_nak()

#     yield harness.host_send_token_packet(PID.OUT, addr, epaddr_out)
#     yield harness.host_send_data_packet(PID.DATA1, out_data)
#     yield harness.host_expect_nak()

#     #for i in range(200):
#     #    yield

#     yield harness.set_response(epaddr_out, EndpointResponse.ACK)
#     yield harness.host_send_token_packet(PID.OUT, addr, epaddr_out)
#     yield harness.host_send_data_packet(PID.DATA1, out_data)
#     yield harness.host_expect_ack()
#     yield harness.host_expect_data(epaddr_out, out_data)
#     yield harness.clear_pending(epaddr_out)

@cocotb.test()
def test_in_transfer(dut):
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()
    yield harness.connect()

    addr = 28
    epaddr = EndpointType.epaddr(1, EndpointType.IN)
    yield harness.write(harness.csrs['usb_address'], addr)

    d = [0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0x7, 0x8]

    yield harness.clear_pending(epaddr)
    yield harness.set_response(epaddr, EndpointResponse.NAK)

    yield harness.set_data(epaddr, d[:4])
    yield harness.set_response(epaddr, EndpointResponse.ACK)
    yield harness.host_send_token_packet(PID.IN, addr, epaddr)
    yield harness.host_expect_data_packet(PID.DATA1, d[:4])
    yield harness.host_send_ack()

    pending = yield harness.pending(epaddr)
    if pending:
        raise TestFailure("data was still pending")
    yield harness.clear_pending(epaddr)
    yield harness.set_data(epaddr, d[4:])
    yield harness.set_response(epaddr, EndpointResponse.ACK)

    yield harness.host_send_token_packet(PID.IN, addr, epaddr)
    yield harness.host_expect_data_packet(PID.DATA0, d[4:])
    yield harness.host_send_ack()

@cocotb.test()
def test_in_transfer_stuff_last(dut):
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()
    yield harness.connect()

    addr = 28
    epaddr = EndpointType.epaddr(1, EndpointType.IN)
    yield harness.write(harness.csrs['usb_address'], addr)

    d = [0x37, 0x75, 0x00, 0xe0]

    yield harness.clear_pending(epaddr)
    yield harness.set_response(epaddr, EndpointResponse.NAK)

    yield harness.set_data(epaddr, d)
    yield harness.set_response(epaddr, EndpointResponse.ACK)
    yield harness.host_send_token_packet(PID.IN, addr, epaddr)
    yield harness.host_expect_data_packet(PID.DATA1, d)

@cocotb.test()
def test_debug_in(dut):
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()
    yield harness.connect()

    addr = 28
    yield harness.write(harness.csrs['usb_address'], addr)
    # The "scratch" register defaults to 0x12345678 at boot.
    reg_addr = harness.csrs['ctrl_scratch']
    setup_data = [0xc3, 0x00,
                    (reg_addr >> 0) & 0xff,
                    (reg_addr >> 8) & 0xff,
                    (reg_addr >> 16) & 0xff,
                    (reg_addr >> 24) & 0xff, 0x04, 0x00]
    epaddr_in = EndpointType.epaddr(0, EndpointType.IN)
    epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)

    yield harness.transaction_data_in(addr, epaddr_in, [0x2, 0x4, 0x6, 0x8, 0xa], chunk_size=64)

    yield harness.clear_pending(epaddr_out)
    yield harness.clear_pending(epaddr_in)

    # Setup stage
    yield harness.host_send_token_packet(PID.SETUP, addr, epaddr_out)
    yield harness.host_send_data_packet(PID.DATA0, setup_data)
    yield harness.host_expect_ack()

    # Data stage
    yield harness.host_send_token_packet(PID.IN, addr, epaddr_in)
    yield harness.host_expect_data_packet(PID.DATA1, [0x12, 0, 0, 0])
    yield harness.host_send_ack()

    # Status stage
    yield harness.host_send_token_packet(PID.OUT, addr, epaddr_in)
    yield harness.host_send_data_packet(PID.DATA1, [])
    yield harness.host_expect_ack()

# @cocotb.test()
# def test_debug_in_missing_ack(dut):
#     harness = UsbTestValenty(dut, dut_csrs)
#     yield harness.reset()
#     yield harness.connect()

#     addr = 28
#     reg_addr = harness.csrs['ctrl_scratch']
#     setup_data = [0xc3, 0x00,
#                     (reg_addr >> 0) & 0xff,
#                     (reg_addr >> 8) & 0xff,
#                     (reg_addr >> 16) & 0xff,
#                     (reg_addr >> 24) & 0xff, 0x04, 0x00]
#     epaddr_in = EndpointType.epaddr(0, EndpointType.IN)
#     epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)

#     # Setup stage
#     yield harness.host_send_token_packet(PID.SETUP, addr, epaddr_out)
#     yield harness.host_send_data_packet(PID.DATA0, setup_data)
#     yield harness.host_expect_ack()

#     # Data stage (missing ACK)
#     yield harness.host_send_token_packet(PID.IN, addr, epaddr_in)
#     yield harness.host_expect_data_packet(PID.DATA1, [0x12, 0, 0, 0])

#     # Data stage
#     yield harness.host_send_token_packet(PID.IN, addr, epaddr_in)
#     yield harness.host_expect_data_packet(PID.DATA1, [0x12, 0, 0, 0])
#     yield harness.host_send_ack()

#     # Status stage
#     yield harness.host_send_token_packet(PID.OUT, addr, epaddr_out)
#     yield harness.host_send_data_packet(PID.DATA1, [])
#     yield harness.host_expect_ack()

@cocotb.test()
def test_debug_out(dut):
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()
    yield harness.connect()

    addr = 28
    yield harness.write(harness.csrs['usb_address'], addr)
    reg_addr = harness.csrs['ctrl_scratch']
    setup_data = [0x43, 0x00,
                    (reg_addr >> 0) & 0xff,
                    (reg_addr >> 8) & 0xff,
                    (reg_addr >> 16) & 0xff,
                    (reg_addr >> 24) & 0xff, 0x04, 0x00]
    ep0in_addr = EndpointType.epaddr(0, EndpointType.IN)
    ep1in_addr = EndpointType.epaddr(1, EndpointType.IN)
    ep0out_addr = EndpointType.epaddr(0, EndpointType.OUT)

    # Force Wishbone to acknowledge the packet
    yield harness.clear_pending(ep0out_addr)
    yield harness.clear_pending(ep0in_addr)
    yield harness.clear_pending(ep1in_addr)

    # Setup stage
    yield harness.host_send_token_packet(PID.SETUP, addr, ep0out_addr)
    yield harness.host_send_data_packet(PID.DATA0, setup_data)
    yield harness.host_expect_ack()

    # Data stage
    yield harness.host_send_token_packet(PID.OUT, addr, ep0out_addr)
    yield harness.host_send_data_packet(PID.DATA1, [0x42, 0, 0, 0])
    yield harness.host_expect_ack()

    # Status stage (wrong endopint)
    yield harness.host_send_token_packet(PID.IN, addr, ep1in_addr)
    yield harness.host_expect_nak()

    # Status stage
    yield harness.host_send_token_packet(PID.IN, addr, ep0in_addr)
    yield harness.host_expect_data_packet(PID.DATA1, [])
    yield harness.host_send_ack()

    new_value = yield harness.read(reg_addr)
    if new_value != 0x42:
        raise TestFailure("memory at 0x{:08x} should be 0x{:08x}, but memory value was 0x{:08x}".format(reg_Addr, 0x42, new_value))