#include "parsing.hpp"

namespace parsing
{
	std::string regex_escape(const std::string& string_to_escape)
	{
		static const boost::regex re_boostRegexEscape("[\\{\\}\\^\\.\\$\\|\\(\\)\\[\\]\\*\\+\\?\\/\\\\]");
		const std::string rep("\\\\\\1&");
		std::string result = regex_replace(string_to_escape,
										   re_boostRegexEscape,
										   rep,
										   boost::match_default | boost::format_sed);
		return result;
	}

    bool build_command_ssh_expect_regular_expression(const std::string& command,
                                                     boost::regex& regexp_object)
    {
		//std::cout << "build_command_ssh_expect_regular_expression entry." << std::endl;
		//std::cout << "command: " << command << std::endl;
        std::stringstream regexp_ss;

        regexp_ss << "^[[:space:]]*";
        regexp_ss << command;
        regexp_ss << "[[:space:]]*";
        regexp_ss << "(.*)";
        //std::cout << "regexp string: " << regexp_ss.str() << std::endl;
        boost::regex local_regexp_object(regexp_ss.str());
		//std::cout << "built local_regexp_object";
        regexp_object = local_regexp_object;        

		//std::cout << "build_command_ssh_expect_regular_expression exit." << std::endl;
        return true;
    }

    bool build_prompt_ssh_expect_regular_expression(const std::string& prompt,
                                                    boost::regex& regexp_object)
    {
        std::stringstream regexp_ss;

        regexp_ss << "^(.*)";
        regexp_ss << "[[:space:]]*";
        regexp_ss << prompt;
        regexp_ss << "[[:space:]]*$";   
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
			//std::cout << "input: " << std::endl;
			//std::cout << input << std::endl;
            //std::cout << "match found" << std::endl;            
			//std::cout << "number of matches: " << match.size() << std::endl;
			//std::cout << "match[1]: " << std::endl;
            //std::cout << match[1] << std::endl;
            contents = match[1];
            rc = true;
			//std::cout << "contents is: " << contents << std::endl;
        }
        else
        {
            //std::cout << "no match found" << std::endl;
            rc = false;
        }        		
        return rc;
    }        
}
