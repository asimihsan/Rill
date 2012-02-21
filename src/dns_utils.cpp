#include "dns_utils.hpp"

namespace dns_utils
{    
    using boost::asio::ip::tcp;

    bool is_string_an_ipv4_address(const std::string &input)
    {
        boost::system::error_code ec;
        boost::asio::ip::address::from_string(input, ec);
        if (ec)
        {
            return false;
        }
        else
        {
            return true;
        }
    }

    bool resolve_hostname_to_ipv4(const std::string &hostname,
                                  std::vector< std::string >&output_ipv4_addresses)
    {        
        // -------------------------------------------------------------------
        //  Initialize local variables.
        // -------------------------------------------------------------------
        boost::asio::io_service io_service;
        // -------------------------------------------------------------------

        // -------------------------------------------------------------------
        //  Validate inputs.
        // -------------------------------------------------------------------

        // -------------------------------------------------------------------

        // -------------------------------------------------------------------
        //  Initialize output variables.
        // -------------------------------------------------------------------
        output_ipv4_addresses.clear();
        // -------------------------------------------------------------------
        
        tcp::resolver resolver(io_service);
        tcp::resolver::query query(hostname.c_str(), "");        
        boost::system::error_code ec;
        tcp::resolver::iterator destination = resolver.resolve(query, ec);        
        if (ec)
        {
            return false;
        }
        tcp::resolver::iterator end;        
        tcp::endpoint endpoint;        

        while (destination != end)
        {
            endpoint = *destination++;
            std::string ip_address = endpoint.address().to_string();
            output_ipv4_addresses.push_back(ip_address);
        }

        return true;
    } // std::string resolve_hostname_to_ipv4(const std::string &hostname)
}