import os

# SSL Requests
default_verify_tls = True

# Flask app settings
debug = False
app_name = "Python Git Server"
default_app_port = 5000
default_config_file_name = 'config.yaml'
default_app_host_address = '0.0.0.0'
default_repo_search_paths = ['~/git-server/repos']
default_ondemand_repo_search_paths = ['~/git-server/repos.ondemand']
default_num_workers = 4
default_num_threads = 8
default_preload = True
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
    "ondemand": {
      "search_paths": default_ondemand_repo_search_paths
    },
    "gunicorn": {
      "workers": default_num_workers, 
      "threads": default_num_threads, 
      "preload": default_preload
    }
  }
}