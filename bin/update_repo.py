# This file is part of lsst/.github
#
# Developed for the LSST Data Management System.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import argparse
import os
import re
from github import Github

# Checks run by Travis

TRAVIS_LIKE_CHECKS = [
    'continuous-integration/travis-ci',
    'Travis CI - Branch',
    'Travis CI - Pull Request',
]

# Parse the command-line arguments.

parser = argparse.ArgumentParser(
    description="Update GitHub repo actions and branch protections."
)
parser.add_argument("repo")
parser.add_argument("--remove-travis", dest="travis", action="store_true")
parser.add_argument("--null-check", dest="null", action="store_true")
parser.add_argument("--flake8", dest="lint", action="store_true")
parser.add_argument("--shellcheck", dest="shellcheck", action="store_true")
parser.add_argument("--yamllint", dest="yamllint", action="store_true")
parser.add_argument("--org", dest="org", default="lsst")
parser.add_argument("--tag", dest="tag", default="w.2020.47")
parser.add_argument("--user", dest="user", default=None)
args = parser.parse_args()

# Initialize the GitHub interface and access the desired repo.

github = Github(os.environ["GH_TOKEN"])
if args.user:
    repo = github.get_user(args.user).get_repo(args.repo)
else:
    repo = github.get_organization(args.org).get_repo(args.repo)
template_repo = github.get_repo("lsst/.github")

print(f"{repo.name}:")

# Sanity checks to make sure we aren't doing something dangerous.

assert not repo.archived
assert not repo.fork
if args.org == "lsst" and not args.user:
    assert args.tag in [tag.name for tag in repo.get_tags()]

# Set the merge conditions.

print("* Turning off rebase/squash merges")
repo.edit(allow_rebase_merge=False, allow_squash_merge=False,
          delete_branch_on_merge=True)

# Disable branch protection for admins temporarily.
# Remove any Travis checks from the branch protections.

branch = repo.get_branch(repo.default_branch)
branch.edit_protection(enforce_admins=False)
if args.travis and branch.protected:
    prot = branch.get_protection()
    if prot.required_status_checks:
        contexts = prot.required_status_checks.contexts
        new_contexts = [c for c in contexts if c not in TRAVIS_LIKE_CHECKS]
        print(f"* Changing {contexts} to {new_contexts}")
        branch.edit_protection(strict=True, contexts=new_contexts)
else:
    prot = None

# Remove Travis workflow.

if args.travis:
    print("* Removing .travis.yml")
    travis = repo.get_contents(".travis.yml")
    repo.delete_file(".travis.yml", "Remove Travis workflow.", travis.sha)

# Add new workflow(s).

new_contexts = set()
if args.lint:
    print("* Creating lint.yaml")
    lint_yaml = template_repo.get_contents(
        "workflow-templates/lint.yaml").decoded_content
    repo.create_file(".github/workflows/lint.yaml",
                  "Add Python lint GitHub Action.", lint_yaml)
    new_contexts.add("lint")
if args.shellcheck:
    print("* Creating shellcheck.yaml")
    shellcheck_yaml = template_repo.get_contents(
        "workflow-templates/shellcheck.yaml").decoded_content
    repo.create_file(".github/workflows/shellcheck.yaml",
                  "Add shellcheck GitHub Action.", shellcheck_yaml)
    new_contexts.add("shellcheck")
if args.yamllint:
    print("* Creating yamllint.yaml")
    yamllint_yaml = template_repo.get_contents(
        "workflow-templates/yamllint.yaml").decoded_content
    repo.create_file(".github/workflows/yamllint.yaml",
                  "Add YAML lint GitHub Action.", yamllint_yaml)
    new_contexts.add("lint")
if args.null:
    print("* Creating null.yaml")
    null_yaml = template_repo.get_contents(
        "workflow-templates/null.yaml").decoded_content
    repo.create_file(".github/workflows/null.yaml",
                  "Add null GitHub Action.", null_yaml)
    new_contexts.add("null_check")

# Turn on required status checks, enforce up-to-date branches, and restore
# enforcement for admins.

if prot and prot.required_status_checks:
    contexts = prot.required_status_checks.contexts
    print(f"Old contexts={contexts}")
    new_contexts.update(contexts)
print(f"* Setting strict protection contexts={new_contexts}")
branch.edit_protection(strict=True, contexts=list(new_contexts),
                       enforce_admins=True)
