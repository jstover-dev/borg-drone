APP_NAME := borg_drone

lint-fix:
	yapf -rip $(APP_NAME) tests/
	autoflake -ri --remove-all-unused-imports --remove-unused-variables --ignore-init-module-imports $(APP_NAME) tests/
	mypy --install-types $(APP_NAME)

test:
	python -m pytest -vvv tests/
