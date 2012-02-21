#include "parsing.hpp"

namespace parsing
{
    bool build_ssh_expect_regular_expression(const std::string& command,
                                             const std::string& prompt,
                                             boost::regex& regexp_object)
    {
        std::stringstream regexp_ss;

        regexp_ss << "^[[:blank:]]*";
        regexp_ss << command;
        regexp_ss << "(.*)";
        regexp_ss << prompt;
        regexp_ss << "[[:blank:]]*$";   
        //std::cout << "regexp string: " << regexp_ss.str() << std::endl;
        boost::regex local_regexp_object(regexp_ss.str());
        regexp_object = local_regexp_object;        
        return true;
    }

    bool parse_ssh_command_output(const std::string& input,
                                  boost::regex& regexp_object,
                                  std::string &contents)
    {
        // -------------------------------------------------------------------
        //  Initialize local variables.
        // -------------------------------------------------------------------
        
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
        //  Use the regular expression to match the input.
        // -------------------------------------------------------------------
        boost::smatch match;
        //std::cout << "input: " << input << std::endl;
        // -------------------------------------------------------------------

        if (boost::regex_search(input,
                                match,
                                regexp_object,
                                boost::match_extra))
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
             