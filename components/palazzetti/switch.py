import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import switch

from . import BusEntity, bus_entity_schema, palazzetti_ns, register_bus_entity

DEPENDENCIES = ["palazzetti"]

CONF_ON_VALUE = "on_value"
CONF_OFF_VALUE = "off_value"
CONF_OFF_STATES = "off_states"

BusSwitch = palazzetti_ns.class_("BusSwitch", BusEntity, switch.Switch)

CONFIG_SCHEMA = (
    switch.switch_schema(BusSwitch, default_restore_mode="DISABLED")
    .extend(bus_entity_schema())
    .extend(
        {
            cv.Optional(CONF_ON_VALUE, default=1): cv.uint8_t,
            cv.Optional(CONF_OFF_VALUE, default=0): cv.uint8_t,
            # Raw values (besides off_value) reported as "off", e.g. stove alarms/cleaning states.
            cv.Optional(CONF_OFF_STATES, default=[]): cv.ensure_list(cv.int_),
        }
    )
)


async def to_code(config):
    var = await switch.new_switch(config)
    await register_bus_entity(var, config)
    cg.add(var.set_on_value(config[CONF_ON_VALUE]))
    cg.add(var.set_off_value(config[CONF_OFF_VALUE]))
    if config[CONF_OFF_STATES]:
        cg.add(var.set_off_states(config[CONF_OFF_STATES]))
