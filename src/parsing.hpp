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
                                  boost::regex& regexp_object,
                                  std::string &contents);
    bool build_ssh_expect_regular_expression(const std::string& command,
                                             const std::string& prompt,
                                             boost::regex& regexp_object);
}

#endif