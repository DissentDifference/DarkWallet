import errno
import os
import shutil

def make_sure_dir_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def make_sure_file_exists(filename):
    if not os.path.isfile(filename):
        print("Initializing new darkwallet.cfg.")
        shutil.copyfile("darkwallet.cfg", filename)

