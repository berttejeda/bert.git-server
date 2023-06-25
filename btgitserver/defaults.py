import os

# SSL Requests
default_verify_tls = True

# Flask app settings
debug = False
app_name = "Python Git Server"
default_app_port = 5000
default_config_file_name = 'config.yaml'
default_app_host_address = '0.0.0.0'
default_repo_search_paths = ['~/repos']
default_num_workers = 4
default_settings = {
  "auth": {
    "users": {
      "git-user": {
        "password": "git-password"
      }
    }
  },
  "app": {
    "debug": debug,
    "listen": default_app_host_address,
    "port": default_app_port,
    "search_paths": default_repo_search_paths,
    "workers": default_num_workers
  }
}