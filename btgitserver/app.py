import atexit
import gzip
import gunicorn.app.base
import logging
import random
import re
import sys
import subprocess

from btgitserver.args import parse_args
from btgitserver.config import AppConfig
from btgitserver.defaults import \
default_app_host_address, \
default_app_port, \
default_num_threads, \
default_num_workers, \
default_preload, \
default_repo_search_paths, \
default_ondemand_repo_search_paths, \
default_verify_tls
from btgitserver.logger import Logger

from hashlib import sha1
from dulwich import repo
from dulwich.pack import PackStreamReader
from flask_httpauth import HTTPBasicAuth
from flask import Flask, make_response, request, abort
from pathlib import Path

from io import BytesIO


# Private variables
__author__ = 'berttejeda'
__original_author = 'stewartpark'

# Read command-line args
args = parse_args()

# Initialize logging facility
logger_obj = Logger(
    logfile_path=args.logfile_path,
    logfile_write_mode=args.logfile_write_mode)
logger = logger_obj.init_logger('app')

verify_tls = args.no_verify_tls or default_verify_tls

# Flask
auth = HTTPBasicAuth()

# Initialize Config Readers
app_config = AppConfig().initialize(
  args=vars(args),
  verify_tls=verify_tls
)

git_ondemand_search_paths = args.ondemand_repo_search_paths or app_config.get('app.ondemand.search_paths', default_ondemand_repo_search_paths)
git_search_paths = args.repo_search_paths or app_config.get('app.search_paths', default_repo_search_paths)
git_search_paths = git_search_paths + git_ondemand_search_paths
app_host_address = args.host_address or app_config.get('app.listen', default_app_host_address)
app_port = args.port or app_config.get('app.port', default_app_port)
gunicorn_preload = args.preload or app_config.get('app.gunicorn.preload', default_preload)
gunicorn_threads = args.threads or app_config.get('app.gunicorn.threads', default_num_threads)
gunicorn_workers = args.workers or app_config.get('app.gunicorn.workers', default_num_workers)

authorized_users = app_config.auth.users
users = [u[0] for u in authorized_users.items()]

allowed_services = ('git-upload-pack', 'git-receive-pack')
valid_name_pattern = re.compile(r'^[A-Za-z0-9_-][A-Za-z0-9._-]*$')


class StandaloneApplication(gunicorn.app.base.BaseApplication):

    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {key: value for key, value in self.options.items()
                  if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application

def get_repos(org, search_paths):
    repo_map = {}

    for git_search_path in search_paths:
        fq_git_search_path = Path(git_search_path).expanduser().joinpath(org)
        logger.debug(f'Building git repo map ...')
        logger.debug(f'Adding git repos under {fq_git_search_path}')
        for p in Path(fq_git_search_path).glob("*"):
            dotgit = Path(p).joinpath(".git")
            if dotgit.is_dir():
                git_directory = p.as_posix()
                git_directory_name = p.name
                if git_directory_name:
                    repo_map[git_directory_name] = git_directory
    logger.debug(f'Finished building git repo map!')
    numrepos = len(list(repo_map.keys()))
    logger.debug(f'Found {numrepos} repo(s)')
    return repo_map


def fix_dangling_head(project_path):
    """Point HEAD at an existing branch if it refers to one that doesn't exist.

    New repos are initialized with HEAD -> refs/heads/master, so a first push
    of e.g. 'main' would otherwise leave clones with nothing to check out.
    """
    try:
        project_repo = repo.Repo(project_path)
        _, head_sha = project_repo.refs.follow(b'HEAD')
        if head_sha is not None:
            return
        branches = project_repo.refs.keys(base=b'refs/heads/')
        if not branches:
            return
        for preferred in (b'main', b'master'):
            if preferred in branches:
                branch = preferred
                break
        else:
            branch = sorted(branches)[0]
        logger.info(f'Pointing HEAD at refs/heads/{branch.decode()} for {project_path}')
        project_repo.refs.set_symbolic_ref(b'HEAD', b'refs/heads/' + branch)
        if not project_repo.bare:
            # Sync the (previously unborn) index and working tree with the new
            # HEAD, otherwise updateInstead rejects the next push to it
            subprocess.run(['git', 'reset', '--hard', '-q'], cwd=project_path, check=True)
    except Exception as e:
        logger.warning(f'Could not update HEAD for {project_path}: {e}')


def interrupt():
  logger.info("Stop API")

def start_api(**kwargs):
  """API functions.
  This function defines the API routes and starts the API Process.
  """
  app = Flask(__name__)
  # app.config['MAX_CONTENT_LENGTH'] = 1600 * 1024 * 1024 # 16GB
  # app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB

  @auth.get_password
  def get_pw(username):
      if username in users:
          credential = authorized_users.get(username).password
          return credential
      else:
          return None

  @app.before_request
  def validate_path_names():
      # Reject org/project names that could escape the repo search paths
      # (e.g. "..") or that aren't plain directory names
      for name in (request.view_args or {}).values():
          if not valid_name_pattern.match(name):
              abort(400)

  @app.route('/<string:org_name>/<string:project_name>/info/refs')
  @auth.login_required
  def info_refs(org_name, project_name):
      git_repo_map = get_repos(org_name, git_search_paths)
      available_repos = list(git_repo_map.keys())
      service = request.args.get('service')
      if service not in allowed_services:
          abort(400)

      logger.info(f'Receiving {org_name}/{project_name}')
      
      if project_name in available_repos:
          # Ensure receive.denyCurrentBranch is set to updateInstead for existing repos
          project_path = git_repo_map[project_name]
          try:
              project_repo = repo.Repo(project_path)
              project_repo_config = project_repo.get_config()
              try:
                  current_value = project_repo_config.get("receive", "denyCurrentBranch")
              except KeyError:
                  current_value = None
              if current_value not in (b"updateInstead", "updateInstead"):
                  logger.info(f'Setting receive.denyCurrentBranch to updateInstead for {project_path}')
                  project_repo_config.set("receive", "denyCurrentBranch", "updateInstead")
                  project_repo_config.write_to_path()
          except Exception as e:
              logger.warning(f'Could not set receive.denyCurrentBranch for {project_path}: {e}')
          return info_refs_header(
              git_repo_map=git_repo_map,
              project_name=project_name,
              service=service
          )
      elif service != 'git-receive-pack':
          # Only a push may create a repo; fetches/clones of unknown repos are a 404
          abort(404)
      else:
          logger.info(f'Repo at {org_name}/{project_name} does not currently exist, processing as on-demand')
          ondemand_search_path = random.choice(git_ondemand_search_paths)
          ondemand_org_path = Path(ondemand_search_path).expanduser().joinpath(org_name)
          ondemand_project_path = ondemand_org_path.joinpath(project_name).as_posix()
          try:
              if not ondemand_org_path.is_dir():
                  logger.info(f'Creating on-demand repo org path at {ondemand_org_path}')
                  ondemand_org_path.mkdir(parents=True)
              logger.info(f'Initializing on-demand repo {ondemand_project_path}')
              project_repo = repo.Repo.init(ondemand_project_path, mkdir=True)
              project_repo_config = project_repo.get_config()
              project_repo_config.set("receive", "denyCurrentBranch", "updateInstead")
              project_repo_config.write_to_path()
              logger.info(f'Initialization complete for {ondemand_project_path}')
          except Exception as e:
              logger.error(f"Could not create on-demand project path at {ondemand_project_path}, error was {e}")
              abort(500)
          git_repo_map = get_repos(org_name, git_search_paths)
          return info_refs_header(
              git_repo_map=git_repo_map,
              project_name=project_name,
              service=service
          )

  def info_refs_header(**kwargs):
    git_repo_map = kwargs['git_repo_map']
    project_name = kwargs['project_name']
    service = kwargs['service']
    project_path = [v for k, v in git_repo_map.items() if k == project_name][0]
    p = subprocess.Popen([service, '--stateless-rpc', '--advertise-refs', project_path], stdout=subprocess.PIPE)
    packet = '# service=%s\n' % service
    length = len(packet) + 4
    _hex = '0123456789abcdef'
    prefix = ''
    prefix += _hex[length >> 12 & 0xf]
    prefix += _hex[length >> 8 & 0xf]
    prefix += _hex[length >> 4 & 0xf]
    prefix += _hex[length & 0xf]
    data = prefix + packet + '0000'
    data = data.encode() + p.stdout.read()
    res = make_response(data)
    res.headers['Expires'] = 'Fri, 01 Jan 1980 00:00:00 GMT'
    res.headers['Pragma'] = 'no-cache'
    res.headers['Cache-Control'] = 'no-cache, max-age=0, must-revalidate'
    res.headers['Content-Type'] = 'application/x-%s-advertisement' % service
    p.wait()
    return res

  def get_request_body():
    # git gzips larger upload-pack (fetch) requests
    data = request.get_data()
    if request.headers.get('Content-Encoding') == 'gzip':
        data = gzip.decompress(data)
    return data

  @app.route('/<string:org_name>/<string:project_name>/git-receive-pack', methods=('POST',))
  @auth.login_required
  def git_receive_pack(org_name, project_name):
      git_repo_map = get_repos(org_name, git_search_paths)
      available_repos = list(git_repo_map.keys())
      if project_name in available_repos:
          project_path = [v for k,v in git_repo_map.items() if k == project_name][0]
          p = subprocess.Popen(['git-receive-pack', '--stateless-rpc', project_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
          data_in = get_request_body()
          # Not every receive-pack request carries a pack: git sends a bare
          # flush-pkt ("0000") probe before a large (chunked) push, and
          # delete-only pushes have no pack either.
          pack_start = data_in.find(b'PACK')
          if pack_start != -1 and logger.isEnabledFor(logging.DEBUG):
              try:
                  pack_file_io = BytesIO(data_in[pack_start:])
                  objects = PackStreamReader(sha1, pack_file_io.read, pack_file_io.read)
                  for obj in objects.read_objects():
                      if obj.obj_type_num == 1: # Commit
                          logger.debug(obj)
              except Exception as e:
                  logger.debug(f'Could not parse pack for logging: {e}')
          data_out, _ = p.communicate(input=data_in)
          res = make_response(data_out)
          res.headers['Expires'] = 'Fri, 01 Jan 1980 00:00:00 GMT'
          res.headers['Pragma'] = 'no-cache'
          res.headers['Cache-Control'] = 'no-cache, max-age=0, must-revalidate'
          res.headers['Content-Type'] = 'application/x-git-receive-pack-result'
          p.wait()
          fix_dangling_head(project_path)
          logger.info(f'Finished receiving {org_name}/{project_name}')
          return res
      else:
          abort(404)

  @app.route('/<string:org_name>/<string:project_name>/git-upload-pack', methods=('POST',))
  @auth.login_required
  def git_upload_pack(org_name, project_name):
      git_repo_map = get_repos(org_name, git_search_paths)
      available_repos = list(git_repo_map.keys())
      if project_name in available_repos:
          project_path = [v for k,v in git_repo_map.items() if k == project_name][0]
          p = subprocess.Popen(['git-upload-pack', '--stateless-rpc', project_path],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
          data, _ = p.communicate(input=get_request_body())
          res = make_response(data)
          res.headers['Expires'] = 'Fri, 01 Jan 1980 00:00:00 GMT'
          res.headers['Pragma'] = 'no-cache'
          res.headers['Cache-Control'] = 'no-cache, max-age=0, must-revalidate'
          res.headers['Content-Type'] = 'application/x-git-upload-pack-result'
          p.wait()
          return res
      else:
          abort(404)

  logger.info("Start API")

  options = {
      'bind': f'{app_host_address}:{app_port}',
      'preload': gunicorn_preload,
      'threads': gunicorn_threads,
      'workers': gunicorn_workers,
  }

  atexit.register(interrupt)
  if args.dev_server:
    app.run(host=app_host_address, port=app_port)
  else:
    StandaloneApplication(app, options).run()    

if __name__ == '__main__':
  start_api()
