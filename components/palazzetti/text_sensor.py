import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import text_sensor

from . import BusEntity, bus_entity_schema, palazzetti_ns, register_bus_entity

DEPENDENCIES = ["palazzetti"]

CONF_MAP = "map"

BusTextSensor = palazzetti_ns.class_("BusTextSensor", BusEntity, text_sensor.TextSensor)

CONFIG_SCHEMA = (
    text_sensor.text_sensor_schema(BusTextSensor)
    .extend(bus_entity_schema())
    .extend({cv.Optional(CONF_MAP, default={}): cv.Schema({cv.int_: cv.string})})
)


async def to_code(config):
    var = await text_sensor.new_text_sensor(config)
    await register_bus_entity(var, config)
    for raw, text in config[CONF_MAP].items():
        cg.add(var.add_mapping(raw, text))
