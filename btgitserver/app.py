from btgitserver.args import parse_args
from btgitserver.config import AppConfig
from btgitserver.defaults import default_app_port, \
default_app_host_address, \
default_repo_search_paths, \
default_verify_tls
from btgitserver.logger import Logger

from dulwich.pack import PackStreamReader
import subprocess
from flask_httpauth import HTTPBasicAuth
from flask import Flask, make_response, request, abort
from pathlib import Path
import sys
if sys.version_info[0] == 2:
    from StringIO import StringIO
if sys.version_info[0] >= 3:
    from io import StringIO

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
app = Flask(__name__)
auth = HTTPBasicAuth()

# Initialize Config Readers
app_config = AppConfig().initialize(
  args=vars(args),
  verify_tls=verify_tls
)

git_search_paths = args.repo_search_paths or app_config.get('app.search_paths', default_repo_search_paths)
git_repo_map = {}

for git_search_path in git_search_paths:
  fq_git_search_path = Path(git_search_path).expanduser()
  logger.info(f'Building git repo map ...')
  logger.info(f'Adding git repos under {fq_git_search_path}')
  for p in Path(fq_git_search_path).rglob("*"):
      if p.is_dir() and p.name == '.git':
        git_directory = p.parent.as_posix()
        git_directory_name = p.parent.name
        if git_directory_name:
          git_repo_map[git_directory_name] = git_directory
  logger.info(f'Finished building git repo map!')

numrepos = len(list(git_repo_map.keys()))
logger.info(f'Found {numrepos} repo(s)')

authorized_users = app_config.auth.users
users = [u[0] for u in authorized_users.items()]
available_repos = list(git_repo_map.keys())

def start_api():
  """API functions.
  This function defines the API routes and starts the API Process.
  """

  @auth.get_password
  def get_pw(username):
      if username in users:
          credential = authorized_users.get(username).password
          return credential
      else:
          return None

  @app.route('/example/<string:project_name>/info/refs')
  @app.route('/<string:project_name>/info/refs')
  @auth.login_required
  def info_refs(project_name):
      service = request.args.get('service')
      if service[:4] != 'git-':
          abort(500)

      if project_name in available_repos:
          project_path = [v for k,v in git_repo_map.items() if k == project_name][0]
          p = subprocess.Popen([service, '--stateless-rpc', '--advertise-refs', project_path], stdout=subprocess.PIPE)
          packet = '# service=%s\n' % service
          length = len(packet) + 4
          _hex = '0123456789abcdef'
          prefix = ''
          prefix += _hex[length >> 12 & 0xf]
          prefix += _hex[length >> 8  & 0xf]
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
      else:
          abort(501)

  @app.route('/example/<string:project_name>/git-receive-pack', methods=('POST',))
  @app.route('/<string:project_name>/git-receive-pack', methods=('POST',))
  @auth.login_required
  def git_receive_pack(project_name):
      if project_name in available_repos:
          project_path = [v for k,v in git_repo_map.items() if k == project_name][0]
          p = subprocess.Popen(['git-receive-pack', '--stateless-rpc', project_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
          data_in = request.data
          pack_file = data_in[data_in.index('PACK'):]
          objects = PackStreamReader(StringIO(pack_file).read)
          for obj in objects.read_objects():
              if obj.obj_type_num == 1: # Commit
                  print(obj)
          p.stdin.write(data_in)
          data_out = p.stdout.read()
          res = make_response(data_out)
          res.headers['Expires'] = 'Fri, 01 Jan 1980 00:00:00 GMT'
          res.headers['Pragma'] = 'no-cache'
          res.headers['Cache-Control'] = 'no-cache, max-age=0, must-revalidate'
          res.headers['Content-Type'] = 'application/x-git-receive-pack-result'
          p.wait()
          return res
      else:
          abort(501)

  @app.route('/example/<string:project_name>/git-upload-pack', methods=('POST',))
  @app.route('/<string:project_name>/git-upload-pack', methods=('POST',))
  @auth.login_required
  def git_upload_pack(project_name):
      if project_name in available_repos:
          project_path = [v for k,v in git_repo_map.items() if k == project_name][0]
          p = subprocess.Popen(['git-upload-pack', '--stateless-rpc', project_path],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
          p.stdin.write(request.data)
          p.stdin.close()
          data = p.stdout.read()
          res = make_response(data)
          res.headers['Expires'] = 'Fri, 01 Jan 1980 00:00:00 GMT'
          res.headers['Pragma'] = 'no-cache'
          res.headers['Cache-Control'] = 'no-cache, max-age=0, must-revalidate'
          res.headers['Content-Type'] = 'application/x-git-upload-pack-result'
          p.wait()
          return res
      else:
          abort(501)

  logger.info("Start API")

  app_port = args.port or app_config.get('app.port') or default_app_port
  app_host_address = args.host_address or app_config.get('app.address') or default_app_host_address
  app.run(host=app_host_address, port=app_port)

  logger.info("Stop API")

def main():
  """The main entrypoint
  """

  start_api()

if __name__ == '__main__':
  main()


