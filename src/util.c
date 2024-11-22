// SPDX-License-Identifier: Apache-2.0

#include <zephyr/drivers/gpio.h>
#include <zephyr/pm/device.h>
#include <zephyr/sys/poweroff.h>
#include <zephyr/logging/log.h>
#include <zephyr/logging/log_ctrl.h>

#include "battery.h"
#include "bt.h"
#include "config.h"

#define STACKSIZE 1024
#define PRIORITY  7

LOG_MODULE_REGISTER(UTIL, LOG_LEVEL_INF);

void sensor_helper();
void sensor_update();
void sleep_timer_handler(struct k_timer *dummy);
void debounce_timer_handler(struct k_timer *dummy);
void system_sleep(struct k_work *work);

K_SEM_DEFINE(sensor_sem, 0, 1);
K_SEM_DEFINE(debounce_sem, 0, 1);
K_THREAD_DEFINE(sensor_helper_id, STACKSIZE, sensor_helper, NULL, NULL, NULL, PRIORITY, 0, 0);
K_TIMER_DEFINE(sleep_timer, sleep_timer_handler, NULL);
K_TIMER_DEFINE(debounce_timer, debounce_timer_handler, NULL);
K_WORK_DEFINE(system_sleep_work, system_sleep);

void wait_on_log_flushed(void)
{
	while (log_buffered_cnt()) {
		k_sleep(K_MSEC(20));
	}
}

// timer manipulation and expiry handlers

void sleep_timer_start(void)
{
	LOG_INF("Sleep timer started, system off in %i seconds", SLEEP_TIMEOUT_SEC);
	k_timer_start(&sleep_timer, K_SECONDS(SLEEP_TIMEOUT_SEC), K_NO_WAIT);
}

void sleep_timer_stop(void)
{
	LOG_INF("Sleep timer stopped");
	k_timer_stop(&sleep_timer);
}

void sleep_timer_handler(struct k_timer *dummy)
{
	k_work_submit(&system_sleep_work);
}

void debounce_timer_handler(struct k_timer *dummy)
{
	k_sem_give(&debounce_sem);
}

// Power related functions

/** A discharge curve specific to the power source. */
static const struct battery_level_point levels[] = {
	/* "Curve" here eyeballed from captured data for the [Adafruit
	 * 3.7v 2000 mAh](https://www.adafruit.com/product/2011) LIPO
	 * under full load that started with a charge of 3.96 V and
	 * dropped about linearly to 3.58 V over 15 hours.  It then
	 * dropped rapidly to 3.10 V over one hour, at which point it
	 * stopped transmitting.
	 *
	 * Based on eyeball comparisons we'll say that 15/16 of life
	 * goes between 3.95 and 3.55 V, and 1/16 goes between 3.55 V
	 * and 3.1 V.
	 */

	{10000, 3950},
	{625, 3550},
	{0, 3100},
};

int power_state_read(int *out_mv, int *out_percentage, int *out_charge_state, int *out_vbus)
{
	// enable ADC
	int rc = battery_measure_enable(true);
	if (rc != 0) {
		LOG_ERR("Failed to enable ADC");
		return rc;
	}

	// sample battery voltage
	*out_mv = battery_sample();
	if (*out_mv < 0) {
		LOG_ERR("Failed to read battery voltage: %d", *out_mv);
		rc = -1;
		return rc;
	}
	LOG_INF("Battery voltage: %d mV", *out_mv);

	// calculate battery percentage
	*out_percentage = battery_level_pptt(*out_mv, levels) / 100;
	LOG_INF("Battery percentage: %d", *out_percentage);

	// get vbus status
	*out_vbus = gpio_pin_get_dt(&vbus_det);
	LOG_INF("VBUS: %d", *out_vbus);

	// charge state should be ignored if vbus is not present
	if (*out_vbus == 1) {
		*out_charge_state = gpio_pin_get_dt(&charge_status);
	} else {
		*out_charge_state = 0;
	}

	LOG_INF("Charging state: %d", *out_charge_state);

	// disable ADC
	rc = battery_measure_enable(false);
	if (rc != 0) {
		LOG_ERR("Failed to disable ADC");
		return rc;
	}

	return 0;
}

void system_sleep(struct k_work *work)
{
	LOG_INF("Sleep timer expired");
	int state = gpio_pin_get_dt(&occupancy_sw);
	LOG_INF("Switch state: %i", state);
	state = !state;
	LOG_INF("Setting wakeup state to: %i", state);
	gpio_pin_interrupt_configure_dt(&occupancy_sw, state);
	// Disable pull-up on CHG to save power
	gpio_pin_configure_dt(&charge_status, GPIO_INPUT);
	LOG_INF("Entering system off");
	wait_on_log_flushed();

	pm_device_action_run(console, PM_DEVICE_ACTION_SUSPEND);
	sys_poweroff();
}

// sensor helper thread
void sensor_helper()
{
	while (true) {
		if (k_sem_take(&sensor_sem, K_FOREVER) == 0 &&
		    k_sem_take(&debounce_sem, K_FOREVER) == 0) {
			LOG_INF("Updating sensor data");
			sleep_timer_stop();

			// collect power info and update advertising data
			int voltage, percentage, charge_state, vbus, rc;
			rc = power_state_read(&voltage, &percentage, &charge_state, &vbus);
			int occupancy = gpio_pin_get_dt(&occupancy_sw);
			advertising_update(occupancy, voltage, percentage, charge_state);

			sleep_timer_start();
		}
	}
}

// sensor GPIO ISR
void switch_state_callback(const struct device *dev, struct gpio_callback *cb,
			   gpio_port_pins_t pins)
{
	// use debounce timer
	k_timer_start(&debounce_timer, K_SECONDS(DEBOUNCE_TIMER_SEC), K_NO_WAIT);
	k_sem_give(&sensor_sem);
}

void charge_state_callback(const struct device *dev, struct gpio_callback *cb,
			   gpio_port_pins_t pins)
{
	// ignore debounce timer and update immediately
	sensor_update();
}

void sensor_update()
{
	k_sem_give(&debounce_sem);
	k_sem_give(&sensor_sem);
}