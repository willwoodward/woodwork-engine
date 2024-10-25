from woodwork.globals import global_config as config

def set_globals(**kwargs) -> None:
    for key, value in kwargs.items():
        config[key] = value

def print_debug(*args: any) -> None:
    if config["mode"] == "debug":
        print(*args)