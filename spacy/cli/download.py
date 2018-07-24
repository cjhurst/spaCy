# coding: utf8
from __future__ import unicode_literals

import plac
import requests
import os
import subprocess
import sys
import pkg_resources

from ._messages import Messages
from .link import link
from ..util import prints, get_package_path, get_data_path, get_model_meta, is_package
from .. import about
from ..compat import path2str

@plac.annotations(
    model=("model to download, shortcut or name)", "positional", None, str),
    direct=("force direct download. Needs model name with version and won't "
            "perform compatibility check", "flag", "d", bool),
    silent=("force direct download. Needs model name with version and won't "
            "perform compatibility check", "flag", "s", bool),
    pip_args=("additional arguments to be passed to `pip install` when "
              "installing the model")
)
def download(model, direct=False, silent=False, *pip_args):
    """
    Download compatible model from default download path using pip. Model
    can be shortcut, model name or, if --direct flag is set, full model name
    with version.
    """
    if direct:
        dl = download_model('{m}/{m}.tar.gz#egg={m}'.format(m=model), pip_args, silent)
        if silent:
            return dl

    else:
        shortcuts = get_json(about.__shortcuts__, "available shortcuts")
        model_name = shortcuts.get(model, model)
        compatibility = get_compatibility()
        version = get_version(model_name, compatibility)

        dl = download_model('{m}-{v}/{m}-{v}.tar.gz#egg={m}=={v}'
                            .format(m=model_name, v=version), pip_args, silent)
        if silent:
            return dl

        if dl.returncode != 0:  # if download subprocess doesn't return 0, exit
            sys.exit(dl.returncode)

        try:
            # Get package path here because link uses
            # pip.get_installed_distributions() to check if model is a
            # package, which fails if model was just installed via
            # subprocess
            package_path = get_package_path(model_name)
            link(model_name, model, force=True, model_path=package_path)

        except:
            # Dirty, but since spacy.download and the auto-linking is
            # mostly a convenience wrapper, it's best to show a success
            # message and loading instructions, even if linking fails.
            prints(Messages.M001.format(name=model_name), title=Messages.M002)
            return dl
        return dl


def run_in_shell(cmd, silent=False):
    if silent:
        print(silent)
        # If silent we return Popen object with open pipes
        dl = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=os.environ.copy())
        print(dl)
        # wait for the process to finish so it has a return code.
        dl.wait()
        return dl
    else:
        # If not silent, return Popen object but don't redirect the pipes
        dl = subprocess.Popen(cmd, env=os.environ.copy(), stdout=None, stderr=None)
        # wait for the process to finish so it has a return code.
        dl.wait()
        return dl


def get_pkg_for_link(name):
    shortcut_path = get_data_path() / name  # path to shortcut link
    meta = get_model_meta(shortcut_path)
    model_pkg_name = '{}_{}'.format(meta['lang'], meta['name']).replace('_', '-')
    shortcut_dest = shortcut_path.resolve().parent
    dist = [d for d in pkg_resources.working_set
            if d.module_path == path2str(shortcut_dest)  # in same root directory
            and d.project_name == model_pkg_name]        # package name matches
    if dist:
        return dist[0].project_name.replace('-', '_')


def uninstall_model(model_name, silent=False):
    cmd = [sys.executable, '-m', 'pip', 'uninstall']
    if silent:
        cmd.append('-y')
    cmd.append(model_name)
    return run_in_shell(cmd, silent)


def uninstall(name, silent=False):

    if is_package(name):  # great, name is an installed package
        return uninstall_model(name, silent)

    link_path = get_data_path() / name

    print(link_path)

    if link_path.exists():  # name is a shortcut link
        pkg_name = get_pkg_for_link(name)
        if pkg_name:  # great, link maps to installed package
            return uninstall_model(pkg_name, silent)


def get_json(url, desc):
    r = requests.get(url)
    if r.status_code != 200:
        prints(Messages.M004.format(desc=desc, version=about.__version__),
               title=Messages.M003.format(code=r.status_code), exits=1)
    return r.json()


def get_compatibility():
    version = about.__version__
    version = version.rsplit('.dev', 1)[0]
    comp_table = get_json(about.__compatibility__, "compatibility table")
    comp = comp_table['spacy']
    if version not in comp:
        prints(Messages.M006.format(version=version), title=Messages.M005,
               exits=1)
    return comp[version]


def get_version(model, comp):
    model = model.rsplit('.dev', 1)[0]
    if model not in comp:
        prints(Messages.M007.format(name=model, version=about.__version__),
               title=Messages.M005, exits=1)
    return comp[model][0]


def download_model(filename, user_pip_args=None, silent=False):
    download_url = about.__download_url__ + '/' + filename
    pip_args = ['--no-cache-dir', '--no-deps']
    if user_pip_args:
        pip_args.extend(user_pip_args)
    cmd = [sys.executable, '-m', 'pip', 'install'] + pip_args + [download_url]
    return run_in_shell(cmd, silent)
