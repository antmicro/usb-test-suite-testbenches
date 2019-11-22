import cocotb

from cocotb_usb.harness import get_harness
from cocotb_usb.device import UsbDevice
from cocotb_usb.descriptors import Descriptor

from os import environ

descriptorFile = environ['TARGET_CONFIG']

DEVICE_ADDRESS = 20

model = UsbDevice(descriptorFile)


@cocotb.test()
def test_enumeration(dut):
    harness = get_harness(dut)
    harness.max_packet_size = model.deviceDescriptor.bMaxPacketSize0
    yield harness.reset()
    yield harness.wait(1e3, units="us")

    yield harness.port_reset(10e3)
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

    # Does the device report any string descriptors?
    str_to_check = []
    for idx in (
                model.deviceDescriptor.iManufacturer,
                model.deviceDescriptor.iProduct,
                model.deviceDescriptor.iSerialNumber):
        if idx != 0:
            str_to_check.append(idx)

    # If the device implements string descriptors, let's try reading them
    if str_to_check != []:
        yield harness.get_string_descriptor(
          lang_id=Descriptor.LangId.UNSPECIFIED,
          idx=0,
          response=model.stringDescriptor[0].get())

        lang_id = model.stringDescriptor[0].wLangId[0]
        for idx in str_to_check:
            yield harness.get_string_descriptor(
                lang_id=lang_id,
                idx=idx,
                response=model.stringDescriptor[lang_id][idx].get())

    yield harness.set_configuration(1)
    # Device should now be in "Configured" state
    # TODO: Class-specific config
