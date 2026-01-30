import sys
import pytest


def run_all_tests() -> None:
    print("==================================================")
    print("SENTINEL-ALPHA: SYSTEM VALIDATION SUITE")
    print("==================================================")

    exit_code = pytest.main(["-q", "-v", "--tb=short", "test"])

    if exit_code == 0:
        print("\nOK: test suite passed.")
    else:
        print("\nFAIL: test suite failed.")

    sys.exit(exit_code)


if __name__ == "__main__":
    run_all_tests()
