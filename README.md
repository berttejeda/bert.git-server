## Overview

A git server implementation written in python.

Based off the amazing work by Stewart Park in this gist: [https://gist.github.com/stewartpark/1b079dc0481c6213def9](https://gist.github.com/stewartpark/1b079dc0481c6213def9).

The app makes any git repository lying below the _search\_paths_ 
available for `git clone` via HTTP using basic authentication.

Application defaults can be overridden by specifying a configuration file.

Review [etc/config.yaml](etc/config.yaml) for a sample data structure.

## Installation

- Install from pypi.org: `pip install btgitserver`
- Install directly from git repo: `pip install git+http://www.github.com/berttejeda/bert.gt-server.git`

## Usage

To get usage information and help: `git-server -h`

### Clone paths

There are two routes accepted by the script:

- '/example/<project name>'
- '/<project name>'

All resolve to the same underlying repository path.

This effectively allows you to mock organizational structures.

TODO: Define additional routes dynamically as opposed to hard-coding.

### Usage Examples

Quick test:

* Create a test repo:

```
mkdir -p /tmp/repos/test
cd /tmp/repos/test
git init .
touch test_file.txt
git add .
git commit -m 'Initial Commit'
git-server -r /tmp/repos
```

**Note**: The `--repo-search-paths/-r` cli option allows specifying 
multiple, space-delimitted search paths, e.g. `git-server -r /tmp/repos /tmp/repos2`

* Launch the standalone git server

`git-server`

You should see output similar to:
```
Running on http://0.0.0.0:5000/	
```

* On client-side:

Try cloning the repo you just created via the supported routes:

e.g.
	
```bash
git clone http://127.0.0.1:5000/test.git
git clone http://127.0.0.1:5000/example/test.git
```
