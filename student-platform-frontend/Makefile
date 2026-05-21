FRONTEND_DIST ?= dist
DJANGO_APP ?= ../learning
DJANGO_TEMPLATE_DIR ?= $(DJANGO_APP)/templates
DJANGO_STATIC_DIR ?= $(DJANGO_APP)/static

.DEFAULT_GOAL := deploy

.PHONY: build copy-template copy-static deploy clean-dist

build:
	npm run build

copy-template: build
	mkdir -p $(DJANGO_TEMPLATE_DIR)
	cp $(FRONTEND_DIST)/index.html $(DJANGO_TEMPLATE_DIR)/index.html

copy-static: build
	mkdir -p $(DJANGO_STATIC_DIR)
	cp -R $(FRONTEND_DIST)/static/. $(DJANGO_STATIC_DIR)/
	find $(FRONTEND_DIST) -maxdepth 1 -type f ! -name index.html -exec cp {} $(DJANGO_STATIC_DIR)/ \;

deploy: copy-template copy-static

clean-dist:
	rm -rf $(FRONTEND_DIST)
