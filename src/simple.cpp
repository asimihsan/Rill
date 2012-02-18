/*
 * Sample showing how to do SSH2 connect.
 *
 * The sample code has default values for host name, user name, password
 * and path to copy, but you can specify them on the command line like:
 *
 * "ssh2 host user password [-p|-i|-k]"
 */

#include <cstdio>
#include <cctype>
#include <cerrno>
#include <istream>
#include <iostream>
#include <ostream>
#include <sstream>
#include <vector>
#include <string>
#include <set>
#include <cstdlib>

#include <boost/asio.hpp>
#include <boost/bind.hpp>
#include <boost/program_options.hpp>
#include <boost/foreach.hpp>
#include <boost/shared_ptr.hpp>
#include <boost/exception/all.hpp> 
namespace po = boost::program_options;
#include <boost/thread/thread.hpp>

#ifdef WIN32
#define LIBSSH2_API __declspec(dllexport)
#endif
#include <libssh2_config.h>
#include <libssh2.h>
#include <libssh2_sftp.h>

#ifdef HAVE_WINDOWS_H
# include <windows.h>
#endif
#ifdef HAVE_WINSOCK2_H
# include <winsock2.h>
#endif
#ifdef HAVE_SYS_SOCKET_H
# include <sys/socket.h>
#endif
#ifdef HAVE_NETINET_IN_H
# include <netinet/in.h>
#endif
# ifdef HAVE_UNISTD_H
#include <unistd.h>
#endif
# ifdef HAVE_ARPA_INET_H
#include <arpa/inet.h>
#endif

LIBSSH2_SESSION *session;
LIBSSH2_CHANNEL *channel;
int sock;

// ---------------------------------------------------------------------------
//  Includes for signal handling.
// ---------------------------------------------------------------------------
#if !defined(WIN32)
    #include <signal.h>
#else
    #include <windows.h>
#endif
// ---------------------------------------------------------------------------

int min(int a, int b)
{
    if (a < b)
    {
        return a;
    }
    else
    {
        return b;
    }
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

void cleanup()
{
    libssh2_channel_free(channel);
    channel = NULL;
    libssh2_session_disconnect(session, "Normal Shutdown, Thank you for playing");
    libssh2_session_free(session);
    session = NULL;
    #ifdef WIN32
        closesocket(sock);
    #else
        close(sock);
    #endif
        printf("all done!\n");
        libssh2_exit();
    exit(0);
}

#if defined(WIN32)
    BOOL CtrlHandler(DWORD fdwCtrlType)
    {
        switch(fdwCtrlType)
        {
        case CTRL_C_EVENT:
            printf("CTRL-C\n");
            cleanup();
            exit(0);
        default:
            return FALSE;
        } // switch(fdwCtrlType)
    } // BOOL CtrlHandler(DWORD fdwCtrlType)
#else
    void stop(int s)
    {
        printf("CTRL-C\n");
        s = s;
        cleanup();
        exit(0);
    }
#endif


const char *keyfile1="~/.ssh/id_rsa.pub";
const char *keyfile2="~/.ssh/id_rsa";
const char *username="ubuntu";
const char *password="password";

static void kbd_callback(const char *name, int name_len,
                         const char *instruction, int instruction_len,
                         int num_prompts,
                         const LIBSSH2_USERAUTH_KBDINT_PROMPT *prompts,
                         LIBSSH2_USERAUTH_KBDINT_RESPONSE *responses,
                         void **abstract)
{
    (void)name;
    (void)name_len;
    (void)instruction;
    (void)instruction_len;
    if (num_prompts == 1) {
        responses[0].text = strdup(password);
        responses[0].length = strlen(password);
    }
    (void)prompts;
    (void)abstract;
} /* kbd_callback */

static int waitsocket(int socket_fd, LIBSSH2_SESSION *session, int timeout)
{
    struct timeval timeout_struct;
    int rc;
    fd_set fd;
    fd_set *writefd = NULL;
    fd_set *readfd = NULL;
    int dir;
 
    timeout_struct.tv_sec = timeout;
    timeout_struct.tv_usec = 0;
 
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

static std::string read_from_channel(LIBSSH2_CHANNEL *channel, int size, int timeout)
{    
    if (size <= 0)
    {
        size = 0x4000;
    }
    char *buffer = (char *)malloc(size);    
    std::string output;
    int time_elapsed;
    int byte_count;
    int rc;
    for (time_elapsed = 0, byte_count = 0;
         (time_elapsed < timeout) && (byte_count < size);
         time_elapsed += 1)
    {
        do
        {            
            rc = libssh2_channel_read(channel, buffer, size);
            if (rc > 0)
            {
                int i;
                byte_count += rc;
                //fprintf(stderr, "We read:\n");
                for(i=0; i < rc; ++i)
                {
                    fputc( buffer[i], stderr);
                }                    
                //fprintf(stderr, "\n");
            }
            else
            {
                if (rc != LIBSSH2_ERROR_EAGAIN)
                {
                    /* no need to output this for the EAGAIN case */ 
                    fprintf(stderr, "libssh2_channel_read returned %d\n", rc);
                }
            }
        }
        while( rc > 0 );
        output.append(buffer);

        /* this is due to blocking that would occur otherwise so we loop on
           this condition */ 
        if(rc == LIBSSH2_ERROR_EAGAIN)
        {
            waitsocket(sock, session, 1);
        }
        else
        {
            break;
        }
    } // outer for loop based on time and size
    free(buffer);
    return output;
}

static int sync_original_prompt(LIBSSH2_CHANNEL *channel)
{
    int rc = 0;
    char *line_break = "\n";
    std::string x, a, b;

    // Clear out the cache before getting the prompt;
    read_from_channel(channel, 10000, 1);

    boost::this_thread::sleep(boost::posix_time::milliseconds(100));    
    libssh2_channel_write(channel, line_break, 1);
    boost::this_thread::sleep(boost::posix_time::milliseconds(500));
    a = read_from_channel(channel, 1000, 1);

    boost::this_thread::sleep(boost::posix_time::milliseconds(100));    
    libssh2_channel_write(channel, line_break, 1);
    boost::this_thread::sleep(boost::posix_time::milliseconds(500));
    b = read_from_channel(channel, 1000, 1);

    int ld = levenstein_distance(a, b);
    int len_a = a.length();
    if (len_a == 0)
        rc = 1;
    else if (float(ld) / len_a > 0.4)
        rc = 1;
    return rc;
}

int main(int argc, char *argv[])
{
    unsigned long hostaddr;
    int rc, auth_pw = 0;
    struct sockaddr_in sin;
    const char *fingerprint;
    char *userauthlist;
    int bytecount = 0;
    std::string output;

    std::string unset_prompt = std::string("unset PROMPT_COMMAND\n");
    std::string unique_prompt = std::string("PS1='[PEXPECT]\\$ '\n");

#ifdef WIN32
    WSADATA wsadata;

    WSAStartup(MAKEWORD(2,0), &wsadata);
#endif

    // ---------------------------------------------------------------------------
    //  Register signal handler for CTRL-C, that will simply call exit().  This
    //  is primarily here to allow GCC profile guided optimisation (PGO) to work,
    //  as this requires the program under instrumentation to cleanly quit.
    //
    //  While we're at it support it on Windows as well; however Microsoft Visual
    //  Studio's (MSVC) PGO is smart enough to handle CTRL-C's.
    //
    //  References:
    //  - http://msdn.microsoft.com/en-us/library/ms685049%28VS.85%29.aspx
    //  - http://stackoverflow.com/questions/1641182/how-can-i-catch-a-ctrl-c-event-c
    // ---------------------------------------------------------------------------
    #if !defined(WIN32)
        struct sigaction sig_int_handler;
        sig_int_handler.sa_handler = stop;
        sigemptyset(&sig_int_handler.sa_mask);
        sig_int_handler.sa_flags = 0;
        sigaction(SIGINT, &sig_int_handler, NULL);
    #else
        SetConsoleCtrlHandler((PHANDLER_ROUTINE)CtrlHandler, TRUE);
    #endif
    // ---------------------------------------------------------------------------

    // ---------------------------------------------------------------------------
    //  Parse, validate command-line arguments.
    // ---------------------------------------------------------------------------
    po::options_description desc("Allowed options");
    desc.add_options()
        ("help", "Produce help message.")
        ("host,H", po::value< std::string >(), "An IP address or DNS hostname.")
        ("command,C", po::value< std::string >(), "Command to execute.")
        ("zeromq_bind,b", po::value< std::vector<std::string> >(), "One or more ip_address:port pairs to publish ZeroMQ messages from, e.g. 'tcp://127.0.0.1:5556'.")
        ("verbose,V", "Verbose debug output.");  
    po::positional_options_description positional_desc;
    positional_desc.add("command", -1);

    po::variables_map vm;
    po::store(po::command_line_parser(argc, argv).options(desc).positional(positional_desc).run(),
              vm);
    po::notify(vm);

    std::string host;
    if (!vm.count("host"))
    {
        std::cout << "Need to specify an IP address or DNS hostname for the host." << std::endl;
        std::cout << desc;
        exit(2);
    }
    else
    {
        host = vm["host"].as< std::string >();
        hostaddr = inet_addr(host.c_str());
    } // if (!vm.count("host"))

    std::string command;
    if (!vm.count("command"))
    {
        std::cout << "Need to specific a command to execute." << std::endl;
        std::cout << desc;
        exit(3);
    }
    else
    {
        command = vm["command"].as< std::string >();
        command.append("\n");
    } // if (!vm.count("command"))
    // ---------------------------------------------------------------------------

    rc = libssh2_init(0);
    if (rc != 0) {
        fprintf (stderr, "libssh2 initialization failed (%d)\n", rc);
        return 1;
    }

    /* Ultra basic "connect to port 22 on localhost".  Your code is
     * responsible for creating the socket establishing the connection
     */
    sock = socket(AF_INET, SOCK_STREAM, 0);

    sin.sin_family = AF_INET;
    sin.sin_port = htons(22);
    sin.sin_addr.s_addr = hostaddr;
    if (connect(sock, (struct sockaddr*)(&sin),
                sizeof(struct sockaddr_in)) != 0) {
        fprintf(stderr, "failed to connect!\n");
        return -1;
    }

    /* Create a session instance and start it up. This will trade welcome
     * banners, exchange keys, and setup crypto, compression, and MAC layers
     */
    session = libssh2_session_init();
    if (libssh2_session_handshake(session, sock)) {
        fprintf(stderr, "Failure establishing SSH session\n");
        return -1;
    }

    /* At this point we havn't authenticated. The first thing to do is check
     * the hostkey's fingerprint against our known hosts Your app may have it
     * hard coded, may go to a file, may present it to the user, that's your
     * call
     */
    fingerprint = libssh2_hostkey_hash(session, LIBSSH2_HOSTKEY_HASH_SHA1);
    /*
    printf("Fingerprint: ");
    for(i = 0; i < 20; i++) {
        printf("%02X ", (unsigned char)fingerprint[i]);
    }
    printf("\n");
    */

    /* check what authentication methods are available */
    userauthlist = libssh2_userauth_list(session, username, strlen(username));
    printf("Authentication methods: %s\n", userauthlist);
    if (strstr(userauthlist, "password") != NULL) {
        auth_pw |= 1;
    }
    if (strstr(userauthlist, "keyboard-interactive") != NULL) {
        auth_pw |= 2;
    }
    if (strstr(userauthlist, "publickey") != NULL) {
        auth_pw |= 4;
    }

    if (auth_pw & 1) {
        /* We could authenticate via password */
        if (libssh2_userauth_password(session, username, password)) {
            printf("\tAuthentication by password failed!\n");
            goto shutdown;
        } else {
            printf("\tAuthentication by password succeeded.\n");
        }
    } else if (auth_pw & 4) {
        /* Or by public key */
        if (libssh2_userauth_publickey_fromfile(session, username, keyfile1,
                                                keyfile2, password)) {
            printf("\tAuthentication by public key failed!\n");
            goto shutdown;
        } else {
            printf("\tAuthentication by public key succeeded.\n");
        }
    } else {
        printf("No supported authentication methods found!\n");
        goto shutdown;
    }

    /* Request a shell */
    if (!(channel = libssh2_channel_open_session(session))) {
        fprintf(stderr, "Unable to open a session\n");
        goto shutdown;
    }

    /* Some environment variables may be set,
     * It's up to the server which ones it'll allow though
     */
    //libssh2_channel_setenv(channel, "PS1", "[PEXPECT]");

    /* Request a terminal with 'vanilla' terminal emulation
     * See /etc/termcap for more options
     */
    if (libssh2_channel_request_pty(channel, "vanilla")) {
        fprintf(stderr, "Failed requesting pty\n");
        goto skip_shell;
    }

    /* Open a SHELL on that pty */
    if (libssh2_channel_shell(channel)) {
        fprintf(stderr, "Unable to request shell on allocated pty\n");
        goto shutdown;
    }

    /* At this point the shell can be interacted with using
     * libssh2_channel_read()
     * libssh2_channel_read_stderr()
     * libssh2_channel_write()
     * libssh2_channel_write_stderr()
     *
     * Blocking mode may be (en|dis)abled with: libssh2_channel_set_blocking()
     * If the server send EOF, libssh2_channel_eof() will return non-0
     * To send EOF to the server use: libssh2_channel_send_eof()
     * A channel can be closed with: libssh2_channel_close()
     * A channel can be freed with: libssh2_channel_free()
     */
    libssh2_channel_set_blocking(channel, 0);
    
    //std::cout << "first read..." << std::endl;
    rc = sync_original_prompt(channel);
    //std::cout << "sync_original_prompt: " << rc << std::endl;
    //std::cout << "first read completed." << std::endl;

    libssh2_channel_write(channel, unset_prompt.c_str(), unset_prompt.length());
    libssh2_channel_write(channel, unique_prompt.c_str(), unique_prompt.length());    
    
    libssh2_channel_write(channel, command.c_str(), command.length());
    output = read_from_channel(channel, -1, 5);
    std::cout << "-------" << std::endl;
    std::cout << output << std::endl;

  skip_shell:
    if (channel) {
        libssh2_channel_free(channel);
        channel = NULL;
    }

    /* Other channel types are supported via:
     * libssh2_scp_send()
     * libssh2_scp_recv()
     * libssh2_channel_direct_tcpip()
     */

  shutdown:

    libssh2_session_disconnect(session,
                               "Normal Shutdown, Thank you for playing");
    libssh2_session_free(session);

#ifdef WIN32
    closesocket(sock);
#else
    close(sock);
#endif
    printf("all done!\n");

    libssh2_exit();

    return 0;
}
