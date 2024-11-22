// SPDX-License-Identifier: Apache-2.0

#include "config.h"

#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/uuid.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(BT, LOG_LEVEL_INF);

#define SERVICE_DATA_LEN 12
#define SERVICE_UUID     0xfcd2 /* BTHome service UUID */
#define IDX_BATTERY_PCT  4
#define IDX_VOLTAGEL     6
#define IDX_VOLTAGEH     7
#define IDX_CHRG         9
#define IDX_OCCUPANCY    11

#define ADV_PARAM                                                                                  \
	BT_LE_ADV_PARAM(BT_LE_ADV_OPT_USE_IDENTITY, BT_GAP_ADV_SLOW_INT_MIN,                       \
			BT_GAP_ADV_SLOW_INT_MAX, NULL)

static uint8_t service_data[SERVICE_DATA_LEN] = {
	BT_UUID_16_ENCODE(SERVICE_UUID),
	0x44, /* BTHome Device Information */
	0x01, /* battery % */
	0x64,
	0x0c, /* voltage */
	0x02,
	0x0C,
	0x16, /* battery charging */
	0x00,
	0x23, /* occupancy */
	0x00,
};

static struct bt_data ad[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR),
	BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME, sizeof(CONFIG_BT_DEVICE_NAME) - 1),
	BT_DATA(BT_DATA_SVC_DATA16, service_data, ARRAY_SIZE(service_data))};

static void bt_ready(int err)
{
	if (err) {
		LOG_ERR("Bluetooth init failed (err %d)", err);
		return;
	}

	LOG_INF("Bluetooth initialized");

	// start advertising
	err = bt_le_adv_start(ADV_PARAM, ad, ARRAY_SIZE(ad), NULL, 0);
	if (err) {
		LOG_ERR("Advertising failed to start (err %d)", err);
		return;
	}
}

int advertising_start(void)
{
	int rc = 0;

	rc = bt_enable(bt_ready);
	if (rc) {
		LOG_ERR("Bluetooth init failed (err %d)", rc);
	}

	return rc;
}

int advertising_update(int occupancy, int mv, int percentage, int charge_state)
{
	int err;
	LOG_INF("Updating advertising data");
	LOG_INF("occupancy %d, voltage %d, percentage %d, charge state %d", occupancy, mv,
		percentage, charge_state);

	// populate data
	service_data[IDX_BATTERY_PCT] = percentage;
	service_data[IDX_VOLTAGEH] = (mv) >> 8;
	service_data[IDX_VOLTAGEL] = (mv) & 0xff;
	service_data[IDX_CHRG] = charge_state;
	service_data[IDX_OCCUPANCY] = occupancy;

	err = bt_le_adv_update_data(ad, ARRAY_SIZE(ad), NULL, 0);
	if (err) {
		LOG_ERR("Failed to update advertising data (err %d)", err);
		return err;
	}

	return 0;
}
