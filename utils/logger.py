from icecream import ic
import os

def setup_ic():
    is_production = os.getenv("PRODUCTION", "False").lower() in ("true", "1", "yes")
    if is_production:
        ic.disable()
    else:
        ic.enable()
    return ic

show = setup_ic()