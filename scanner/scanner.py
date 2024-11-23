import asyncio
import logging
import sys
import json

from bleak import BleakScanner
from bleak.assigned_numbers import AdvertisementDataType
from bleak.backends.bluezdbus.advertisement_monitor import OrPattern
from bleak.backends.bluezdbus.scanner import BlueZScannerArgs
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.uuids import normalize_uuid_16
from parser import BleParser
from bthome import parse_bthome

BTHOME_VID = 0xFCD2

logger = logging.getLogger(__name__)

# List of your own MAC addresses
DEVICES = ["AA:BB:CC:DD:EE:FF"]


def adv_callback(device: BLEDevice, advertisement_data: AdvertisementData):
    if normalize_uuid_16(BTHOME_VID) in advertisement_data.service_uuids:
        logger.info(
            f"{device.address} RSSI: {advertisement_data.rssi}, {advertisement_data}"
        )
        if device.address in DEVICES:
            data = b"\x00\x00\x00\x00" + advertisement_data.service_data.get(
                normalize_uuid_16(BTHOME_VID)
            )
            parser = BleParser()
            sensor_data = parse_bthome(
                parser,
                data,
                BTHOME_VID,
                bytearray.fromhex(device.address.replace(":", "")),
            )
            if sensor_data is not None:
                data_callback(sensor_data)


def data_callback(sensor_data):
    logger.info(json.dumps(sensor_data))
    # do stuff here with the decoded data


async def main(service_uuids):
    passive_filters = [
        OrPattern(0, AdvertisementDataType.SERVICE_DATA_UUID16, b"\xd2\xfc"),
    ]

    scanner = BleakScanner(
        detection_callback=adv_callback,
        scanning_mode="passive",
        bluez=BlueZScannerArgs(or_patterns=passive_filters),
    )

    await scanner.start()
    event = asyncio.Event()
    await event.wait()  # wait indefinitely


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )
    service_uuids = sys.argv[1:]
    asyncio.run(main(service_uuids))
