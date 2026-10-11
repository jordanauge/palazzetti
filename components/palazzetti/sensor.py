import esphome.codegen as cg
from esphome.components import sensor

from . import BusEntity, bus_entity_schema, palazzetti_ns, register_bus_entity

DEPENDENCIES = ["palazzetti"]

BusSensor = palazzetti_ns.class_("BusSensor", BusEntity, sensor.Sensor)

CONFIG_SCHEMA = sensor.sensor_schema(BusSensor, accuracy_decimals=0).extend(bus_entity_schema())


async def to_code(config):
    var = await sensor.new_sensor(config)
    await register_bus_entity(var, config)
