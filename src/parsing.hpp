#ifndef PARSING_HPP_
#define PARSING_HPP_

#include <string>
#include <boost/regex.hpp>
#include <istream>
#include <iostream>
#include <ostream>
#include <sstream>

namespace parsing
{
    bool parse_ssh_command_output(const std::string& input,
                                  const std::string& command,
                                  const std::string& prompt,
                                  std::string &contents);
}

#endif