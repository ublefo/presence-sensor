"""Parser for passive BLE advertisements."""
import logging
from typing import Optional

from bthome import parse_bthome
from helpers import to_mac, to_unformatted_mac, to_uuid

_LOGGER = logging.getLogger(__name__)


class BleParser:
    """Parser for BLE advertisements"""
    def __init__(
        self,
        report_unknown=False,
        discovery=True,
        filter_duplicates=False,
        sensor_whitelist=None,
        tracker_whitelist=None,
        report_unknown_whitelist=None,
        aeskeys=None
    ):
        self.report_unknown = report_unknown
        self.discovery = discovery
        self.filter_duplicates = filter_duplicates
        if sensor_whitelist is None:
            self.sensor_whitelist = []
        else:
            self.sensor_whitelist = sensor_whitelist
        if tracker_whitelist is None:
            self.tracker_whitelist = []
        else:
            self.tracker_whitelist = tracker_whitelist
        if report_unknown_whitelist is None:
            self.report_unknown_whitelist = []
        else:
            self.report_unknown_whitelist = report_unknown_whitelist
        if aeskeys is None:
            self.aeskeys = {}
        else:
            self.aeskeys = aeskeys

        self.lpacket_ids = {}
        self.movements_list = {}
        self.adv_priority = {}
        self.no_key_message = []

    def parse_raw_data(self, data):
        """Parse the raw data."""
        # check if packet is Extended scan result
        is_ext_packet = True if data[3] == 0x0D else False
        # check for no BR/EDR + LE General discoverable mode flags
        adpayload_start = 29 if is_ext_packet else 14
        # https://www.silabs.com/community/wireless/bluetooth/knowledge-base.entry.html/2017/02/10/bluetooth_advertisin-hGsf
        try:
            adpayload_size = data[adpayload_start - 1]
        except IndexError:
            return None, None
        # check for BTLE msg size
        msg_length = data[2] + 3
        if (
            msg_length <= adpayload_start or msg_length != len(data) or msg_length != (
                adpayload_start + adpayload_size + (0 if is_ext_packet else 1)
            )
        ):
            return None, None
        # extract RSSI byte
        rssi_index = 18 if is_ext_packet else msg_length - 1
        rssi = data[rssi_index]
        # strange positive RSSI workaround
        if rssi > 127:
            rssi = rssi - 256
        # MAC address
        mac = (data[8 if is_ext_packet else 7:14 if is_ext_packet else 13])[::-1]
        complete_local_name = ""
        shortened_local_name = ""
        service_class_uuid16 = None
        service_class_uuid128 = None
        service_data_list = []
        man_spec_data_list = []

        while adpayload_size > 1:
            adstuct_size = data[adpayload_start] + 1
            if adstuct_size > 1 and adstuct_size <= adpayload_size:
                adstruct = data[adpayload_start:adpayload_start + adstuct_size]
                # https://www.bluetooth.com/specifications/assigned-numbers/generic-access-profile/
                adstuct_type = adstruct[1]
                if adstuct_type == 0x02:
                    # AD type 'Incomplete List of 16-bit Service Class UUIDs'
                    service_class_uuid16 = (adstruct[2] << 8) | adstruct[3]
                elif adstuct_type == 0x03:
                    # AD type 'Complete List of 16-bit Service Class UUIDs'
                    service_class_uuid16 = (adstruct[2] << 8) | adstruct[3]
                elif adstuct_type == 0x06:
                    # AD type '128-bit Service Class UUIDs'
                    service_class_uuid128 = adstruct[2:]
                elif adstuct_type == 0x08:
                    # AD type 'shortened local name'
                    try:
                        shortened_local_name = adstruct[2:].decode("utf-8")
                    except UnicodeDecodeError:
                        shortened_local_name = ""
                elif adstuct_type == 0x09:
                    # AD type 'complete local name'
                    try:
                        complete_local_name = adstruct[2:].decode("utf-8")
                    except UnicodeDecodeError:
                        complete_local_name = ""
                elif adstuct_type == 0x16 and adstuct_size > 4:
                    # AD type 'Service Data - 16-bit UUID'
                    service_data_list.append(adstruct)
                elif adstuct_type == 0xFF:
                    # AD type 'Manufacturer Specific Data'
                    man_spec_data_list.append(adstruct)
                    # https://www.bluetooth.com/specifications/assigned-numbers/company-identifiers/
            adpayload_size -= adstuct_size
            adpayload_start += adstuct_size

        if complete_local_name:
            local_name = complete_local_name
        else:
            local_name = shortened_local_name

        sensor_data, tracker_data = self.parse_advertisement(
            mac,
            rssi,
            service_class_uuid16,
            service_class_uuid128,
            local_name,
            service_data_list,
            man_spec_data_list
        )
        return sensor_data, tracker_data

    def parse_advertisement(
            self,
            mac: bytes,
            rssi: int,
            service_class_uuid16: Optional[int] = None,
            service_class_uuid128: Optional[bytes] = None,
            local_name: Optional[str] = "",
            service_data_list: Optional[list] = None,
            man_spec_data_list: Optional[list] = None
    ):
        """parse BLE advertisement"""
        sensor_data = {}
        tracker_data = {}
        uuid = None
        unknown_sensor = False
        if service_data_list is None:
            service_data_list = []
        if man_spec_data_list is None:
            man_spec_data_list = []

        while not sensor_data:
            if service_data_list:
                for service_data in service_data_list:
                    # parse data for sensors with service data
                    uuid16 = (service_data[3] << 8) | service_data[2]
                    if uuid16 in [0x181C, 0x181E]:
                        # UUID16 = User Data and Bond Management (used by BTHome)
                        sensor_data = parse_bthome(self, service_data, uuid16, mac)
                        break
                    elif uuid16 == 0xFCD2:
                        # UUID16 = Allterco Robotics ltd (BTHome V2)
                        sensor_data = parse_bthome(self, service_data, uuid16, mac)
                        break
                    else:
                        unknown_sensor = True
            else:
                unknown_sensor = True
            if unknown_sensor and self.report_unknown == "Other":
                _LOGGER.info(
                    "Unknown advertisement received for mac: %s"
                    "service data: %s"
                    "manufacturer specific data: %s"
                    "local name: %s"
                    "UUID16: %s,"
                    "UUID128: %s",
                    to_mac(mac),
                    service_data_list,
                    man_spec_data_list,
                    local_name,
                    service_class_uuid16,
                    service_class_uuid128,
                )
            break

        # Ignore sensor data for MAC addresses not in sensor whitelist, when discovery is disabled
        if self.discovery is False and mac not in self.sensor_whitelist:
            _LOGGER.debug("Discovery is disabled. MAC: %s is not whitelisted!", to_mac(mac))
            sensor_data = None
        # Ignore sensor data for UUID not in sensor whitelist, when discovery is disabled
        if self.discovery is False and uuid and uuid not in self.sensor_whitelist:
            _LOGGER.debug("Discovery is disabled. UUID: %s is not whitelisted!", to_uuid(uuid))

            sensor_data = None
        # add rssi and local name to the sensor_data output
        if sensor_data:
            sensor_data.update({
                "rssi": rssi,
                "local_name": local_name,
            })
        else:
            sensor_data = None

        # check for monitored device trackers
        tracker_id = tracker_data['tracker_id'] if tracker_data and 'tracker_id' in tracker_data else mac
        if tracker_id in self.tracker_whitelist:
            tracker_data.update({
                "is connected": True,
                "mac": to_unformatted_mac(mac),
                "rssi": rssi,
                "local_name": local_name,
            })
        else:
            tracker_data = None

        if self.report_unknown_whitelist:
            if tracker_id in self.report_unknown_whitelist:
                _LOGGER.info(
                    "BLE advertisement received from MAC/UUID %s: "
                    "service data: %s"
                    "manufacturer specific data: %s"
                    "local name: %s"
                    "UUID16: %s,"
                    "UUID128: %s",
                    tracker_id.hex(),
                    service_data_list,
                    man_spec_data_list,
                    local_name,
                    service_class_uuid16,
                    service_class_uuid128
                )

        return sensor_data, tracker_data
