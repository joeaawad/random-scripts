"""Created by Joe Awad

Update a string in a file that exists in all repos an organization owns that
match a given name regex.

A common use case is if you have all repos that use a certain tool include the
tool name in the repo name and you would like to update the pinned version of
a package across the entire organization.
"""

import argparse
import fileinput
import git # pip install gitpython
import github # pip install pygithub
import os
import tempfile

def get_repo_names(org_name: str, repo_regex: str,
                   ignore_repos: list) -> list:
    repos = []

    org = gh.get_organization(org_name)
    all_repos = org.get_repos()

    for repo in all_repos:
        if repo_regex in repo.name and repo.name not in ignore_repos:
            repos.append(repo.name)

    return repos

def update_file(file_path: str, target: str, replacement: str):
    with fileinput.FileInput(file_path, inplace=True) as file:
        for line in file:
            print(line.replace(target, replacement), end='')

def update_repo(
        org_name: str, repo_name: str, parent_directory: str,
        branch_name: str, commit_message: str, file_name: str,
        target: str, replacement: str) -> str:
    remote_repo = gh.get_repo(f"{org_name}/{repo_name}")

    repo_path = os.path.join(parent_directory, repo_name)
    print(f"Cloning {repo_name} to {repo_path}")
    repo = git.Repo.clone_from(remote_repo.ssh_url, repo_path)

    update_file(
        os.path.join(repo_path, file_name),
        target,
        replacement)

    branch = repo.create_head(branch_name)
    branch.checkout()
    repo.git.commit(
        "-a",
        "-m",
        commit_message)
    repo.git.push()
    pr = remote_repo.create_pull(
        title=commit_message,
        body="", # required or the package assumes the PR is based on an issue
        head=branch_name,
        base="master")

    print(f"Created {pr.html_url}")
    return pr.html_url

def main(org_name: str, repo_regex: str, ignore_repos: list,
         branch_name: str, commit_message: str,
         file_name: str, target: str, replacement: str):
    pr_links = []
    parent_directory = tempfile.TemporaryDirectory().name

    print(f"Directory created at {parent_directory}")

    repo_names = get_repo_names(org_name, repo_regex, ignore_repos)

    print(f"The following repos will be updated: {repo_names}")

    for repo_name in repo_names:
        pr_url = update_repo(
            org_name, repo_name, parent_directory, branch_name,
            commit_message, file_name, target, replacement)

        pr_links.append(pr_url)

    print("Finished, created the following PRs:")
    for url in pr_links:
        print(url)


def parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "org_name", help="Github Organization")
    parser.add_argument(
        "repo_regex",
        help="Regex to determine what repo names to change")
    parser.add_argument(
        "--ignore_repos", default=[],
        help="List of names of repos to skip")
    parser.add_argument(
        "branch_name", help="Name to create the branch with")
    parser.add_argument(
        "commit_message", help="Commit message")
    parser.add_argument(
        "file_name", help="Name of the file to do the replacement in")
    parser.add_argument(
        "target", help="String to find and replace")
    parser.add_argument(
        "replacement", help="String to replace old_string with")

    return parser.parse_args()

if __name__ == "__main__":
    args = parser()

    gh = github.Github(os.getenv("GITHUB_TOKEN"))

    main(
        args.org_name,
        args.repo_regex,
        args.ignore_repos,
        args.branch_name,
        args.commit_message,
        args.file_name,
        args.target,
        args.replacement)
