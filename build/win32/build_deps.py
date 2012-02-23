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

def build_yaml(yaml_directory, deps_directory):
    logger = logging.getLogger("%s.build_yaml" % (APP_NAME, ))
    logger.debug("entry. yaml_directory: %s, deps_directory: %s" % (yaml_directory, deps_directory))

    sln_filepath = os.path.join(yaml_directory, "win32", "vs2008", "libyaml.sln")
    if not os.path.isfile(sln_filepath):
        logger.error("MSVC solution file %s does not exist." % (sln_filepath, ))
        return
    cmd = r"msbuild.exe %s /target:yaml /p:Configuration=Release" % (sln_filepath, )
    logger.debug("executing: %s" % (cmd, ))
    proc = subprocess.Popen(cmd,
                            cwd=yaml_directory,
                            stdout=subprocess.PIPE)
    for line in proc.stdout:
        print line.rstrip("\n")
    proc.wait()

    output_file = os.path.join(yaml_directory,
                               "win32",
                               "vs2008",
                               "Output",
                               "Release",
                               "lib",
                               "yaml.lib")
    if not os.path.isfile(output_file):
        logger.error("Cannot file output file: %s" % (output_file, ))
        return
    destination = os.path.join(deps_directory, "yaml.lib")
    shutil.copy(output_file, destination)

def build_libpgm(libpgm_directory, deps_directory):
    logger = logging.getLogger("%s.build_libpgm" % (APP_NAME, ))
    logger.debug("entry. libpgm_directory: %s, deps_directory: %s" % (libpgm_directory, deps_directory))

    sln_filepath = os.path.join(libpgm_directory, "openpgm", "pgm", "build", "OpenPGM.sln")
    if not os.path.isfile(sln_filepath):
        logger.error("MSVC solution file %s does not exist." % (sln_filepath, ))
        return
    cmd = r"msbuild.exe %s /target:libpgm /p:Configuration=Release" % (sln_filepath, )
    logger.debug("executing: %s" % (cmd, ))
    proc = subprocess.Popen(cmd,
                            cwd=libpgm_directory,
                            stdout=subprocess.PIPE)
    for line in proc.stdout:
        print line.rstrip("\n")
    proc.wait()
    output_file = os.path.join(libpgm_directory,
                               "openpgm",
                               "pgm",
                               "build",
                               "lib",
                               "Release",
                               "libpgm.lib")
    if not os.path.isfile(output_file):
        logger.error("Cannot file output file: %s" % (output_file, ))
        return
    destination = os.path.join(deps_directory, "libpgm.lib")
    shutil.copy(output_file, destination)

def build_zeromq(zeromq_directory, deps_directory):
    logger = logging.getLogger("%s.build_zeromq" % (APP_NAME, ))
    logger.debug("entry. zeromq_directory: %s, deps_directory: %s" % (zeromq_directory, deps_directory))

    sln_filepath = os.path.join(zeromq_directory, "builds", "msvc", "msvc.sln")
    if not os.path.isfile(sln_filepath):
        logger.error("MSVC solution file %s does not exist." % (sln_filepath, ))
        return
    cmd = r"msbuild.exe %s /target:libzmq /p:Configuration=Release" % (sln_filepath, )
    logger.debug("executing: %s" % (cmd, ))
    proc = subprocess.Popen(cmd,
                            cwd=zeromq_directory,
                            stdout=subprocess.PIPE)
    for line in proc.stdout:
        print line.rstrip("\n")
    proc.wait()

    output_file = os.path.join(zeromq_directory,
                               "builds",
                               "msvc",
                               "Release",
                               "libzmq.lib")
    if not os.path.isfile(output_file):
        logger.error("Cannot file output file: %s" % (output_file, ))
        return
    destination = os.path.join(deps_directory, "libzmq.lib")
    shutil.copy(output_file, destination)

def build_re2(re2_directory, deps_directory):
    logger = logging.getLogger("%s.build_re2" % (APP_NAME, ))
    logger.debug("entry. re2_directory: %s, deps_directory: %s" % (re2_directory, deps_directory))

    sln_filepath = os.path.join(re2_directory, "re2.sln")
    if not os.path.isfile(sln_filepath):
        logger.error("MSVC solution file %s does not exist." % (sln_filepath, ))
        return
    cmd = r"msbuild.exe %s /target:re2 /p:Configuration=Release" % (sln_filepath, )
    logger.debug("executing: %s" % (cmd, ))
    proc = subprocess.Popen(cmd,
                            cwd=re2_directory,
                            stdout=subprocess.PIPE)
    for line in proc.stdout:
        print line.rstrip("\n")
    proc.wait()

    output_file = os.path.join(re2_directory,
                               "Release",
                               "libzmq.lib")
    if not os.path.isfile(output_file):
        logger.error("Cannot file output file: %s" % (output_file, ))
        return
    destination = os.path.join(deps_directory, "re2.lib")
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

    yaml_directory = glob(os.path.join(lib_directory, "yaml*"))
    assert(len(yaml_directory) == 1)
    yaml_directory = os.path.abspath(yaml_directory[0])
    assert(os.path.isdir(yaml_directory))

    zeromq_directory = glob(os.path.join(lib_directory, "zeromq*"))
    assert(len(zeromq_directory) == 1)
    zeromq_directory = os.path.abspath(zeromq_directory[0])
    assert(os.path.isdir(zeromq_directory))

    #re2_directory = glob(os.path.join(lib_directory, "re2*"))
    #assert(len(re2_directory) == 1)
    #re2_directory = os.path.abspath(re2_directory[0])
    #assert(os.path.isdir(re2_directory))
    # ----------------------------------------------------------------------

    #build_zlib(zlib_directory, deps_directory)
    #build_openssl(openssl_directory, deps_directory)
    build_libssh2(libssh2_directory, deps_directory)
    build_yaml(yaml_directory, deps_directory)
    build_zeromq(zeromq_directory, deps_directory)
    #build_re2(re2_directory, deps_directory)

if __name__ == "__main__":
    main()
