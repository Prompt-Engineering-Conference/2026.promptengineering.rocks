years := $(wildcard 20*)

########################################################################
# LANDING PAGE (temporary)
# To switch back to the regular site:
#   1. Remove the "landing" target below
#   2. Change "generate" default target back to:
#        generate: $(addprefix static/,$(addsuffix /index.html,$(years))) static/index.html
########################################################################
generate: landing

landing:
	mkdir -p static/bg
	cp landing/index.html landing/style.css landing/script.js landing/logo-white.svg static/
	cp home/assets/bg/* static/bg/
########################################################################

# --- Regular site build (uncomment and set as default to restore) ---
# generate: $(addprefix static/,$(addsuffix /index.html,$(years))) static/index.html

20%/static/index.html: 20%/_build/* 20%/_templates/* 20%/_db/* 20%/Makefile 20%/metadata.*
	@echo $@
	@echo $^
	$(eval LOCATION := 20$*)
	cd ${LOCATION} && \
		make clean && \
		make generate

static/20%/index.html: 20%/static/index.html
	@echo ">>>" $@
	cp -r 20$*/static/ static/20$*

static/index.html: home/**/*
	cd home && \
		make clean && \
		make generate && \
		cp -r static/* ../static
	cp -r photos ./static
	cp -r speakers ./static

env:
	python3 -m venv env

deps:
	pip install -r _build/requirements.txt
	mkdir -p static

clean:
	rm -rf ./static/* ./20*/static/*

serve:
	python3 _build/serve.py
	open http://localhost:8080

.PHONY: env deps clean serve landing
