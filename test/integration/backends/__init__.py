import os


def backends_to_test():
    return os.environ.get("BACKENDS_TO_TEST", "").split()
