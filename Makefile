PYTHON ?= python3.11

.PHONY:
build:
	$(PYTHON) -m build

.PHONY:
upload:
	$(PYTHON) -m twine upload -r testpypi -u __token__ -p "$(TEST_PYPI_TOKEN)" dist/*

.PHONY:
docker:
	docker build -t janakj.net/lost/db        -f Dockerfile.db        .
	docker build -t janakj.net/lost/db/server -f Dockerfile.db.server .
	docker build -t janakj.net/lost           -f Dockerfile           .
	docker build -t janakj.net/lost/server    -f Dockerfile.server    .
	docker build -t janakj.net/lost/resolver  -f Dockerfile.resolver  .

.PHONY:
fetch:
	
