import os
import sys
import subprocess
import shutil
from glob import glob

# ----------------------------------------------------------------------
#   Logging.
# ----------------------------------------------------------------------
import logging
import logging.handlers
APP_NAME = 'build_deps'
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
logger = logging.getLogger(APP_NAME)
# ----------------------------------------------------------------------

def build_zlib(zlib_directory, deps_directory):
    logger = logging.getLogger("%s.build_zlib" % (APP_NAME, ))
    logger.debug("entry. zlib_directory: %s, deps_directory: %s" % (zlib_directory, deps_directory))
    cmd = r"nmake -f win32/Makefile.msc"
    logger.debug("executing: %s" % (cmd, ))
    proc = subprocess.Popen(cmd,
                            cwd=zlib_directory,
                            stdout=subprocess.PIPE)
    for line in proc.stdout:
        print line.rstrip("\n")
    proc.wait()

    output_file = os.path.join(zlib_directory, "zlib.lib")
    if not os.path.isfile(output_file):
        logger.error("Cannot file output file: %s" % (output_file, ))
        return
    destination = os.path.join(deps_directory, "zlib.lib")
    shutil.copy(output_file, destination)

def build_openssl(openssl_directory, deps_directory):
    logger = logging.getLogger("%s.build_openssl" % (APP_NAME, ))
    logger.debug("entry. openssl_directory: %s, deps_directory: %s" % (openssl_directory, deps_directory))
    cmd = r"ms\32all.bat"
    logger.debug("executing: %s" % (cmd, ))
    proc = subprocess.Popen(cmd,
                            cwd=openssl_directory,
                            stdout=subprocess.PIPE,
                            shell=True)
    for line in proc.stdout:
        print line.rstrip("\n")
    proc.wait()

    output_files = ["libeay32.lib", "ssleay32.lib"]
    output_directory = os.path.join(openssl_directory, "out32")
    for filename in output_files:
        source = os.path.join(output_directory, filename)
        if not os.path.isfile(source):
           logger.error("Cannot find output file: %s" % (output_file, ))
           return
        destination = os.path.join(deps_directory, filename)
        shutil.copy(source, destination)

def build_libssh2(libssh2_directory, deps_directory):
    logger = logging.getLogger("%s.build_libssh2" % (APP_NAME, ))
    logger.debug("entry. libssh2_directory: %s, deps_directory: %s" % (libssh2_directory, deps_directory))

    sln_filepath = os.path.join(libssh2_directory, "win32", "libssh2.sln")
    if not os.path.isfile(sln_filepath):
        logger.error("MSVC solution file %s does not exist." % (sln_filepath, ))
        return
    cmd = r"msbuild.exe %s /p:Configuration=LIB_Release" % (sln_filepath, )
    logger.debug("executing: %s" % (cmd, ))
    proc = subprocess.Popen(cmd,
                            cwd=libssh2_directory,
                            stdout=subprocess.PIPE)
    for line in proc.stdout:
        print line.rstrip("\n")
    proc.wait()

    output_file = os.path.join(libssh2_directory, "win32", "Release_lib", "libssh2.lib")
    if not os.path.isfile(output_file):
        logger.error("Cannot file output file: %s" % (output_file, ))
        return
    destination = os.path.join(deps_directory, "libssh2.lib")
    shutil.copy(output_file, destination)

def main():
    logger = logging.getLogger("%s.main" % (APP_NAME, ))
    logger.debug("entry.")

    # ----------------------------------------------------------------------
    #   Path determination and validation.
    # ----------------------------------------------------------------------
    current_path = os.path.abspath(__file__)
    assert(os.path.isfile(current_path))
    current_directory = os.path.abspath(os.path.join(current_path, os.pardir))
    assert(os.path.isdir(current_directory))
    root_directory = os.path.abspath(os.path.join(current_directory, os.pardir, os.pardir))
    assert(os.path.isdir(root_directory))

    lib_directory = os.path.abspath(os.path.join(root_directory, "lib"))
    assert(os.path.isdir(lib_directory))
    deps_directory = os.path.abspath(os.path.join(root_directory, "dep"))
    if not os.path.isdir(deps_directory):
        os.mkdir(deps_directory)

    zlib_directory = glob(os.path.join(lib_directory, "zlib*"))
    assert(len(zlib_directory) == 1)
    zlib_directory = os.path.abspath(zlib_directory[0])
    assert(os.path.isdir(zlib_directory))

    openssl_directory = glob(os.path.join(lib_directory, "openssl*"))
    assert(len(openssl_directory) == 1)
    openssl_directory = os.path.abspath(openssl_directory[0])
    assert(os.path.isdir(openssl_directory))

    libssh2_directory = glob(os.path.join(lib_directory, "libssh2*"))
    assert(len(libssh2_directory) == 1)
    libssh2_directory = os.path.abspath(libssh2_directory[0])
    assert(os.path.isdir(libssh2_directory))
    # ----------------------------------------------------------------------

    build_zlib(zlib_directory, deps_directory)
    build_openssl(openssl_directory, deps_directory)
    build_libssh2(libssh2_directory, deps_directory)

if __name__ == "__main__":
    main()
