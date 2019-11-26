import cocotb
from cocotb.triggers import Timer

from cocotb_usb.harness import get_harness
from cocotb_usb.device import UsbDevice
from cocotb_usb.descriptors.cdc import (setLineCoding, setControlLineState,
                                        getLineCoding, LineCodingStructure)

from os import environ

descriptorFile = environ['TARGET_CONFIG']

DEVICE_ADDRESS = 20

model = UsbDevice(descriptorFile)


@cocotb.test()
def test_tinyfpgabl_cdc_transfer(dut):
    harness = get_harness(dut)
    harness.max_packet_size = model.deviceDescriptor.bMaxPacketSize0
    yield harness.reset()
    yield harness.wait(1e3, units="us")

    dut._log.info("[Enumerating device]")

    yield harness.port_reset(1e3)
    yield harness.connect()
    yield harness.wait(1e3, units="us")
    # After waiting (bus inactivity) let's start with SOF
    yield harness.host_send_sof(0x01)
    yield harness.get_device_descriptor(response=model.deviceDescriptor.get())

    yield harness.set_device_address(DEVICE_ADDRESS)
    # There is a longish recovery period after setting address, so let's send
    # a SOF to make sure DUT doesn't suspend
    yield harness.host_send_sof(0x02)
    yield harness.get_configuration_descriptor(
        length=9,
        # Device must implement at least one configuration
        response=model.configDescriptor[1].get()[:9])

    total_config_len = model.configDescriptor[1].wTotalLength
    yield harness.get_configuration_descriptor(
        length=total_config_len,
        response=model.configDescriptor[1].get()[:total_config_len])

    yield harness.set_configuration(1)
    # Device should now be in "Configured" state

    INTERFACE = 1
    # Values from TinyFPGA-Bootloader ep_rom
    line_coding = LineCodingStructure(9600,
                                      LineCodingStructure.STOP_BITS_1_5,
                                      LineCodingStructure.PARITY_NONE,
                                      LineCodingStructure.DATA_BITS_8)

    dut._log.info("[Getting line coding]")
    yield harness.control_transfer_in(
            DEVICE_ADDRESS,
            getLineCoding(INTERFACE),
            line_coding.get())

    line_coding.dwDTERate = 115200
    line_coding.bCharFormat = LineCodingStructure.STOP_BITS_1
    dut._log.info("[Setting line coding]")
    yield harness.control_transfer_out(
            DEVICE_ADDRESS,
            setLineCoding(INTERFACE),
            line_coding.get())

    dut._log.info("[Setting control line state]")
    yield harness.control_transfer_out(
            DEVICE_ADDRESS,
            setControlLineState(
                interface=0,
                rts=1,
                dtr=1),
            None)

    BOOT_OPCODE = 0x00
    EP_ADDRESS = 0x01
    dut._log.info("[Sending BOOT op code]")
    yield harness.transaction_data_out(DEVICE_ADDRESS,
                                       EP_ADDRESS,
                                       [BOOT_OPCODE])

    yield Timer(1e2, "us")  # Wait and see if it "boots"
    boot = int(dut.dut.tinyfpga_bootloader.boot_to_user_design)
    dut._log.info(f"Boot line state: {boot}")
