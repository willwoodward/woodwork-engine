import logging
from woodwork.components.outputs.console import console
from woodwork.utils import format_kwargs

log = logging.getLogger(__name__)


class cli(console):
    """CLI output component - alias for console output"""
    
    def __init__(self, **config):
        format_kwargs(config, type="cli")
        super().__init__(**config)
        log.debug("Creating CLI output component...")