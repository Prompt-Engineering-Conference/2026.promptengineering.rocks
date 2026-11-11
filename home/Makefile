generate: deps theme
	python _build/generate.py

deps:
	mkdir -p static

clean:
	rm -rf ./static/*

theme: deps   # static/ must exist first: under make -j, cp into a missing static/ made static a copy of assets/ (home lost its CSS, 2026-11-11)
	cp -r ../_assets/template_v1/* static/
	cp -r assets static

serve:
	python _build/serve.py

env:
	python3 -m venv env

.PHONY: generate serve theme clean
