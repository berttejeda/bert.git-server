## Overview

A git server implementation written in python.

Based off the amazing work by Stewart Park in this gist: [https://gist.github.com/stewartpark/1b079dc0481c6213def9](https://gist.github.com/stewartpark/1b079dc0481c6213def9).

Features:

- Makes any git repository lying below the _search\_paths_ setting
  available for `git clone` and `git push` via HTTP using basic authentication
- Application defaults can be overridden by specifying a configuration file<br />
  Review [etc/config.yaml](etc/config.yaml) for a sample data structure.
- On-demand repos: If you attempt to push a non-existing repo to the server, it will be created 

## Installation

- Install from pypi.org: `pip install btgitserver`
- Install directly from git repo: `pip install git+http://www.github.com/berttejeda/bert.gt-server.git`

## Usage

To get usage information and help: `bt.git-server -h`

### Clone paths

These are the routes accepted by the script:

- '/<org_name>/<project_name>'

These routes mirror the directory structure under the git search path(s).

### Authentication
  
For now, the only authentication available is HTTP AUTH BASIC

As such, the default credentials are:

Username: `git-user`
Password: `git-password`

### Usage Examples

#### Clone a repo

* Create a test org and repo:

```
cd ~
mkdir -p /tmp/repos/contoso/test
cd /tmp/repos/contoso/test
git init .
git checkout -b main
touch test_file.txt
git add .
git commit -m 'Initial Commit'
cd ~
bt.git-server -r /tmp/repos
```

**Note**: The `--repo-search-paths/-r` cli option allows specifying 
multiple, space-delimitted search paths, e.g. `bt.git-server -r /tmp/repos /tmp/repos2`

* Launch the standalone git server

`bt.git-server`

You should see output similar to:
```
Running on http://0.0.0.0:5000/	
```

* On client-side:

Try cloning the repo you just created via the supported routes:

e.g.
	
```bash
git clone http://git-user:git-password@127.0.0.1:5000/contoso/test
```

#### Push an on-demand repo

```
mkdir -p foo-bar
cd foo-bar
git init .
git remote add origin http://git-user:git-password@127.0.0.1:5000/contoso/foo-bar
git checkout -b main
touch test_file.txt
git add .
git commit -m 'Initial Commit'
git push --set-upstream origin $(git rev-parse --abbrev-ref HEAD)
```