#include "ssh_utils.hpp"

namespace ssh_utils
{
    using namespace boost::algorithm;

    inline int minimum(int a, int b)
    {
            return (a < b) ? a : b;
    }

    static void sleep(int milliseconds)
    {
        boost::this_thread::sleep(boost::posix_time::milliseconds(milliseconds)); 
    }

    int send_string_to_channel(LIBSSH2_CHANNEL *channel, const std::string& contents)
    {
        int rc = libssh2_channel_write(channel, contents.c_str(), contents.length());
        return rc;
    }

    int send_line_break_to_channel(LIBSSH2_CHANNEL *channel)
    {
        int rc = send_string_to_channel(channel, line_break);
        return rc;
    }

    int send_command_to_channel(LIBSSH2_CHANNEL *channel, const std::string &command)
    {
		int rc = send_string_to_channel(channel, command);
        return rc;
    }

    int sync_original_prompt(int sock,
                             LIBSSH2_SESSION *session,
                             LIBSSH2_CHANNEL *channel,
                             int base_delay,
							 char *read_buffer,
							 int read_buffer_size)
    {
        int rc = 0;        
        const int small_delay = base_delay;
        const int medium_delay = 5 * small_delay;
        //const int large_delay = 10 * small_delay;        

        std::string a, b;

        // Clear out the cache before getting the prompt;        
        read_from_channel(sock,
                          session,
                          channel,
                          MICROSECONDS_IN_ONE_SECOND / 10,
                          false,
                          NULL,
						  read_buffer,
						  read_buffer_size,
                          false,
                          false,
                          std::string());
        
        sleep(small_delay);
        send_line_break_to_channel(channel);        
        sleep(medium_delay);
        a = read_from_channel(sock,
                              session,
                              channel,
                              MICROSECONDS_IN_ONE_SECOND / 10,
                              false,
                              NULL,
							  read_buffer,
							  read_buffer_size,
                              true,
                              false,
                              std::string());
        trim(a);
        sleep(small_delay);
        send_line_break_to_channel(channel);
        sleep(medium_delay);
        b = read_from_channel(sock,
                              session,
                              channel,
                              MICROSECONDS_IN_ONE_SECOND / 10,
                              false,
                              NULL,
							  read_buffer,
							  read_buffer_size,
                              true,
                              false,
                              std::string());
        trim(b);
        int ld = levenstein_distance(a, b);
        int len_a = a.length();
        int len_b = b.length();
        //std::cout << "a: " << a << std::endl;
        //std::cout << "b: " << b << std::endl;
        //std::cout << "ld: " << ld << ", len_a: " << len_a << std::endl;
        if ((len_a == 0) || (len_b == 0))
        {
            rc = 1;
        }        
        else if (float(ld) / len_a > 0.4)
        {
            rc = 1;
        }
        //std::cout << "lev rc: " << rc << std::endl;
        return rc;
    }

    int reset_prompt_to_pexpect_version(int sock,
                                        LIBSSH2_SESSION *session,
                                        LIBSSH2_CHANNEL *channel,
                                        int estimated_delay,
										char *read_buffer,
										int read_buffer_size)
    {        
        // -------------------------------------------------------------------
        //  !!AI TADA, it's magic baby! :(. We need to establish the RTT
        //  of the link, where RTT includes both network and processing
        //  delay, and then munge it into an estimate of how long to
        //  wait for resetting the bash prompt will take.
        //
        //  Is there a non-empirical way of doing this? We'll see. For now
        //  make it chunky, and sit on it.
        // -------------------------------------------------------------------
        const int timeout_usecs = estimated_delay * 50000;  
        // -------------------------------------------------------------------

        send_command_to_channel(channel, unset_prompt);
		send_line_break_to_channel(channel);
        send_command_to_channel(channel, unique_prompt);        
		send_line_break_to_channel(channel);
        read_from_channel(sock,
                          session,
                          channel,
                          timeout_usecs,
                          false,
                          NULL,
						  read_buffer,
						  read_buffer_size,
                          false,
                          false,
                          std::string());
        return true;
    }

    int read_once_from_channel(int sock,
                               LIBSSH2_SESSION *session,
                               LIBSSH2_CHANNEL *channel,
                               char *read_buffer,
                               int read_buffer_size,
                               std::stringstream &output)
    {   
        int rc = libssh2_channel_read(channel, read_buffer, read_buffer_size - 1);
        if (rc > 0)
        {            
            int last_byte = (rc > (read_buffer_size - 1)) ? (read_buffer_size - 1) : rc;
            read_buffer[last_byte] = '\0';
            output << read_buffer;                
        }
        return rc;
    }

    std::string read_from_channel(int sock,
                                  LIBSSH2_SESSION *session,
                                  LIBSSH2_CHANNEL *channel,
                                  int timeout_usecs,
                                  bool is_executing_command,
                                  std::string *command,
								  char *read_buffer,
								  int read_buffer_size,
                                  bool capture_output,
                                  bool is_zeromq_bind_present,
                                  const std::string& zeromq_bind)
    {   
        log4cxx::LoggerPtr logger = log4cxx::Logger::getLogger("ssh_utils::read_from_channel");
        LOG4CXX_DEBUG(logger, "entry. { timeout_usecs=" << timeout_usecs <<
                                     ", is_executing_command=" << is_executing_command <<
                                     ", capture_output=" << capture_output <<
                                     ", is_zeromq_bind_present=" << is_zeromq_bind_present <<
                                     "}");

		// -------------------------------------------------------------------
		//	Validate inputs.
		// -------------------------------------------------------------------
		assert(session != NULL);
		assert(channel != NULL);
		assert(read_buffer != NULL);        
		// -------------------------------------------------------------------        

        // -------------------------------------------------------------------
        //  Initialize local variables.
        // -------------------------------------------------------------------
        std::stringstream output_all;
		std::stringstream output_incremental;
        std::stringstream output_last_line;
        std::string output_incremental_string;
        std::string output_last_line_string;

        long long time_elapsed;        
        int read_rc;
        const long long wait_duration = MICROSECONDS_IN_ONE_HUNDRETH_SECOND;

		bool parse_rc;			
        std::string result;        
		boost::regex prompt_regexp_object;		
		bool is_first_read = true;
		bool have_found_prompt = false;

        zmq::context_t context(1);
        zmq::socket_t publisher(context, ZMQ_PUB);        
        Json::Value json_root;
        Json::FastWriter json_writer;
        std::string json_string;
        // -------------------------------------------------------------------

        // -------------------------------------------------------------------
        //  Validate inputs.
        // -------------------------------------------------------------------
		assert((!is_executing_command) ||
			   ((is_executing_command) && (command != NULL)));
        // -------------------------------------------------------------------

        // -------------------------------------------------------------------
        //  Set up the ZeroMQ PUBLISH bind, if requested.
        // -------------------------------------------------------------------
        if (is_zeromq_bind_present)
        {
            LOG4CXX_DEBUG(logger, "Binding publisher to: " << zeromq_bind.c_str());
            publisher.bind(zeromq_bind.c_str());
        }
        // -------------------------------------------------------------------
		
		if (is_executing_command)
		{
            LOG4CXX_DEBUG(logger, "Is executing command: " << (*command));
			parsing::build_prompt_ssh_expect_regular_expression(prompt_regexp,
																prompt_regexp_object);			
		}		
        for (time_elapsed = 0;
             ;
             time_elapsed += wait_duration)
        {

			// ------------------------------------------------------------------------
			//	Only apply timeout constraints if we've requested a timeout.
			// ------------------------------------------------------------------------
			if ((timeout_usecs > 0) && (time_elapsed >= (long long)timeout_usecs))
			{
				break;
			}
			// ------------------------------------------------------------------------

            do
            {       
                read_rc = read_once_from_channel(sock,
                                                 session,
                                                 channel,
                                                 read_buffer,
                                                 read_buffer_size,
                                                 output_incremental);
            }
            while(read_rc > 0);
            output_incremental_string = output_incremental.str();
			if ((is_executing_command) &&
				(is_first_read) &&
				(output_incremental_string.length() > 0))
			{
                LOG4CXX_DEBUG(logger, "Left trip output for first and only time.");
				trim_left(output_incremental_string);
				is_first_read = false;
			} // if (is_first_read)

            output_last_line_string = output_incremental_string;
            output_last_line.str(output_last_line_string);

			if (is_executing_command)
			{
				// -----------------------------------------------------------
				//	If we haven't found the prompt yet look for it as well. If
				//	we find it and we're executing a command this tells us
				//	that the command is finished.
				// -----------------------------------------------------------
				if (!have_found_prompt)
				{
					parse_rc = parsing::parse_ssh_command_output(output_incremental_string,
																 prompt_regexp_object,
																 result);
					if (parse_rc == true)
					{						
                        if (is_executing_command)
                        {
                            std::cout << result;
                        }
						output_all << result;
						return output_all.str();
					} // if (parse_rc == true)
				} // if (!have_found_prompt)
				// -----------------------------------------------------------
			} // if (is_executing_command)
			
            // ---------------------------------------------------------------
            //  If there is any output currently available, then 
            //  there are three branches here:
            //
            //  1) Are we capturing the output into a single, massive stream
            //  so that we can return it at the end? If so, then put
            //  the current increment of output into output_all.
            //
            //  2) Are we executing a command, and are we only outputting it
            //  to console? If so then do so.
            //
            //  3) Are we executing a command, and are we only outputting it
            //  to a ZeroMQ binding? If so then do so.
            // ---------------------------------------------------------------
            if (output_incremental_string.length() > 0)
            {
                if (capture_output)
                {
                    // Capturing the output.
                    output_all << output_incremental_string;
                }			
			    if ((is_executing_command) && (!is_zeromq_bind_present))
                {
                    // Only output to console.
                    std::cout << output_incremental_string; 
                }
                else if (is_executing_command)
			    {
                    // Only output to ZeroMQ binding.                
                    json_root.clear();
                    json_root["contents"] = output_incremental_string;
                    json_string = json_writer.write(json_root);
                    trim(json_string);
                    LOG4CXX_DEBUG(logger, "Sending JSON via ZeroMQ: " << json_string);
                    int json_size = json_string.length();
                    zmq::message_t zmq_message(json_size);
                    memcpy(zmq_message.data(),
                           json_string.c_str(),
                           json_size);
                    publisher.send(zmq_message);
			    }			
            } // if (output_incremental_string.length() > 0)
            // ---------------------------------------------------------------

			output_incremental.str(std::string());			
            output_last_line.str(std::string());

            /* this is due to blocking that would occur otherwise so we loop on
               this condition */ 
            if(read_rc == LIBSSH2_ERROR_EAGAIN)
            {            
                //LOG4CXX_DEBUG(logger, "Loop, wait for more.");
                waitsocket(sock, session, wait_duration);
            }
            else
            {
                LOG4CXX_ERROR(logger, "Error code '" << read_rc << "' on read, so bail out.");
                break;
            }
        } // outer for loop based on time and size

        std::string return_value = output_all.str();
        LOG4CXX_DEBUG(logger, "returning: \n'" << return_value << "'");
        return return_value;
    }

    std::string get_result_from_command_execution(int sock,
                                                  LIBSSH2_SESSION *session,
                                                  LIBSSH2_CHANNEL *channel,                                                  
                                                  std::string& command,
                                                  int timeout_seconds,
												  char *read_buffer,
												  int read_buffer_size,
                                                  bool is_zeromq_bind_present,
                                                  const std::string& zeromq_bind)
    {
		const bool is_executing_command = true;        
        int rc;

        rc = send_command_to_channel(channel, command);
        read_from_channel(sock,
                          session,
                          channel,
                          MICROSECONDS_IN_ONE_SECOND / 2,
                          false,
                          NULL,
						  read_buffer,
						  read_buffer_size,
                          false,
                          false,
                          std::string());

		send_line_break_to_channel(channel);
        std::string output = read_from_channel(sock,
                                               session,
                                               channel,
                                               timeout_seconds * MICROSECONDS_IN_ONE_SECOND,
                                               is_executing_command,
                                               (&command),
											   read_buffer,
											   read_buffer_size,
                                               true,                                               
                                               is_zeromq_bind_present,
                                               zeromq_bind);
        trim(output);
        return output;
    }

    void command_execution_without_result(int sock,
                                          LIBSSH2_SESSION *session,
                                          LIBSSH2_CHANNEL *channel,                                                  
                                          std::string& command,
                                          int timeout_seconds,
										  char *read_buffer,
										  int read_buffer_size,
                                          bool is_zeromq_bind_present,
                                          const std::string& zeromq_bind)
    {
		const bool is_executing_command = true;        
        int rc;

        rc = send_command_to_channel(channel, command);
        read_from_channel(sock,
                          session,
                          channel,
                          MICROSECONDS_IN_ONE_SECOND / 2,
                          false,
                          NULL,
						  read_buffer,
						  read_buffer_size,
                          false,
                          false,
                          std::string());

		send_line_break_to_channel(channel);
        read_from_channel(sock,
                          session,
                          channel,
                          timeout_seconds * MICROSECONDS_IN_ONE_SECOND,
                          is_executing_command,
                          (&command),
						  read_buffer,
						  read_buffer_size,
                          false,
                          is_zeromq_bind_present,
                          zeromq_bind);
    }

    int waitsocket(int socket_fd, LIBSSH2_SESSION *session, int timeout_usec)
    {
        struct timeval timeout_struct;
        int rc;
        fd_set fd;
        fd_set *writefd = NULL;
        fd_set *readfd = NULL;
        int dir;
     
        timeout_struct.tv_sec = 0;
        timeout_struct.tv_usec = timeout_usec;
     
        FD_ZERO(&fd);
     
        FD_SET(socket_fd, &fd);
     
        /* now make sure we wait in the correct direction */ 
        dir = libssh2_session_block_directions(session);
     
        if(dir & LIBSSH2_SESSION_BLOCK_INBOUND)
            readfd = &fd;
     
        if(dir & LIBSSH2_SESSION_BLOCK_OUTBOUND)
            writefd = &fd;
     
        rc = select(socket_fd + 1, readfd, writefd, NULL, &timeout_struct);
     
        return rc;
    }

    int levenstein_distance(const std::string& source, const std::string& target)
    {

      // Step 1

      const int n = source.length();
      const int m = target.length();
      if (n == 0) {
        return m;
      }
      if (m == 0) {
        return n;
      }

      // Good form to declare a TYPEDEF

      typedef std::vector< std::vector<int> > Tmatrix; 

      Tmatrix matrix(n+1);

      // Size the vectors in the 2.nd dimension. Unfortunately C++ doesn't
      // allow for allocation on declaration of 2.nd dimension of vec of vec

      for (int i = 0; i <= n; i++) {
        matrix[i].resize(m+1);
      }

      // Step 2

      for (int i = 0; i <= n; i++) {
        matrix[i][0]=i;
      }

      for (int j = 0; j <= m; j++) {
        matrix[0][j]=j;
      }

      // Step 3

      for (int i = 1; i <= n; i++) {

        const char s_i = source[i-1];

        // Step 4

        for (int j = 1; j <= m; j++) {

          const char t_j = target[j-1];

          // Step 5

          int cost;
          if (s_i == t_j) {
            cost = 0;
          }
          else {
            cost = 1;
          }

          // Step 6

          const int above = matrix[i-1][j];
          const int left = matrix[i][j-1];
          const int diag = matrix[i-1][j-1];
          int cell = ssh_utils::minimum(above + 1, ssh_utils::minimum(left + 1, diag + cost));

          // Step 6A: Cover transposition, in addition to deletion,
          // insertion and substitution. This step is taken from:
          // Berghel, Hal ; Roach, David : "An Extension of Ukkonen's 
          // Enhanced Dynamic Programming ASM Algorithm"
          // (http://www.acm.org/~hlb/publications/asm/asm.html)

          if (i>2 && j>2) {
            int trans=matrix[i-2][j-2]+1;
            if (source[i-2]!=t_j) trans++;
            if (s_i!=target[j-2]) trans++;
            if (cell>trans) cell=trans;
          }

          matrix[i][j]=cell;
        }
      }

      // Step 7

      return matrix[n][m];
    }
}



