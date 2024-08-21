from woodwork.config_parser import main_function
from woodwork.dependencies import init

import sys

def main():
    if len(sys.argv) == 1:
        main_function()
    elif sys.argv[1] == "init":
        if len(sys.argv) == 2:
            init()
        else:
            if sys.argv[2] == "--isolated":
                init({"isolated": True})