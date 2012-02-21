#include "ssh_utils.hpp"

namespace ssh_utils
{
    using namespace boost::algorithm;

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
        std::stringstream command_to_send;
        command_to_send << command << line_break;        
        int rc = send_string_to_channel(channel, command_to_send.str());
        return rc;
    }

    int sync_original_prompt(int sock,
                             LIBSSH2_SESSION *session,
                             LIBSSH2_CHANNEL *channel,
                             int base_delay)
    {
        int rc = 0;        
        const int small_delay = base_delay;
        const int medium_delay = 5 * small_delay;
        const int large_delay = 10 * small_delay;
        const int size = 10000;

        std::string a, b;

        // Clear out the cache before getting the prompt;
        read_from_channel(sock,
                          session,
                          channel,
                          size,
                          1,
                          false,
                          NULL);
        
        sleep(small_delay);
        send_line_break_to_channel(channel);        
        sleep(medium_delay);
        a = read_from_channel(sock,
                              session,
                              channel,
                              size,
                              1,
                              false,
                              NULL);
        trim(a);
        sleep(small_delay);
        send_line_break_to_channel(channel);
        sleep(medium_delay);
        b = read_from_channel(sock,
                              session,
                              channel,
                              size,
                              1,
                              false,
                              NULL);
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
                                        LIBSSH2_CHANNEL *channel)
    {
        send_command_to_channel(channel, unset_prompt);
        send_command_to_channel(channel, unique_prompt);
        std::string output = read_from_channel(sock,
                                               session,
                                               channel,
                                               -1,
                                               5,
                                               false,
                                               NULL);        
        return true;
    }

    int read_once_from_channel(int sock,
                               LIBSSH2_SESSION *session,
                               LIBSSH2_CHANNEL *channel,
                               char *buffer,
                               int buffer_size,
                               std::stringstream &output)
    {   
        int rc = libssh2_channel_read(channel, buffer, buffer_size);
        if (rc > 0)
        {            
            int last_byte = (rc > (buffer_size - 1)) ? (buffer_size - 1) : rc;
            buffer[last_byte] = '\0';
            output << buffer;                
        }
        return rc;
    }

    std::string read_from_channel(int sock,
                                  LIBSSH2_SESSION *session,
                                  LIBSSH2_CHANNEL *channel,
                                  int size,
                                  int timeout_seconds,
                                  bool is_executing_command,
                                  std::string *command)
    {       
        // -------------------------------------------------------------------
        //  Initialize local variables.
        // -------------------------------------------------------------------
        if (size <= 0)
        {
            size = 0x4000;
        }
        std::stringstream output;
        int time_elapsed;
        int byte_count;
        int read_rc;
        bool parse_rc;
        std::string result;
        boost::regex regexp_object;
        int timeout_microseconds = timeout_seconds * MICROSECONDS_IN_ONE_SECOND;
        const int wait_duration = MICROSECONDS_IN_ONE_HUNDRETH_SECOND;
        // -------------------------------------------------------------------

        // -------------------------------------------------------------------
        //  Validate inputs.
        // -------------------------------------------------------------------
        assert((!is_executing_command) ||
               (is_executing_command && (command != NULL)));
        // -------------------------------------------------------------------

        if (is_executing_command)
        {
            bool rc = parsing::build_ssh_expect_regular_expression((*command),
                                                                   prompt_regexp,
                                                                   regexp_object);
        }

        char *buffer = (char *)malloc(size);
        for (time_elapsed = 0, byte_count = 0;
             (time_elapsed < timeout_microseconds) && (byte_count < size);
             time_elapsed += wait_duration)
        {
            do
            {       
                read_rc = read_once_from_channel(sock,
                                                 session,
                                                 channel,
                                                 buffer,
                                                 size,
                                                 output);
            }
            while(read_rc > 0);            
            if (is_executing_command)
            {
                parse_rc = parsing::parse_ssh_command_output(output.str(),
                                                             regexp_object,
                                                             result);                
                if (parse_rc == true)
                {
                    free(buffer);
                    return result;
                } // if (rc == true)
            }

            /* this is due to blocking that would occur otherwise so we loop on
               this condition */ 
            if(read_rc == LIBSSH2_ERROR_EAGAIN)
            {            
                waitsocket(sock, session, wait_duration);
            }
            else
            {
                break;
            }
        } // outer for loop based on time and size
        free(buffer);    
        return output.str();
    }

    std::string get_result_from_command_execution(int sock,
                                                  LIBSSH2_SESSION *session,
                                                  LIBSSH2_CHANNEL *channel,                                                  
                                                  std::string& command,
                                                  int timeout_seconds)
    {
        int rc;
        bool is_executing_command = (timeout_seconds <= 0) ? false : true;
        int size = 0;
        rc = send_command_to_channel(channel, command);
        std::string output = read_from_channel(sock,
                                               session,
                                               channel,
                                               size,
                                               timeout_seconds,
                                               is_executing_command,
                                               (&command));
        trim(output);
        return output;
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
          int cell = min( above + 1, min(left + 1, diag + cost));

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



