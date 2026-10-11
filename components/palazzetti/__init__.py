"""Palazzetti stove hub for boards speaking the Micronova protocol (not Fumis; see docs/boards.md)."""

from pathlib import Path
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import automation
from esphome import final_validate as fv
from esphome.components import socket, uart
from esphome.const import CONF_ADDRESS, CONF_ID, CONF_PORT, CONF_VALUE
from esphome.core import CORE

CODEOWNERS = ["@jordanauge"]
DEPENDENCIES = ["uart"]
AUTO_LOAD = ["socket", "json"]
MULTI_CONF = True

CONF_PALAZZETTI_ID = "palazzetti_id"
CONF_MEMORY = "memory"
CONF_ENCODING = "encoding"
CONF_ECHO = "echo"
CONF_REPLY_TIMEOUT = "reply_timeout"
CONF_FRAME_GAP = "frame_gap"
CONF_MAX_RETRIES = "max_retries"
CONF_MAX_QUEUE = "max_queue"
CONF_LAB_SERVER = "lab_server"
CONF_ALLOW_WRITE = "allow_write"
CONF_WRITE_ALLOWLIST = "write_allowlist"

palazzetti_ns = cg.esphome_ns.namespace("palazzetti")
micronova_ns = cg.global_ns.namespace("micronova")
Palazzetti = palazzetti_ns.class_("Palazzetti", cg.Component, uart.UARTDevice)
LabServer = palazzetti_ns.class_("LabServer", cg.Component)
MapWeb = palazzetti_ns.class_("MapWeb", cg.Component)
BusEntity = palazzetti_ns.class_("BusEntity", cg.PollingComponent)
WriteAction = palazzetti_ns.class_("WriteAction", automation.Action)

Memory = micronova_ns.enum("Memory", is_class=True)
MEMORY = {"ram": Memory.RAM, "eeprom": Memory.EEPROM}

EchoMode = palazzetti_ns.enum("EchoMode", is_class=True)
ECHO = {"auto": EchoMode.AUTO, True: EchoMode.ON, False: EchoMode.OFF}

Encoding = palazzetti_ns.enum("Encoding", is_class=True)
ENCODING = {
    "uint8": Encoding.UINT8,
    "int8": Encoding.INT8,
    "bcd": Encoding.BCD,
    "uint16_be": Encoding.UINT16_BE,
    "uint16_le": Encoding.UINT16_LE,
    "int16_be": Encoding.INT16_BE,
    "int16_le": Encoding.INT16_LE,
}

MAX_ADDRESS = 0x1FFF


def _echo(value):
    if isinstance(value, str) and value.lower() == "auto":
        return "auto"
    return cv.boolean(value)


def _consume_lab_socket(config):
    if CONF_LAB_SERVER in config:
        socket.consume_sockets(1, "palazzetti_lab", socket.SocketType.TCP_LISTEN)(config)
        socket.consume_sockets(1, "palazzetti_lab")(config)
    return config


def _map_web(config):
    if "map_web" in config:
        if CORE.target_platform != "esp8266":
            raise cv.Invalid("map_web currently supports ESP8266 only")
        full_config = fv.full_config.get()
        if "web_server" not in full_config or "auth" not in full_config["web_server"]:
            raise cv.Invalid("map_web requires web_server with auth")
        auth = full_config["web_server"]["auth"]
        if auth.get("type", "basic") == "basic" and len(
            (auth["username"] + ":" + auth["password"]).encode()
        ) > 53:
            raise cv.Invalid("ESP8266 Basic auth requires username:password <=53 UTF-8 bytes; use a shorter strong password or digest auth")
        if len(full_config["palazzetti"]) != 1:
            raise cv.Invalid("map_web requires a single Palazzetti hub")
        layout = full_config["esphome"].get("platformio_options", {}).get("board_build.ldscript", "")
        if not layout or layout == "eagle.flash.4m.ld":
            raise cv.Invalid("map_web requires an explicit filesystem linker layout; use eagle.flash.4m1m.ld for the 4 MiB NodeMCU")
    return config


LAB_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(LabServer),
        cv.Optional(CONF_PORT, default=6638): cv.port,
        cv.Optional(CONF_ALLOW_WRITE, default=False): cv.boolean,
    }
)


def _write_rule(config):
    if config["min_value"] > config["max_value"]:
        raise cv.Invalid("write_allowlist min_value must not exceed max_value")
    if not config["evidence"].strip():
        raise cv.Invalid("write_allowlist evidence must not be empty")
    return config


WRITE_RULE_SCHEMA = cv.All(cv.Schema({
    cv.Required(CONF_MEMORY): cv.enum(MEMORY, lower=True),
    cv.Required(CONF_ADDRESS): cv.int_range(0, MAX_ADDRESS),
    cv.Required("min_value"): cv.uint8_t,
    cv.Required("max_value"): cv.uint8_t,
    cv.Required("evidence"): cv.string_strict,
}), _write_rule)

CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(Palazzetti),
            cv.Optional(CONF_ECHO, default="auto"): _echo,
            cv.Optional(CONF_REPLY_TIMEOUT, default="300ms"): cv.positive_time_period_milliseconds,
            cv.Optional(CONF_FRAME_GAP, default="30ms"): cv.positive_time_period_milliseconds,
            cv.Optional(CONF_MAX_RETRIES, default=2): cv.int_range(0, 10),
            cv.Optional(CONF_MAX_QUEUE, default=48): cv.int_range(4, 250),
            cv.Optional(CONF_LAB_SERVER): LAB_SCHEMA,
            cv.Optional(CONF_WRITE_ALLOWLIST, default=[]): cv.ensure_list(WRITE_RULE_SCHEMA),
            cv.Optional("map_web"): cv.Schema({cv.GenerateID(): cv.declare_id(MapWeb)}),
        }
    )
    .extend(cv.COMPONENT_SCHEMA)
    .extend(uart.UART_DEVICE_SCHEMA),
    _consume_lab_socket,
)

FINAL_VALIDATE_SCHEMA = cv.All(
    uart.final_validate_device_schema(
        "palazzetti", baud_rate=1200, require_tx=True, require_rx=True, stop_bits=2
    ),
    _map_web,
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await uart.register_uart_device(var, config)
    cg.add(var.set_echo_mode(ECHO[config[CONF_ECHO]]))
    cg.add(var.set_reply_timeout(config[CONF_REPLY_TIMEOUT]))
    cg.add(var.set_frame_gap(config[CONF_FRAME_GAP]))
    cg.add(var.set_max_retries(config[CONF_MAX_RETRIES]))
    cg.add(var.set_max_queue(config[CONF_MAX_QUEUE]))
    if web := config.get("map_web"):
        cg.add_define("USE_PALAZZETTI_MAP_WEB")
        cg.add_library("LittleFS", None)
        page = Path(__file__).with_name("map_web.html").read_text()
        cg.add_global(cg.RawStatement('static const char MAP_WEB_PAGE[] PROGMEM = R"plzpage(' + page + ')plzpage";'))
        dashboard = cg.new_Pvariable(web[CONF_ID])
        await cg.register_component(dashboard, web)
        await cg.register_parented(dashboard, var)
        cg.add(dashboard.set_page(cg.RawExpression("MAP_WEB_PAGE")))
    for rule in config[CONF_WRITE_ALLOWLIST]:
        cg.add(var.add_write_rule(MEMORY[rule[CONF_MEMORY]], rule[CONF_ADDRESS],
                                 rule["min_value"], rule["max_value"]))
    if lab := config.get(CONF_LAB_SERVER):
        cg.add_define("USE_PALAZZETTI_LAB")
        srv = cg.new_Pvariable(lab[CONF_ID])
        await cg.register_component(srv, lab)
        await cg.register_parented(srv, var)
        cg.add(srv.set_port(lab[CONF_PORT]))
        cg.add(srv.set_allow_write(lab[CONF_ALLOW_WRITE]))


# Shared by the entity platforms.
def bus_entity_schema(default_interval="30s", default_encoding="uint8"):
    return cv.Schema(
        {
            cv.GenerateID(CONF_PALAZZETTI_ID): cv.use_id(Palazzetti),
            cv.Optional(CONF_MEMORY, default="ram"): cv.enum(MEMORY, lower=True),
            cv.Required(CONF_ADDRESS): cv.int_range(0, MAX_ADDRESS),
            cv.Optional(CONF_ENCODING, default=default_encoding): cv.enum(ENCODING, lower=True),
        }
    ).extend(cv.polling_component_schema(default_interval))


async def register_bus_entity(var, config):
    await cg.register_component(var, config)
    await cg.register_parented(var, config[CONF_PALAZZETTI_ID])
    cg.add(var.set_memory(MEMORY[config[CONF_MEMORY]]))
    cg.add(var.set_address(config[CONF_ADDRESS]))
    cg.add(var.set_encoding(ENCODING[config[CONF_ENCODING]]))


@automation.register_action(
    "palazzetti.write",
    WriteAction,
    cv.Schema(
        {
            cv.GenerateID(): cv.use_id(Palazzetti),
            cv.Optional(CONF_MEMORY, default="ram"): cv.enum(MEMORY, lower=True),
            cv.Required(CONF_ADDRESS): cv.int_range(0, MAX_ADDRESS),
            cv.Required(CONF_VALUE): cv.templatable(cv.uint8_t),
        }
    ),
    synchronous=True,
)
async def write_action_to_code(config, action_id, template_arg, args):
    var = cg.new_Pvariable(action_id, template_arg)
    await cg.register_parented(var, config[CONF_ID])
    cg.add(var.set_memory(MEMORY[config[CONF_MEMORY]]))
    cg.add(var.set_address(config[CONF_ADDRESS]))
    cg.add(var.set_value(await cg.templatable(config[CONF_VALUE], args, cg.uint8)))
    return var
