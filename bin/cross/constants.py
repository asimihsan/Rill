#!/usr/bin/env python2.7

import os
import sys
import platform
from string import Template

current_path = os.path.abspath(__file__)
assert(os.path.isfile(current_path)), "%s not good current_path" % (current_path, )
current_directory = os.path.split(current_path)[0]
assert(os.path.isdir(current_directory)), "%s not good current_directory" % (current_directory, )

root_rill_directory = os.path.abspath(os.path.join(current_directory, os.pardir, os.pardir))
assert(os.path.isdir(root_rill_directory)), "%s not goot root_rill_directory" % (root_rill_directory, )

assert(platform.system() in ["Linux", "Windows"]), "Only support Linux and Windows"
if platform.system() == "Linux":
    python_executable = r"/usr/local/bin/python2.7"
else:
    python_executable = "python.exe"

# platform-specific bin directories
if platform.system() == "Linux":
    bin_directory = os.path.join(root_rill_directory, "bin", "linux")
    assert(os.path.isdir(bin_directory)), "%s not good Linux bin_directory" % (bin_directory, )
    bin_extension = ""
else:
    bin_directory = os.path.join(root_rill_directory, "bin", "win32")
    assert(os.path.isdir(bin_directory)), "%s not good Windows bin_directory" % (bin_directory, )
    bin_extension = ".exe"
cross_bin_directory = os.path.join(root_rill_directory, "bin", "cross")
assert(os.path.isdir(cross_bin_directory)), "%s not good cross_bin_directory" % (cross_bin_directory, )

masspinger_filepath = os.path.join(bin_directory, "masspinger" + bin_extension)
assert(os.path.isfile(masspinger_filepath)), "%s not good masspinger_filepath" % (masspinger_filepath, )
masspinger_template = Template(""" "${executable}" --zeromq_bind "${masspinger_zeromq_bind}" ${hosts} """)

config_directory = os.path.join(cross_bin_directory, "config")
assert(os.path.isdir(config_directory)), "%s not good config_directory" % (config_directory, )

robust_ssh_tap_filepath = os.path.join(cross_bin_directory, "robust_ssh_tap.py")
assert(os.path.isfile(robust_ssh_tap_filepath)), "%s not good robust_ssh_tap_filepath" % (robust_ssh_tap_filepath, )
robust_ssh_tap_template = Template(""" ${executable} --masspinger "${masspinger_zeromq_bind}" --ssh_tap "${ssh_tap_zeromq_bind}" --parser "${parser_zeromq_bind}" --parser_name "${parser_name}" --results "${results_zeromq_bind}" --host "${host}" --command "${command}" --username "${username}" --password "${password}" """)

reconcile_log_filepath = os.path.join(cross_bin_directory, "reconcile_log.py")
assert(os.path.isfile(reconcile_log_filepath)), "%s not good reconcile_log_filepath" % (reconcile_log_filepath, )
reconcile_log_template = Template(""" nice -n 19 ${executable} --masspinger "${masspinger_zeromq_bind}" --ssh_tap "${ssh_tap_zeromq_bind}" --parser "${parser_zeromq_bind}" --parser_name "${parser_name}" --host "${host}" --command "${command}" --username "${username}" --password "${password}" --collection_name "${collection_name}" """)

masspinger_tap_filepath = os.path.join(cross_bin_directory, "masspinger_tap.py")
assert(os.path.isfile(masspinger_tap_filepath)), "%s not good masspinger_tap_filepath" % (masspinger_tap_filepath, )
masspinger_tap_template = Template(""" ${executable} --masspinger_zeromq_bind "${masspinger_zeromq_bind}" --database "pings" """)

service_registry_filepath = os.path.join(cross_bin_directory, "service_registry.py")
assert(os.path.isfile(service_registry_filepath)), "%s not good service_registry_filepath" % (service_registry_filepath, )
service_registry_template = Template(""" ${executable} --port ${port} """)

ssh_tap_filepath = os.path.join(bin_directory, "ssh_tap" + bin_extension)
if not (os.path.isfile(ssh_tap_filepath)):
    ssh_tap_filepath = os.path.join(cross_directory, "ssh_tap.py")
assert(os.path.isfile(ssh_tap_filepath)), "%s not good ssh_tap_filepath" % (ssh_tap_filepath, )
ssh_tap_template = Template(""" "${executable}" --host "${host}" --command "${command}" --username "${username}" --password "${password}" --zeromq_bind "${zeromq_bind}" """)

# platform-specific parser templates
if platform.system() == "Windows":
    # Test
    parser_template = Template(""" ${executable} --ssh_tap "${ssh_tap_zeromq_bind}" --results "${parser_zeromq_bind}" --box_name ${box_name} """)
else:
    # Production
    parser_template = Template(""" ${executable} --ssh_tap "${ssh_tap_zeromq_bind}" --results "${parser_zeromq_bind}" --box_name ${box_name} """)

tail_query_inode_template = Template(""" while [[ 1 ]]; do date +"%Y-%m-%dT%H:%M:%S"; ls -i ${log_filepath} 2>&1 | awk '{print \$$1}'; sleep 1; done """)

parser_tap_to_database_filepath = os.path.join(cross_bin_directory, "parser_tap_to_database.py")
assert(os.path.isfile(parser_tap_to_database_filepath)), "%s not good parser_tap_to_database_filepath" % (parser_tap_to_database_filepath, )
parser_tap_to_database_template = Template(""" ${executable} --results "${results_zeromq_bind}" --collection "${collection}" """)

