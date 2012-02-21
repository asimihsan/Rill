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
#include <list>
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
#include <boost/assign/list_of.hpp>
#include <boost/algorithm/string.hpp>
using namespace boost::algorithm;

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

#include "ssh_utils.hpp"
#include "parsing.hpp"       
#include "dns_utils.hpp"

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
std::list< std::string > passwords = boost::assign::list_of
    ("!bootstra")       
    ("!bootstrap")    
    ("mng1")     
    ("pest123") 
    ("^MISTRb9")
    ("admin")    
    ("root")
    ("password");

/*
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
} // kbd_callback
*/

int main(int argc, char *argv[])
{
    unsigned long hostaddr;
    int rc, auth_pw = 0;
    struct sockaddr_in sin;
    const char *fingerprint;
    char *userauthlist;
    int bytecount = 0;
    std::string output;

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
        ("username,U", po::value< std::string >(), "Username.")
        ("password,P", po::value< std::string >(), "First password to try.")
        ("zeromq_bind,b", po::value< std::vector<std::string> >(), "One or more ip_address:port pairs to publish ZeroMQ messages from, e.g. 'tcp://127.0.0.1:5556'.")
        ("timeout,T", po::value< int >(), "Timeout in seconds for command. Put <= 0 for infinity.")
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
        trim(host);
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
        trim(command);
    } // if (!vm.count("command"))

    std::string username;
    if (!vm.count("username"))
    {
        username = "root";
    }
    else
    {
        username = vm["username"].as< std::string >();
        trim(username);
    } // if (!vm.count("username"))

    if (vm.count("password"))
    {
        std::string password = vm["password"].as< std::string >();
        passwords.push_front(password);
    }

    int timeout;
    if (!vm.count("timeout"))
    {
        timeout = 10;
    }
    else
    {
        timeout = vm["timeout"].as< int >();
    } // if (!vm.count("timeout"))
    // ---------------------------------------------------------------------------

    // ---------------------------------------------------------------------------
    //  We must have a host input. At this point it could either be an IP
    //  address, which we'll just use, or it could be a DNS hostname, which
    //  could resolve to one or more IP addresses. In the latter case
    //  assume the first IP address is good to go.
    // ---------------------------------------------------------------------------    
    if (!dns_utils::is_string_an_ipv4_address(host))
    {
        std::vector< std::string > ip_addresses;
        bool rc = dns_utils::resolve_hostname_to_ipv4(host,
                                                      ip_addresses);
        if (!rc)
        {
            std::cout << "Input host '" << host << "' not an IPv4 address, but can't be resolved using DNS." << std::endl;
            exit(1);
        } // if (!rc)
        host = ip_addresses[0];
    }    
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
    hostaddr = inet_addr(host.c_str());
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
    userauthlist = libssh2_userauth_list(session, username.c_str(), username.length());
    //printf("Authentication methods: %s\n", userauthlist);
    if (strstr(userauthlist, "password") != NULL) {
        auth_pw |= 1;
    }
    if (strstr(userauthlist, "keyboard-interactive") != NULL) {
        auth_pw |= 2;
    }
    if (strstr(userauthlist, "publickey") != NULL) {
        auth_pw |= 4;
    }

    if (auth_pw & 1)
    {
        /* We could authenticate via password */
        bool is_password_correct = false;
        BOOST_FOREACH( std::string password, passwords )
        {
            if (libssh2_userauth_password(session, username.c_str(), password.c_str()))
            {
                //std::cout << "Password '" << password << "' failed!" << std::endl;                                                
            }
            else
            {
                //std::cout << "Password '" << password << "' succeeed." << std::endl;                                
                is_password_correct = true;
                break;
            }
            
            libssh2_session_disconnect(session, "Don't mind me, I'm brute-forcing the password.");
            libssh2_session_free(session);
            #ifdef WIN32
            closesocket(sock);
            #else
            close(sock);
            #endif
            //libssh2_exit();

            sock = socket(AF_INET, SOCK_STREAM, 0);
            //libssh2_init(0);
            connect(sock,
                    (struct sockaddr*)(&sin),
                    sizeof(struct sockaddr_in));
            session = libssh2_session_init();
            if (libssh2_session_handshake(session, sock))
            {
                std::cout << "New session establishment fails!" << std::endl;
            }
            
        }
        if (!is_password_correct)
        {
            std::cout << "Authentication by password failed." << std::endl;
            goto shutdown;
        }

    }    
    else if (auth_pw & 4)
    {
        // Or by public key
        if (libssh2_userauth_publickey_fromfile(session,
                                                username.c_str(),
                                                keyfile1,
                                                keyfile2,
                                                NULL))
        {
            printf("\tAuthentication by public key failed!\n");
            goto shutdown;
        }
        else
        {
            //printf("\tAuthentication by public key succeeded.\n");
        }    
    }
    else
    {
        printf("No supported authentication methods found!\n");
        goto shutdown;
    }

    /* Request a shell */    
    while( (channel = libssh2_channel_open_session(session)) == NULL &&
           libssh2_session_last_error(session,NULL,NULL,0) ==
           LIBSSH2_ERROR_EAGAIN )
    {
        ssh_utils::waitsocket(sock, session, ssh_utils::MICROSECONDS_IN_ONE_HUNDRETH_SECOND);
    }
    if( channel == NULL )
    {
        fprintf(stderr,"Error\n");
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

    // -----------------------------------------------------------------------
    //  Make sure we're at a prompt and then reset it to something
    //  we know so that we can expect it in the future.
    // -----------------------------------------------------------------------
    int cnt;
    int base_delay;
    bool is_prompt_synced = false;
    for (cnt = 0, base_delay = 5;
         cnt < 10;
         base_delay *= 2)
    {
        //std::cout << "base_delay: " << base_delay << std::endl;
        rc = ssh_utils::sync_original_prompt(sock,
                                             session,
                                             channel,
                                             base_delay);
        if (!rc)
        {
            is_prompt_synced = true;
            break;
        }
    }
    if (!is_prompt_synced)
    {
        std::cout << "Problem syncing prompt." << std::endl;
    }
    rc = ssh_utils::reset_prompt_to_pexpect_version(sock, session, channel);
    // -----------------------------------------------------------------------    

    // -----------------------------------------------------------------------
    //  You now have pexpect-type access. Send commands, get output, act
    //  on output, send more commands, etc.
    // -----------------------------------------------------------------------
    output = ssh_utils::get_result_from_command_execution(sock,
                                                          session,
                                                          channel,
                                                          command,
                                                          timeout);    
    std::cout << output << std::endl;
    // -----------------------------------------------------------------------

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
    //printf("all done!\n");

    libssh2_exit();

    return 0;
}
