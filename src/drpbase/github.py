import os
import sys
from . import constant

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from isggithub.github import GitHub


class GithubInstance:
    def __init__(self, github_conf: dict):
        constant.GITHUB = GitHub(github_conf)
