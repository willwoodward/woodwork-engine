class component:
    def __init__(self, name, type):
        self.name = name
        self.type = type

    @staticmethod
    def _config_checker(name, keys: list[str], config):
        for key in keys:
            if key not in config:
                print(f"[ERROR] config missing for {name}, please specify the {key} property")
                return False
        return True
