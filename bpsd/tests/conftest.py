def pytest_configure(config):
    config.addinivalue_line("markers", "full: reads the score files of all 32 movements; part of the full suite")
