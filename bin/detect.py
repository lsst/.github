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

import os
import re
import sys
from github import Github, UnknownObjectException

# Only process repos with this tag

DISTRIB_TAG = "w.2020.47"

# Check for Python lint Travis job, as that's all we know how to safely
# replace.

TRAVIS_YML_RE = rb"""sudo: false
language: python
matrix:
\s+include:
\s+- python: '3.[678]'
\s+install:
\s+- '?pip install -r <\(curl https://raw.githubusercontent.com/lsst/linting/master/requirements.txt\)'?
\s+script:\s+(- )?flake8\s*$"""

# Checks run by Travis

TRAVIS_LIKE_CHECKS = [
    'continuous-integration/travis-ci',
    'Travis CI - Branch',
    'Travis CI - Pull Request',
]

# Do initial setup.

g = Github(os.environ["GH_TOKEN"])
o = g.get_organization("lsst")

# Retrieve the template workflows.

template_repo = o.get_repo(".github")
null_yaml = (template_repo.get_contents("workflow-templates/null.yaml")
                     .decoded_content)
lint_yaml = (template_repo.get_contents("workflow-templates/lint.yaml")
                     .decoded_content)

# With no arguments, iterates through all repos.
# With one argument, checks that repo.
# With two arguments, uses those as range limits on the list of repos (useful
# to test on a semi-random subset).

if len(sys.argv) == 2:
    repo_list = [o.get_repo(sys.argv[1])]
else:
    repo_list = o.get_repos('public', 'full_name', 'asc')
    if len(sys.argv) >= 3:
        repo_list = repo_list[int(sys.argv[1]):int(sys.argv[2])]

for r in repo_list:
    command = f"update_repo.py {r.name}"
    print(f"{r.name}:")
    if r.archived:
        print(f"*** Skipping archived repo: {r.name}")
        continue
    if r.fork:
        print(f"*** Skipping forked repo: {r.name}")
        continue
    if DISTRIB_TAG not in [t.name for t in r.get_tags()]:
        print(f"*** Skipping repo not tagged with {DISTRIB_TAG}: {r.name}")
        continue

    if r.allow_rebase_merge:
        print(f"    * Should disable rebase merge: {r.name}")
    if r.allow_squash_merge:
        print(f"    * Should disable squash merge: {r.name}")

    b = r.get_branch(r.default_branch)
    if b.protected:
        p = b.get_protection()
    else:
        p = None
    try:
        t = r.get_contents(".travis.yml")
    except UnknownObjectException as e:
        print(f"    No .travis.yml: {r.name}")
        t = None

    # If non-flake8 travis, leave alone.
    if t and not re.match(TRAVIS_YML_RE, t.decoded_content):
        print(f"    Unrecognized .travis.yml, skipping {r.name}")
        print(t.decoded_content)
        continue

    try:
        w = r.get_contents(".github/workflows")
    except UnknownObjectException as e:
        print(f"    No .github/workflows: {r.name}")
        w = []

    status_check_minimum = []

    # If flake8 travis, unset travis checks, remove travis.
    if t:
        if (p and p.required_status_checks and
            any([c in TRAVIS_LIKE_CHECKS
                 for c in p.required_status_checks.contexts])):
            # Disable travis checks.
            print(f"    * Should remove travis check from {r.name}/{b.name}")
            contexts = [c for c in p.required_status_checks.contexts
                        if c not in TRAVIS_LIKE_CHECKS]
            print(f"    contexts={contexts}")
        print(f"    * Should remove .travis.yml from {r.name}")
        command += " --remove-travis"

        # If lint.yaml GHA, ensure lint GHA check.
        if w and any([f.name in ["lint.yaml", "lint.yml"] for f in w]):
            print(f"    lint.yaml found in {r.name}")
            status_check_minimum = "lint"
        else:
            # Add lint GHA, add lint GHA check.
            print(f"    * Should create lint.yaml in {r.name}")
            status_check_minimum = "lint"
            command += " --flake8"
    elif w:
        known_check_found = False
        for f in w:
            if f.name in ["lint.yaml", "lint.yml"]:
                print(f"    lint.yaml found in {r.name}")
                if f.decoded_content != lint_yaml:
                    print(f"*** lint.yaml differs from template")
                status_check_minimum = "lint"
                known_check_found = True
            if f.name in ["null.yaml", "null.yml"]:
                print(f"    null.yaml found in {r.name}")
                if f.decoded_content != null_yaml:
                    print(f"*** null.yaml differs from template")
                status_check_minimum = "null"
                known_check_found = True
        if not known_check_found:
            # If GHA and no travis, ensure GHA checks.
            print(f"*** Only non-flake8 GHAs found in {r.name}")
            status_check_minimum = None
    else:
        # If no travis and no GHA, add null GHA, add null_check GHA check
        print(f"    * Should create null.yaml in {r.name}")
        status_check_minimum = "null_check"
        command += " --null-check"

    # Check required status checks
    if not p:
        print(f"    Not protected: {r.name}/{b.name}")
        if status_check_minimum is None:
            print(f"*** Don't know which checks to require")
            continue
        print(f"    * Should add contexts=[{status_check_minimum}]")
    else:
        checks = p.required_status_checks
        if not checks:
            print(f"    No required status checks: {r.name}/{b.name}")
            if status_check_minimum is None:
                print(f"*** Don't know which checks to require")
                continue
            else:
                print(f"    * Should add contexts={[status_check_minimum]}")
        elif (not checks.strict
              or status_check_minimum not in checks.contexts
              or not p.enforce_admins):
            contexts = [c for c in checks.contexts
                        if c not in TRAVIS_LIKE_CHECKS]
            print(f"    Before: {contexts}")
            if status_check_minimum:
                if status_check_minimum not in checks.contexts:
                    contexts.append(status_check_minimum)
                    print(f"    * Should be: {contexts}")

    if command != f"update_repo.py {r.name}":
        print("$ " + command)
