import cocotb

from cocotb_usb.harness import get_harness
from cocotb_usb.device import UsbDevice
from cocotb_usb.descriptors import Descriptor

from os import environ

descriptorFile = environ['TARGET_CONFIG']

DEVICE_ADDRESS = 5

model = UsbDevice(descriptorFile)


@cocotb.test()
def test_macos_enumeration(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    yield harness.wait(1e3, units="us")

    yield harness.port_reset(20e3)  # 20 ms
    yield harness.set_device_address(DEVICE_ADDRESS)
    yield harness.get_device_descriptor(response=model.deviceDescriptor.get())

    # If a device implements string descriptors, it must support ENG LangId
    LANG_ID = Descriptor.LangId.ENG

    for idx in (model.deviceDescriptor.iProduct,
                model.deviceDescriptor.iManufacturer,
                model.deviceDescriptor.iSerialNumber):
        if idx != 0:
            # Get first two bytes (to get length?)
            yield harness.get_string_descriptor(
                lang_id=LANG_ID,
                idx=idx,
                length=2,
                response=model.stringDescriptor[LANG_ID][idx].get()[:2])
            total_length = model.stringDescriptor[LANG_ID][idx].bLength
            # Read whole descriptor
            yield harness.get_string_descriptor(
                lang_id=Descriptor.LangId.ENG,
                idx=idx,
                length=total_length,
                response=model.stringDescriptor[LANG_ID][idx].get())

    yield harness.get_configuration_descriptor(
        length=9,
        # Device must implement at least one configuration
        response=model.configDescriptor[1].get()[:9])

    total_config_len = model.configDescriptor[1].wTotalLength
    yield harness.get_configuration_descriptor(
        length=total_config_len,
        response=model.configDescriptor[1].get()[:total_config_len])

    yield harness.set_configuration(1)
    # Device is in CONFIGURED state now

    # TODO: Class-specific config
