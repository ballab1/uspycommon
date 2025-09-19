import os
import sys
from . import constant

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from isggithubapp.githubapp import GitHubApp
from .utils import Utils


class GithubAppInstances:
    """
    This class creates multiple GitHubApp as specified in the configuration and caches them in a dictionary against the app name as kay.
    """

    def __init__(self, github_app_conf: dict):
        constant.GITHUB_APPS = {}
        baseapi = github_app_conf["base_url"]
        private_key_mount_path = github_app_conf["private_key_mount_path"]
        githubapps = github_app_conf["apps"]
        for app in githubapps:
            private_key = Utils.get_secret(
                key=app["app_private_key"],
                mount_path=private_key_mount_path,
                retry_attempt=0,
            )
            constant.GITHUB_APPS[app["name"]] = GitHubApp(
                baseapi, app["app_id"], private_key, github_app_conf
            )
