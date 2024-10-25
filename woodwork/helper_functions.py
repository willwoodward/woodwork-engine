from woodwork.globals import global_config as config

def print_debug(*args: any) -> None:
    if config["mode"] == "debug":
        print(*args)