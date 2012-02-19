#include "parsing.hpp"

namespace parsing
{
    bool parse_ssh_command_output(const std::string& input,
                                  const std::string& command,
                                  const std::string& prompt,
                                  std::string &contents)
    {
        // -------------------------------------------------------------------
        //  Initialize local variables.
        // -------------------------------------------------------------------
        std::stringstream regexp_ss;
        bool rc;
        // -------------------------------------------------------------------

        // -------------------------------------------------------------------
        //  Validate inputs.
        // -------------------------------------------------------------------
    
        // -------------------------------------------------------------------

        // -------------------------------------------------------------------
        //  Initialize output variables.
        // -------------------------------------------------------------------
        contents.clear();
        // -------------------------------------------------------------------

        // -------------------------------------------------------------------
        //  Create the regular expression then match it on the input.
        // -------------------------------------------------------------------
        regexp_ss << "^[[:blank:]]*";
        regexp_ss << command;
        regexp_ss << "(.*)";
        regexp_ss << prompt;
        regexp_ss << "[[:blank:]]*$";
        boost::regex r(regexp_ss.str());
        boost::smatch match;
        //std::cout << "regexp string: " << regexp_ss.str() << std::endl;
        //std::cout << "input: " << input << std::endl;
        // -------------------------------------------------------------------

        if (boost::regex_search(input, match, r, boost::match_extra))
        {
            //std::cout << "match found" << std::endl;            
            //std::cout << match[1] << std::endl;
            contents = match[1];
            rc = true;
        }
        else
        {
            //std::cout << "no match found" << std::endl;
            rc = false;
        }        
        return rc;
    }        
}
             