#ifndef SSH_UTILS_HPP_
#define SSH_UTILS_HPP_

#ifdef WIN32
#define LIBSSH2_API __declspec(dllexport)
#endif
#include <libssh2_config.h>
#include <libssh2.h>
#include <libssh2_sftp.h>

#include <string>
#include <sstream>
#include <iostream>
#include <boost/thread/thread.hpp>
#include <cassert>

#include <boost/algorithm/string.hpp>

#include "parsing.hpp"

namespace ssh_utils
{
    static std::string line_break = std::string("\n");

    static std::string unset_prompt = std::string("unset PROMPT_COMMAND");
    static std::string unique_prompt = std::string("PS1='[PEXPECT]$ '");
    static std::string prompt_regexp = std::string("\\[PEXPECT\\]\\$");

    int send_string_to_channel(LIBSSH2_CHANNEL *channel, const std::string& command);
    int send_line_break_to_channel(LIBSSH2_CHANNEL *channel);
    int send_command_to_channel(LIBSSH2_CHANNEL *channel, const std::string &contents);
    int sync_original_prompt(int sock,
                             LIBSSH2_SESSION *session,
                             LIBSSH2_CHANNEL *channel,
                             int base_delay);
    int reset_prompt_to_pexpect_version(int sock,
                                        LIBSSH2_SESSION *session,
                                        LIBSSH2_CHANNEL *channel);
    std::string read_from_channel(int sock,
                                  LIBSSH2_SESSION *session,
                                  LIBSSH2_CHANNEL *channel,
                                  int size,
                                  int timeout,
                                  bool is_executing_command,
                                  std::string *command);
    int read_once_from_channel(int sock,
                               LIBSSH2_SESSION *session,
                               LIBSSH2_CHANNEL *channel,
                               char *buffer,
                               int buffer_size,
                               std::stringstream &output);
    std::string get_result_from_command_execution(int sock,
                                                  LIBSSH2_SESSION *session,
                                                  LIBSSH2_CHANNEL *channel,                                                  
                                                  std::string& command,
                                                  int timeout_seconds);
    int levenstein_distance(const std::string& source, const std::string& target);
    int waitsocket(int socket_fd, LIBSSH2_SESSION *session);
}

#endif
