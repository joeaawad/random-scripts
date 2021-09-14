"""Created by Joe Awad

From inside a repo on master branch, increment the repo version by the
specified increment type and create new tags for PATCH, MINOR, and MAJOR
versions that point to the current commit. If the tag already exists, delete
the old tag before creating the new one.
"""

import argparse
import git # pip install gitpython
import os
from pkg_resources import parse_version
import re

def prepare_repo(repo: git.Repo):
    if repo.active_branch.name != "master":
        raise RuntimeError("Can only create a new release from 'master' branch")

    try:
        repo.remotes.origin.pull("--tags")
    except (git.exc.GitCommandError):
        raise RuntimeError("Failed to pull from remote. Please run "
                           "`git pull --tags` and resolve any issues before "
                           "retrying")

def get_latest_version(tags: list) -> str:
    latest_version = parse_version("0.0.0")

    for tag_object in tags:
        # Only check full MAJOR.MINOR.PATCH tags
        if not re.match(r"[0-9]+\.[0-9]+\.[0-9]+", tag_object.name):
            continue

        version = parse_version(tag_object.name)

        if version > latest_version:
            latest_version = version

    latest_version_list = list(map(int, latest_version.base_version.split(".")))

    return latest_version_list

def increment_version(version_list: list, increment: str) -> list:
    if increment == "PATCH":
        version_list[2] += 1
    elif increment == "MINOR":
        version_list[1] += 1
        version_list[2] = 0
    elif increment == "MAJOR":
        version_list[0] += 1
        version_list[1] = 0
        version_list[2] = 0

    return version_list

def create_tag(version: str, message: str, repo: git.Repo):
    # delete old tag if it exists
    try:
        repo.delete_tag(version)
        repo.remotes.origin.push(f":{version}")
    except:
        pass

    repo.create_tag(version, message=message)
    repo.remotes.origin.push(version)

def main(increment: str, message: str):
    repo = git.Repo(os.getcwd())

    prepare_repo(repo)

    latest_version_list = get_latest_version(repo.tags)

    new_version_list = increment_version(latest_version_list, increment)

    patch_tag = ".".join(map(str, new_version_list))
    minor_tag = ".".join(map(str, new_version_list[:2]))
    major_tag = str(new_version_list[0])

    create_tag(patch_tag, message, repo)
    create_tag(minor_tag, message, repo)
    create_tag(major_tag, message, repo)

    print(f"Created the following tags: {patch_tag}, {minor_tag}, {major_tag}")

def parser():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "increment", choices=["MAJOR", "MINOR", "PATCH"],
        help="Increment to increase the version by")
    parser.add_argument(
        "message", type=str,
        help="Release summary to attach to the tags")

    return parser.parse_args()

if __name__ == "__main__":
    args = parser()

    main(args.increment, args.message)
