import errno
import os
import shutil
import sys

def make_sure_dir_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def _config_template():
    return os.path.join(sys.path[0], "darkwallet.cfg")

def make_sure_file_exists(filename):
    if not os.path.isfile(filename):
        print("Initializing new darkwallet.cfg.")
        shutil.copyfile(_config_template(), filename)

def list_files(path):
    return [filename for filename in os.listdir(path)
            if os.path.isfile(os.path.join(path, filename))]

