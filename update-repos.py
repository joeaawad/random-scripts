"""Created by Joe Awad

Update a string in all repos an organization owns that match a given name regex
or repo topic.  Or just pass in a list of repos.

A common use case is if you have all repos that use a certain tool include the
tool name in the repo name or topic list and you would like to update the
pinned version of a package across the entire organization.

Must have https://github.com/ggreer/the_silver_searcher#installing installed
if you're not providing a target_file
"""

import argparse
import fileinput
import git # pip install gitpython
import github # pip install pygithub
import os
import subprocess
import tempfile
from time import sleep

def get_repo_names(org_name: str, repo_list: list, repo_regex: str, repo_topic: str,
                   ignore_repos: list) -> list:
    # if user specifys a list of repos, skip expensive github api call
    if repo_list:
        return repo_list
    repos = []

    org = gh.get_organization(org_name)
    all_repos = org.get_repos()

    for repo in all_repos:
        if repo.name in ignore_repos:
            continue
        if repo_regex and repo_regex in repo.name:
            repos.append(repo.name)
        if repo_topic and repo_topic in repo.get_topics():
            repos.append(repo.name)

    return repos

def get_file_paths(repo_path: str, target: str) -> list:
    # Subprocess out to ag since it's much more efficient
    raw_result = subprocess.run(["ag", "-l", target], cwd=repo_path,
                                capture_output=True)
    return raw_result.stdout.decode("utf-8").splitlines()

def update_file(file_path: str, target: str, replacement: str):
    try:
        with fileinput.FileInput(file_path, inplace=True) as file:
            for line in file:
                print(line.replace(target, replacement), end='')
    except FileNotFoundError:
        print(f"WARNING: File {file_path} was not found.")

def update_repo(
        org_name: str, repo_name: str, work_dir: str,
        branch_name: str, commit_message: str,
        target_file: str, target: str, replacement: str, pr: bool) -> str:
    remote_repo = gh.get_repo(f"{org_name}/{repo_name}")
    base_branch = remote_repo.default_branch
    repo_path = os.path.join(work_dir, repo_name)

    try:
        repo = git.Repo(repo_path)
        repo.git.checkout(base_branch)
        repo.git.reset("--hard", "origin/%s" % base_branch)
        repo.git.pull("origin", base_branch)

    except git.exc.NoSuchPathError:
        print(f"Cloning {repo_name} to {repo_path}")
        repo = git.Repo.clone_from(remote_repo.ssh_url, repo_path)

    if target_file:
        file_paths = [target_file]
    else:
        file_paths = get_file_paths(repo_path, target)
        if not file_paths:
            print(f"No matches found in or changes made to {repo_name}")
            return
        print(f"Matches found in: {file_paths}")

    for file_path in file_paths:
        update_file(
            os.path.join(repo_path, file_path),
            target,
            replacement)

    branch = repo.create_head(branch_name)
    branch.checkout()

    try:
        repo.git.commit("-a", "-m", commit_message)
    except (git.exc.GitCommandError):
        print(f"No matches found in or changes made to {repo_name}")
        return

    if pr:
        return create_pr(repo, remote_repo, repo_name, base_branch, branch_name,
                         commit_message)
    else:
        return [f"{repo_name}/{file_path}" for file_path in file_paths]

def create_pr(
        repo, remote_repo, repo_name: str, base_branch: str, branch_name: str,
        commit_message: str) -> str:
    repo.git.push()
    sleep(1) # To avoid GitHub rate limiting if updating more than 10 repos
    pr = remote_repo.create_pull(
        title=commit_message,
        body="", # required or the package assumes the PR is based on an issue
        head=branch_name,
        base=base_branch)

    print(f"Created {pr.html_url}")
    return [pr.html_url]

def main(org_name: str, repo_list: list, repo_regex: str, repo_topic: str, ignore_repos: list,
         branch_name: str, commit_message: str,
         target_file: str, target: str, replacement: str, work_dir: str, pr: bool):
    results = []

    if not repo_regex and not repo_topic and not repo_list:
        raise ValueError("Must specify repo_list, repo-regex, or repo-topic")

    if repo_list and (repo_regex or repo_topic):
        raise ValueError("It's an error to specify a repo list and a regex / topic!")

    if branch_name == "master" or branch_name == "main":
        raise ValueError("--branch-name is the name of your topic branch, it shouldn't be %s!" % branch_name)

    print("Gathering list of repos, this may be slow if the organization owns "
          "a lot of repos.")
    repo_names = get_repo_names(org_name, repo_list, repo_regex, repo_topic, ignore_repos)
    print(f"The following repos will be checked: {repo_names}")

    if not work_dir:
      work_dir = tempfile.TemporaryDirectory().name
      print(f"Directory created at {work_dir}")

    for repo_name in repo_names:
        result_paths = update_repo(
            org_name, repo_name, work_dir, branch_name,
            commit_message, target_file, target, replacement, pr)

        if result_paths is not None:
            results.extend(result_paths)

    print()
    if not results:
        print("No matches found or changes made")
    else:
        if pr:
            print("Finished, created the following PRs:")
        else:
            print(f"Changed the following files in {work_dir}:")
        for path in results:
            print(path)
        if not pr:
            print("\nRerun this command with '--pr' if you would like the "
                  "changes to be pushed up and a PR opened.")

def parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--org-name", required=True, help="Github Organization")
    parser.add_argument(
        "--repo-list", default=[], nargs="*",
        help="List of repos that need to be changed")
    parser.add_argument(
        "--repo-regex",
        help="Repo name regex to determine which repos to change")
    parser.add_argument(
        "--repo-topic",
        help="Repo topic to determine which repos to change")
    parser.add_argument(
        "--ignore-repos", default=[], nargs="*",
        help="List of names of repos to skip")
    parser.add_argument(
        "--branch-name", required=True, help="Name to create the branch with")
    parser.add_argument(
        "--commit-message", required=True, help="Commit message")
    parser.add_argument(
        "--target-file",
        help="Path within the repo of the file to do the replacement in, "
             "default searches all files")
    parser.add_argument(
        "--target", required=True, help="String to find and replace")
    parser.add_argument(
        "--replacement", required=True,
        help="String to replace --target with")
    parser.add_argument(
        "--work-dir",
        help="Path where the git clones should live. WARNING: this is going to run git reset --hard, so dont pick the same dir that you use for manual edits!")
    parser.add_argument(
        "--pr", action="store_true",
        help="If the change should be pushed up and a PR created")

    return parser.parse_args()

if __name__ == "__main__":
    args = parser()

    gh = github.Github(os.getenv("GITHUB_TOKEN"))

    main(
        args.org_name,
        args.repo_list,
        args.repo_regex,
        args.repo_topic,
        args.ignore_repos,
        args.branch_name,
        args.commit_message,
        args.target_file,
        args.target,
        args.replacement,
        args.work_dir,
        args.pr)
