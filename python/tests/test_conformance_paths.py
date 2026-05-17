from pcs_core.conformance import (
    LABTRUST_INVALID_FIXTURES,
    LABTRUST_VALID_FIXTURES,
    labtrust_fixture_path,
)


def test_labtrust_fixture_paths_exist() -> None:
    for name in (*LABTRUST_VALID_FIXTURES, *LABTRUST_INVALID_FIXTURES):
        assert labtrust_fixture_path(name).is_file()
