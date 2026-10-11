# Palazzetti: ESPHome firmware (built by PlatformIO through esphome) and reverse-engineering lab.
#   make build              compile CONFIG (default: the Lara example)
#   make upload [DEVICE=…]  flash over USB, or OTA with DEVICE=palazzetti.local
#   make logs               follow the device logs
#   make test               Python tests (plz) and host C++ codec test
#   make test-compile       compile the test config exercising every platform
#   make gen                regenerate docs/memory-map.md and the entity packages from maps/

CONFIG ?= example/palazzetti-ecofire-lara.yaml
PROFILES ?= palazzetti-ecofire-lara
ESPHOME ?= esphome
UV ?= uv
HTML_CAPTURES ?=
HTML_LEGACY_DIRS ?=

ifeq ($(shell uname -s),Darwin)
DEVICE ?= $(shell ls /dev/cu.usbserial* /dev/cu.wchusbserial* /dev/cu.SLAB* 2>/dev/null | head -1)
else
DEVICE ?= $(shell ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | head -1)
endif

.PHONY: all build config upload logs run test test-py test-cpp test-compile gen docs clean

all: build

config:
	$(ESPHOME) config $(CONFIG)

build:
	$(ESPHOME) compile $(CONFIG)

upload:
	$(ESPHOME) upload $(CONFIG) $(if $(DEVICE),--device $(DEVICE))

logs:
	$(ESPHOME) logs $(CONFIG) $(if $(DEVICE),--device $(DEVICE))

run:
	$(ESPHOME) run $(CONFIG) $(if $(DEVICE),--device $(DEVICE))

test: test-py test-cpp

test-py:
	$(UV) run pytest -q

test-cpp:
	@mkdir -p .pio
	$(CXX) -std=c++17 -Wall -Wextra -Icomponents/palazzetti tests/test_micronova.cpp -o .pio/test_micronova
	./.pio/test_micronova

test-compile:
	$(ESPHOME) compile tests/compile-esp8266.yaml

gen docs:
	$(UV) run plz gen-docs -o docs/memory-map.md
	$(UV) run plz gen-html palazzetti-ecofire-lara -o docs $(foreach c,$(HTML_CAPTURES),--capture $(c)) $(foreach d,$(HTML_LEGACY_DIRS),--legacy-dir $(d))
	@for p in $(PROFILES); do $(UV) run plz gen-esphome $$p -o example/$$p.entities.yaml; done

clean:
	rm -rf .esphome example/.esphome tests/.esphome .pio
