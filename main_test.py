import sys
import pytest


def run_all_tests() -> None:
    print("==================================================")
    print("SENTINEL-ALPHA: SYSTEM VALIDATION SUITE")
    print("==================================================")

    # Test suite is standardized under ./tests (see WI-0250).
    exit_code = pytest.main(["-q", "-v", "--tb=short", "tests"])

    if exit_code == 0:
        print("\nOK: test suite passed.")
    else:
        print("\nFAIL: test suite failed.")

    sys.exit(exit_code)


if __name__ == "__main__":
    run_all_tests()
