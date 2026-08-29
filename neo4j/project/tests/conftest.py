"""Shared pytest fixtures: one driver for the whole test module, loaded once
from the CSV dataset (with a full reset) before any test runs.
"""

import pytest

from neo4j_tutorial import load_data
from neo4j_tutorial.db import get_driver


def load_dataset(driver, reset: bool = True) -> None:
    """Run the same steps as `load_data.main()`, without the CLI/print parts."""
    if reset:
        driver.execute_query("MATCH (n) DETACH DELETE n", database_="neo4j")
    for constraint in load_data.CONSTRAINTS:
        driver.execute_query(constraint, database_="neo4j")
    for csv_name, query in load_data.NODE_QUERIES.items():
        load_data.load_file(driver, csv_name, query)
    for csv_name, query in load_data.REL_QUERIES.items():
        load_data.load_file(driver, csv_name, query)


@pytest.fixture(scope="module")
def driver():
    d = get_driver()
    yield d
    d.close()


@pytest.fixture(scope="module", autouse=True)
def loaded_dataset(driver):
    load_dataset(driver, reset=True)
    yield
    load_dataset(driver, reset=True)
