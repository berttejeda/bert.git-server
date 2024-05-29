from btgitserver.defaults import default_settings
from btgitserver.defaults import default_config_file_name
from btgitserver.logger import Logger
import os
from btconfig import Config

logger = Logger().init_logger(__name__)

class AppConfig():

  def __init__(self, **kwargs):
    pass

  def initialize(self, **kwargs):

    logger.info("Initializing config")
    args = kwargs.get('args', {})
    verify_tls = kwargs.get('verify_tls')
    # Initialize App Config
    initial_data = {
    'environment': os.environ
    }  

    config_file_uri = kwargs.get('config_file') or \
                      args.get('config_file') or \
                      default_config_file_name
    logger.info(f"Config file URI is {config_file_uri}")
    # Initialize App Config
    config = Config(
        config_file_uri=config_file_uri,
        default_value=default_settings,
        initial_data=initial_data,
        args=args,
        warn_if_config_not_found=True,
        verify_tls=verify_tls
    )

    settings = config.read()

    return settings