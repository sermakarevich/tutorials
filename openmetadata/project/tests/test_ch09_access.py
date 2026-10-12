"""Chapter 09 access checks against the running stack (marker `stack`).

Covers the exact numbers the prose relies on: the 200/403 matrix as dana
and the default-policy evidence behind it.
"""

import pytest

from openmetadata_tutorial import ch09_access

pytestmark = pytest.mark.stack


def test_default_policy_allows_description_but_not_owners():
    assert ch09_access.default_policy_allows("EditDescription") is True
    assert ch09_access.default_policy_allows("EditOwners") is False


def test_dana_read_allowed_write_denied():
    probe = ch09_access.probe_access()
    assert probe["GET daily_revenue"][0] == 200
    assert probe["PATCH description daily_revenue"][0] == 200
    # The shipped default already allows description edits to everyone, so
    # the unowned non-sensitive table stays 200 on 2.0.5 (see the chapter).
    assert probe["PATCH description raw.orders"][0] == 200


def test_dana_description_denied_on_pii_table():
    probe = ch09_access.probe_access()
    status, snippet = probe["PATCH description raw.customers"]
    assert status == 403
    assert "NoPIIForConsumers-DenySensitiveEdits" in snippet


def test_pii_sample_data_denied_for_tagged_table_only():
    probe = ch09_access.probe_access()
    status, snippet = probe["GET raw.customers sampleData"]
    assert status == 403
    assert "NoPIIForConsumers" in snippet
    assert probe["GET raw.products sampleData"][0] == 200
