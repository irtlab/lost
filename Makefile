PYTHON ?= python3.11

.PHONY:
build:
	$(PYTHON) -m build

.PHONY:
upload:
	$(PYTHON) -m twine upload -r testpypi -u __token__ -p "$(TEST_PYPI_TOKEN)" dist/*
