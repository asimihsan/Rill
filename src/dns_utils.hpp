#ifndef DNS_UTILS_HPP_
#define DNS_UTILS_HPP_

#include <string>
#include <iostream>
#include <boost/asio.hpp>

namespace dns_utils
{    
    bool resolve_hostname_to_ipv4(const std::string &hostname,
                                  std::vector< std::string >&output_ipv4_addresses);
    bool is_string_an_ipv4_address(const std::string &input);
}

#endif
