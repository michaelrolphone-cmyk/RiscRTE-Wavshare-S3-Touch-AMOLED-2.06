/* PCF85063A: preserves the deployed rtc.clock@2 ABI. Register mapping follows
 * NXP PCF85063A and the pinned Waveshare SensorLib example; no PCF8563 assumptions. */
#include "RiscI2cBusV1.h"
#include "twatch_caps.h"
#include "DriverSupport.h"
#include "twatch_calendar.h"
#include "ProviderLog.h"
#include <stddef.h>
#include <stdio.h>
static const risc_i2c_bus_api_v1 *bus;
static uint64_t claim, irq_claim;
static const risc_gpio_bank_api_v1 *gpio_api;
static bool started;
static const tw_hw_i2c_device_v1 *config;
/* Log the first read and status transitions, plus the read after each write.
 * A successful transfer is deliberately not described as clock persistence. */
static unsigned last_read_status;
static void log_read(unsigned status, const char *reason, const uint8_t *raw) {
    if (last_read_status == status) return;
    last_read_status = status;
    char line[160];
    if (raw)
        snprintf(line,sizeof(line),"RTC_PCF85063 read=%s raw04_0a=%02x,%02x,%02x,%02x,%02x,%02x,%02x",
                 reason,raw[0],raw[1],raw[2],raw[3],raw[4],raw[5],raw[6]);
    else
        snprintf(line,sizeof(line),"RTC_PCF85063 read=%s",reason);
    provider_log(line);
}
static uint8_t bcd(uint8_t v) {
    return (uint8_t)(((v / 10u) << 4) | (v % 10u));
}
static uint8_t dec(uint8_t v) {
    return (uint8_t)((v >> 4) * 10u + (v & 0x0fu));
}
static bool write_regs(uint8_t reg, const uint8_t *bytes, size_t n) {
    uint8_t buf[8];
    if (n > 7u)
        return false;
    buf[0] = reg;
    for (size_t i = 0; i < n; ++i)
        buf[i + 1u] = bytes[i];
    return bus->transact(bus->context, claim, buf, n + 1u, NULL, 0, 30);
}
static bool read_regs(uint8_t reg, uint8_t *out, size_t n) {
    return bus->transact(bus->context, claim, &reg, 1, out, n, 30);
}
static bool read_time(void *context, twatch_rtc_time_v1 *out) {
    (void)context;
    if (!started || !out)
        return false;
    uint8_t raw[7] = {0};
    if (!read_regs(0x04u, raw, 7)) {
        log_read(1,"transfer-failed",NULL);
        return false;
    }
    if (raw[0] & 0x80u) {
        log_read(2,"oscillator-stop",raw);
        return false;
    }
    for (size_t i = 0; i < 7; i++)
        if (i != 4 && !tw_valid_bcd(raw[i] & (i == 0 || i == 1   ? 0x7f
                                              : i == 2 || i == 3 ? 0x3f
                                              : i == 5           ? 0x1f
                                                                 : 0xff))) {
            log_read(3,"invalid-bcd",raw);
            return false;
        }
    twatch_rtc_time_v1 value={0};
    value.second = dec(raw[0] & 0x7fu);
    value.minute = dec(raw[1] & 0x7fu);
    value.hour = dec(raw[2] & 0x3fu);
    value.day = dec(raw[3] & 0x3fu);
    value.weekday = raw[4] & 0x07u;
    value.month = dec(raw[5] & 0x1fu);
    value.year = (uint16_t)(2000u + dec(raw[6]));
    if (!tw_valid_time(&value)) {
        log_read(4,"invalid-calendar",raw);
        return false;
    }
    log_read(5,"valid-calendar",raw);
    *out=value;
    return true;
}
static bool write_time(void *context, const twatch_rtc_time_v1 *in) {
    (void)context;
    if (!started || !tw_valid_time(in))
        return false;
    uint8_t raw[7] = {bcd(in->second),
                      bcd(in->minute),
                      bcd(in->hour),
                      bcd(in->day),
                      in->weekday & 0x07u,
                      bcd(in->month),
                      bcd((uint8_t)(in->year - 2000u))};
    bool ok=write_regs(0x04u, raw, 7);
    char line[160];
    snprintf(line,sizeof(line),"RTC_PCF85063 write=%s raw04_0a=%02x,%02x,%02x,%02x,%02x,%02x,%02x",
             ok?"transfer-ok":"transfer-failed",raw[0],raw[1],raw[2],raw[3],raw[4],raw[5],raw[6]);
    provider_log(line);
    last_read_status=0;
    return ok;
}
/* Keep rtc.clock@2 minute resolution: seconds are matched at 00, disabled fields use AE=1. */
static bool alarm(void *c, uint8_t minute, uint8_t hour, uint8_t day, uint8_t weekday,
                  bool enable) {
    (void)c;
    if (!started || (minute != 255 && minute > 59) || (hour != 255 && hour > 23) ||
        (day != 255 && (!day || day > 31)) || (weekday != 255 && weekday > 6))
        return false;
    uint8_t fields[] = {0, minute == 255 ? 0x80 : bcd(minute), hour == 255 ? 0x80 : bcd(hour),
                        day == 255 ? 0x80 : bcd(day), weekday == 255 ? 0x80 : weekday},
            status;
    if (!read_regs(1, &status, 1))
        return false;
    uint8_t off = status & ~(0xc0u);
    if (!write_regs(1, &off, 1) || !write_regs(0x0b, fields, 5))
        return false;
    off |= enable ? 0x80u : 0;
    return write_regs(1, &off, 1);
}
static bool alarm_pending(void *c, bool *pending, bool ack) {
    (void)c;
    if (!started || !pending)
        return false;
    uint8_t v;
    if (!read_regs(1, &v, 1))
        return false;
    *pending = (v & 0x40u) != 0;
    if (ack) {
        v &= ~0x40u;
        return write_regs(1, &v, 1);
    }
    return true;
}
static bool quiesce(void) {
    if (started && claim) {
        uint8_t v;
        if (!read_regs(1, &v, 1))
            return false;
        v &= ~0x80u;
        if (!write_regs(1, &v, 1))
            return false;
    }
    bool ok = !claim || (bus && bus->release_device(bus->context, claim));
    if (!ok)
        return false;
    claim = 0;
    if (irq_claim) {
        if (!gpio_api->release(gpio_api->context, irq_claim))
            return false;
        irq_claim = 0;
    }
    claim = 0;
    bus = NULL;
    started = false;
    return ok;
}
static bool start(const risc_provider_dependency_v1 *deps, size_t count) {
    if (started || claim || irq_claim)
        return false;
    config = tw_config(deps, count, "nxp,pcf85063a", "peripheral.i2c", sizeof(*config));
    if (!tw_i2c_config_valid(config))
        return false;
    gpio_api = tw_dep(deps, count, "gpio.bank", offsetof(risc_gpio_bank_api_v1,light_sleep));
    if (config->irq != -1 && !tw_gpio_valid(gpio_api))
        return false;
    bus = tw_dep(deps, count, "i2c.bus", sizeof(*bus));
    if (!tw_i2c_valid(bus))
        return false;
    if (config->irq != -1 &&
        !gpio_api->claim(gpio_api->context, config->irq,
                         RISC_GPIO_INPUT | (config->irq_pull_up ? RISC_GPIO_PULLUP : 0),
                         &irq_claim))
        return false;
    if (!bus->claim_device(bus->context, config->address, &claim)) {
        (void)quiesce(); return false;
    }
    uint8_t control = 0;
    if (!read_regs(0, &control, 1)) {
        (void)quiesce();
        return false;
    }
    /* Select 24-hour mode and start oscillator; do not write CTRL2 here.
     * CTRL2 carries live alarm state on this chip, not a separate clock-out register. */
    control &= ~(0x20u | 0x02u);
    if (!write_regs(0, &control, 1)) {
        (void)quiesce();
        return false;
    }
    last_read_status=0;
    started = true;
    return true;
}
static void stop(void) {
    (void)quiesce();
}
static const twatch_rtc_api_v1 api = {TWATCH_RTC_API_V1, sizeof(api), NULL,         read_time,
                                      write_time,        alarm,       alarm_pending};
static const risc_driver_v2 driver = {RISC_PROVIDER_DRIVER_ABI_V2,
                                      sizeof(driver),
                                      "waveshare-rtc",
                                      TWATCH_RTC_CAPABILITY,
                                      TWATCH_RTC_API_V1,
                                      &api,
                                      start,
                                      stop,
                                      quiesce};
__attribute__((visibility("default"))) const risc_driver_v2 *t5_driver_get(uint32_t abi) {
    return abi == RISC_PROVIDER_DRIVER_ABI_V2 ? &driver : NULL;
}
