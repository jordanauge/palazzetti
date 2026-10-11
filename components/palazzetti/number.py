import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import number
from esphome.const import CONF_MAX_VALUE, CONF_MIN_VALUE, CONF_MULTIPLY, CONF_OFFSET, CONF_STEP

from . import BusEntity, bus_entity_schema, palazzetti_ns, register_bus_entity

DEPENDENCIES = ["palazzetti"]

BusNumber = palazzetti_ns.class_("BusNumber", BusEntity, number.Number)

CONFIG_SCHEMA = (
    number.number_schema(BusNumber)
    .extend(bus_entity_schema())
    .extend(
        {
            cv.Optional(CONF_MIN_VALUE, default=0): cv.float_,
            cv.Optional(CONF_MAX_VALUE, default=255): cv.float_,
            cv.Optional(CONF_STEP, default=1): cv.positive_float,
            cv.Optional(CONF_MULTIPLY, default=1.0): cv.float_range(min=0, min_included=False),
            cv.Optional(CONF_OFFSET, default=0.0): cv.float_,
        }
    )
)


async def to_code(config):
    var = await number.new_number(
        config, min_value=config[CONF_MIN_VALUE], max_value=config[CONF_MAX_VALUE], step=config[CONF_STEP]
    )
    await register_bus_entity(var, config)
    cg.add(var.set_multiply(config[CONF_MULTIPLY]))
    cg.add(var.set_offset(config[CONF_OFFSET]))
