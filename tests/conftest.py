"""pytest configuration: register custom markers."""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "requires_db: marks tests that require a populated LanceDB german_cases table "
        "(skip with: pytest -m 'not requires_db')",
    )
