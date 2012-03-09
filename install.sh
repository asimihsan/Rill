#!/bin/bash

INSTALL_GMP=0
INSTALL_MPFR=0
INSTALL_MPC=0
INSTALL_GCC=0
INSTALL_CLANG_AND_LLVM=0

INSTALL_CURL=0
INSTALL_BOOST=0
INSTALL_ZLIB=0
INSTALL_OPENSSL=0
INSTALL_LIBSSH2=0
INSTALL_ZEROMQ=0
INSTALL_YAML=0
INSTALL_PIP=0
INSTALL_NMAP=0
INSTALL_APR=0
INSTALL_LOG4CXX=0
INSTALL_JSONCPP=0

INSTALL_R=1

# ----------------------------------------------------------------------------- 
#   Install GCC.
# ----------------------------------------------------------------------------- 

# GMP
if [[ $INSTALL_GMP -eq 1 ]];
then
    cd /usr/local/src
    rm -rf gmp-5.0.4*
    wget ftp://ftp.gnu.org/gnu/gmp/gmp-5.0.4.tar.bz2
    tar jxf gmp-5.0.4.tar.bz2
    cd gmp-5.0.4
    ./configure
    nice make -j8
    make install
    cd /usr/local/src
    rm -rf gmp-5.0.4*
fi

if [[ $INSTALL_MPFR -eq 1 ]];
then
    cd /usr/local/src
    rm -rf mpfr-3.1.0*
    wget http://www.mpfr.org/mpfr-current/mpfr-3.1.0.tar.bz2
    tar jxf mpfr-3.1.0.tar.bz2
    cd mpfr-3.1.0
    ./configure
    nice make -j8
    make install
    cd /usr/local/src
    rm -rf mpfr-3.1.0*
fi

if [[ $INSTALL_MPC -eq 1 ]];
then
    cd /usr/local/src
    wget http://www.multiprecision.org/mpc/download/mpc-0.8.2.tar.gz 
    tar vxf mpc-0.8.2.tar.gz
    cd mpc-0.8.2
    ./configure
    nice make -j8
    make install
    cd /usr/local/src
    rm -rf mpc-0.8.2*
fi

if [[ $INSTALL_GCC -eq 1 ]];
then
    cd /usr/local/src
    rm -rf gcc-4.6.2*
    wget ftp://ftp.mirrorservice.org/sites/sourceware.org/pub/gcc/releases/gcc-4.6.2/gcc-4.6.2.tar.bz2
    tar jxf gcc-4.6.2.tar.bz2
    cd gcc-4.6.2
    ./configure --with-gmp=/usr/local/lib/ --with-mpfr=/usr/local/lib --with-mpc=/usr/local/lib
    make -j8
    make install
    cd /usr/local/src
    rm -rf gcc-4.6.2*

    # cheap hack to fix the fact we installed gcc in /usr/local/ rather than /usr/
    # http://stackoverflow.com/questions/1952146/glibcxx-3-4-9-not-found
    cd /usr/lib64
    mv libstdc++.so.6 libstdc++.so.6.backup
    ln -s /usr/local/lib64/libstdc++.so.6 .
fi
# ----------------------------------------------------------------------------- 

#export CC=/usr/local/bin/gcc
#export CXX=/usr/local/bin/g++

# ----------------------------------------------------------------------------- 
#   Install Clang and LLVM.
# ----------------------------------------------------------------------------- 
if [[ $INSTALL_CLANG_AND_LLVM -eq 1 ]];
then
    cd /usr/local/src
    rm -rf llvm-3.0*
    rm -rf clang-3.0*
    wget http://llvm.org/releases/3.0/llvm-3.0.tar.gz
    wget http://llvm.org/releases/3.0/clang-3.0.tar.gz
    tar xvf llvm-3.0.tar.gz
    tar xvf clang-3.0.tar.gz
    mv clang-3.0.src llvm-3.0.src/tools/clang
    cd llvm-3.0.src
    ./configure
    nice make -j8
    make install
    cd /usr/local/src
    rm -rf llvm-3.0*
    rm -rf clang-3.0*
fi
# ----------------------------------------------------------------------------- 

# ----------------------------------------------------------------------------- 
#   Install Boost.
# ----------------------------------------------------------------------------- 
if [[ $INSTALL_BOOST -eq 1 ]];
then
    cd /usr/local/src/
    rm -rf boost_1_49_0*
    wget http://sourceforge.net/projects/boost/files/boost/1.49.0/boost_1_49_0.tar.bz2/download
    tar jxf boost_1_49_0.tar.bz2
    cd boost_1_49_0
    ./bootstrap.sh --with-libraries=all
    ./b2 install
    cd /usr/local/src
    rm -rf boost_1_49_0*
fi
# ----------------------------------------------------------------------------- 

# ----------------------------------------------------------------------------- 
#   Install zlib.
# ----------------------------------------------------------------------------- 
if [[ $INSTALL_ZLIB -eq 1 ]];
then
    cd /usr/local/src
    rm -rf zlib*
    wget http://zlib.net/zlib-1.2.6.tar.gz
    tar xvf zlib-1.2.6.tar.gz
    cd zlib-1.2.6
    ./configure
    nice make -j8
    make install
    ldconfig
    cd /usr/local/src
    rm -rf zlib*
fi
# ----------------------------------------------------------------------------- 

# ----------------------------------------------------------------------------- 
#   Install OpenSSL.
# ----------------------------------------------------------------------------- 
if [[ $INSTALL_OPENSSL -eq 1 ]];
then
    cd /usr/local/src
    rm -rf openssl-1.0.0g*
    wget http://www.openssl.org/source/openssl-1.0.0g.tar.gz
    tar xvf openssl-1.0.0g.tar.gz
    cd openssl-1.0.0g
    ./config no-asm
    nice make -j8
    make install
    ldconfig
    cd /usr/local/src
    rm -rf openssl-1.0.0g*
fi
# ----------------------------------------------------------------------------- 

# ----------------------------------------------------------------------------- 
#   Install libssh2
# ----------------------------------------------------------------------------- 
if [[ $INSTALL_LIBSSH2 -eq 1 ]];
then
    cd /usr/local/src
    rm -f libssh2*
    wget http://www.libssh2.org/download/libssh2-1.4.0.tar.gz
    tar xvf libssh2-1.4.0.tar.gz
    cd libssh2-1.4.0
    ./configure --with-openssl=/usr/local/lib --with-zlib=/usr/local/lib
    nice make all install -j8
    ldconfig
    cd /usr/local/src
    rm -rf libssh2*
fi
# ----------------------------------------------------------------------------- 

# ----------------------------------------------------------------------------- 
#   Install curl.
# ----------------------------------------------------------------------------- 
if [[ $INSTALL_CURL -eq 1 ]];
then
    cd /usr/local/src
    rm -rf curl*
    wget http://curl.haxx.se/download/curl-7.24.0.tar.bz2
    tar jxf curl-7.24.0.tar.bz2
    cd curl-7.24.0
    ./configure
    nice make -j8
    make install
    ldconfig
    cd /usr/local/src
    rm -rf curl*
fi

# ----------------------------------------------------------------------------- 

# ----------------------------------------------------------------------------- 
#   Install ZeroMQ.
# ----------------------------------------------------------------------------- 
if [[ $INSTALL_ZEROMQ -eq 1 ]];
then
    yes yes | yum install libuuid libuuid-devel
    cd /usr/local/src
    rm -rf zeromq*
    wget http://download.zeromq.org/zeromq-2.1.11.tar.gz
    tar xvf zeromq-2.1.11.tar.gz
    cd zeromq-2.1.11
    ./configure
    make -j8
    make install
    ldconfig
    cd /usr/local/src
    rm -rf zeromq*
fi
# ----------------------------------------------------------------------------- 

# ----------------------------------------------------------------------------- 
#   Install yaml.
# ----------------------------------------------------------------------------- 
if [[ $INSTALL_YAML -eq 1 ]];
then
    cd /usr/local/src
    rm -rf yaml*
    wget http://pyyaml.org/download/libyaml/yaml-0.1.4.tar.gz
    tar xvf yaml-0.1.4.tar.gz
    cd yaml-0.1.4
    ./configure
    nice make -j8
    make install
    cd /usr/local/src
    rm -rf yaml*
fi
# ----------------------------------------------------------------------------- 

# ----------------------------------------------------------------------------- 
#   Install pip.
# ----------------------------------------------------------------------------- 
if [[ $INSTALL_PIP -eq 1 ]];
then
    curl http://python-distribute.org/distribute_setup.py | python2.7
    curl https://raw.github.com/pypa/pip/master/contrib/get-pip.py | python2.7
    modules="cython pyzmq requests pymongo networkx pyyaml whoosh paramiko supervisor psutil"
    for module in $(echo $modules)
    do
        pip install ${module} --upgrade
    done
fi
# ----------------------------------------------------------------------------- 

# ----------------------------------------------------------------------------- 
#   Install nmap.
# ----------------------------------------------------------------------------- 
if [[ $INSTALL_NMAP -eq 1 ]];
then
    cd /usr/local/src
    rm -f nmap*
    wget http://nmap.org/dist/nmap-5.61TEST4.tar.bz2
    tar xjf nmap-5.61TEST4.tar.bz2
    cd nmap-5.61TEST4
    ./configure
    nice make -j8
    make install
    cd /usr/local/src
    rm -rf nmap*
fi
# ----------------------------------------------------------------------------- 

# ----------------------------------------------------------------------------- 
#   Install apr.
# ----------------------------------------------------------------------------- 
if [[ $INSTALL_APR -eq 1 ]];
then
    cd /usr/local/src
    rm -f apr*
    wget http://mirrors.enquira.co.uk/apache//apr/apr-1.4.6.tar.bz2
    tar xjf apr-1.4.6.tar.bz2
    cd apr-1.4.6
    ./configure
    nice make -j8
    make install
    cd /usr/local/src
    wget http://mirrors.enquira.co.uk/apache//apr/apr-util-1.4.1.tar.bz2
    tar xjf apr-util-1.4.1.tar.bz2
    cd apr-util-1.4.1
    ./configure --with-apr=/usr/local/apr
    nice make -j8
    make install
    cd /usr/local/src
    rm -rf apr*
fi
# ----------------------------------------------------------------------------- 

# ----------------------------------------------------------------------------- 
#   Install log4cxx.
# ----------------------------------------------------------------------------- 
if [[ $INSTALL_LOG4CXX -eq 1 ]];
then
    yes yes | yum install *log4cxx*
    #cd /usr/local/src
    #rm -rf apache*
    #wget http://apache.favoritelinks.net//logging/log4cxx/0.10.0/apache-log4cxx-0.10.0.tar.gz 
    #tar xvf apache-log4cxx-0.10.0.tar.gz
    #cd apache-log4cxx-0.10.0
    #./configure
    #nice make -j8
    #make install
    #cd /usr/local/src
    #rm -rf apache*
fi
# ----------------------------------------------------------------------------- 

# ----------------------------------------------------------------------------- 
#   Install jsoncpp
# ----------------------------------------------------------------------------- 
if [[ $INSTALL_JSONCPP -eq 1 ]];
then
    yes yes | yum insall scons
    cd /usr/local/src
    rm -rf jsoncpp*
    wget "http://downloads.sourceforge.net/project/jsoncpp/jsoncpp/0.5.0/jsoncpp-src-0.5.0.tar.gz?r=http%3A%2F%2Fsourceforge.net%2Fprojects%2Fjsoncpp%2Ffiles%2F&ts=1330220043&use_mirror=freefr"
    tar xvf jsoncpp-src-0.5.0.tar.gz
    cd jsoncpp-src-0.5.0
    scons platform=linux-gcc
    cd /usr/local/src/jsoncpp-src-0.5.0/libs/linux-gcc-4.4.4
    cp /usr/local/src/jsoncpp-src-0.5.0/libs/linux*/* /usr/local/lib
    cp -r /usr/local/src/jsoncpp-src-0.5.0/include/json /usr/local/include/json
    ldconfig
    #rm -rf jsoncpp*
fi
# ----------------------------------------------------------------------------- 

# ----------------------------------------------------------------------------- 
#   Install R.
# ----------------------------------------------------------------------------- 
if [[ $INSTALL_R -eq 1 ]];
then
    cd /usr/local/src
    rm -rf pixman*
    wget "http://cairographics.org/releases/pixman-0.24.4.tar.gz"
    tar xvf pixman-0.24.4.tar.gz
    cd pixman-0.24.4
    ./configure
    nice make -j8
    make install
    cd /usr/local/src
    rm -rf pixman*

    cd /usr/local/src
    rm -f libpng*
    wget "http://downloads.sourceforge.net/project/libpng/libpng15/1.5.9/libpng-1.5.9.tar.gz?r=http%3A%2F%2Fwww.libpng.org%2Fpub%2Fpng%2Flibpng.html&ts=1330783105&use_mirror=garr"
    tar xvf libpng-1.5.9.tar.gz
    cd libpng-1.5.9
    ./configure
    nice make -j8
    make install
    cd /usr/local/src
    rm -rf libpng*

    rm -rf cairo*
    wget "http://cairographics.org/releases/cairo-1.10.2.tar.gz"
    tar xvf cairo-1.10.2.tar.gz
    cd cairo-1.10.2
    ./configure
    nice make -j8
    make install
    cd /usr/local/src
    rm -rf cairo*

fi

# ----------------------------------------------------------------------------- 
