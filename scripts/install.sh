#!/bin/bash
#
# A simple bash script to install darkwallet desktop client at localhost.
#
# You should not run the script as root. Just run as normal user.
# $ bash darkwallet_desktop.sh
#
# sudo should only be used to install dependences.
#

unset LANG

FIRST_INSTALL=true

# check if are running as root. You shoul avoid starting this script as sudo or root.
WHOAMI(){
    if [[ $(id -u) -ne 0 ]] ; then 
        echo "[+] Check if sudo or root: OK..." 
    else
        echo "You shoul avoid starting this script as sudo or root."
        echo "Just run as normal user."
        echo " $ bash dw-desktop-dev.sh"
        exit 1
    fi
}

# Installing dependences to download, compile and install libbitcoin. NPM, python3, sqlipher and pip3 are also needed.
DEPENDENCIES(){
    sudo apt install build-essential autoconf automake libtool pkg-config git libboost-all-dev npm tor torsocks libpython3.5 libpython3.5-dev sqlcipher libsqlcipher-dev python3-pip libffi-dev python3-pycparser
}

# Create directory for local installation. Setting variables: DW_DSKTP | DW_LOG
# Another install path can be used changing DW_DSKTP variable (examplo: changing "export DW_DSKTP=$HOME/darkwallet_desktop" by "export DW_DSKTP=$HOME/workspace/darkwallet").
DW_CREATE_DIR(){ 
    DW_DSKTP=$HOME/darkwallet_desktop
    DW_LOG=$DW_DSKTP/debug.log
    if [ ! -d $DW_DSKTP ]; then
        mkdir -p $DW_DSKTP
        touch $DW_LOG 
    else
        echo "$DW_DSKTP exists. Leaving withot changes."
        FIRST_INSTALL=false
    fi
}

# Create directiory for local installation. Setting environment variables: PKG_CONFIG_PATH | LD_LIBRARY_PATH | USR_LOCAL_PATH
# Change "USR_LOCAL_PATH" to select a different path. (example: changing "export USR_LOCAL_PATH=$DW_DSKTP/usr" to "export USR_LOCAL_PATH=$HOME/usr")
USR_LOCAL_ENV(){
    if [ ! -d $DW_DSKTP/usr ]; then
        mkdir -p $DW_DSKTP/usr
        USR_LOCAL_PATH=$DW_DSKTP/usr
        PKG_CONFIG_PATH=$USR_LOCAL_PATH/lib/pkgconfig/
        LD_LIBRARY_PATH=$USR_LOCAL_PATH/lib
    elif [ -d $DW_DSKTP/usr ]; then
        USR_LOCAL_PATH=$DW_DSKTP/usr
        PKG_CONFIG_PATH=$USR_LOCAL_PATH/lib/pkgconfig/
        LD_LIBRARY_PATH=$USR_LOCAL_PATH/lib
        echo "$USR_LOCAL_PATH exists. Leaving withot changes."
    else 
        exit 1
    fi
}

# Install libsodium from https://github.com/jedisct1/libsodium.git
INSTALL_SODIUM(){
    echo "INSTALL_SODIUM" >> $DW_LOG
    echo "INSTALL_SODIUM"
    if [ ! -d $DW_DSKTP/libsodium ]; then
        cd $DW_DSKTP
        git clone https://github.com/jedisct1/libsodium.git
        cd $DW_DSKTP/libsodium
        ./autogen.sh >> $DW_LOG
        ./configure --prefix $USR_LOCAL_PATH >> $DW_LOG
        make -j2 install >> $DW_LOG
    elif [ -d $DW_DSKTP/libsodium ]; then
        echo "libsodium found. Leave without change."
    else
        exit 1
    fi
}

# Install libsecp256k1 from bitcoin-core:
INSTALL_secp256k1(){
    echo "INSTALL_secp256k1" >> $DW_LOG
    echo "INSTALL_secp256k1" 
    if [ ! -d $DW_DSKTP/secp256k1 ]; then
        cd $DW_DSKTP
        git clone https://github.com/bitcoin-core/secp256k1.git
        cd $DW_DSKTP/secp256k1
        ./autogen.sh >> $DW_LOG
        ./configure --prefix $USR_LOCAL_PATH --enable-module-recovery >> $DW_LOG
        make -j2 install >> $DW_LOG
    elif [ -d $DW_DSKTP/secp256k1 ]; then
        echo "libsecp256k1 found. Leave without change."
    else
        exit 1
    fi
}

# Install/Update libbitcoin:
INSTALL_LIBITCOIN(){
    echo "INSTALL_LIBITCOIN" >> $DW_LOG
    echo "INSTALL_LIBITCOIN"
    if [ ! -d $DW_DSKTP/libbitcoin ]; then
        cd $DW_DSKTP
        git clone https://github.com/libbitcoin/libbitcoin.git
        cd $DW_DSKTP/libbitcoin
        ./autogen.sh >> $DW_LOG
        ./configure --prefix $USR_LOCAL_PATH >> $DW_LOG
        make -j2 install >> $DW_LOG
    elif [ -d $DW_DSKTP/libbitcoin ]; then
        rm -rf $DW_DSKTP/libbitcoin
        cd $DW_DSKTP
        git clone https://github.com/libbitcoin/libbitcoin.git
        cd $DW_DSKTP/libbitcoin
        ./autogen.sh >> $DW_LOG
        ./configure --prefix $USR_LOCAL_PATH >> $DW_LOG
        make -j2 install >> $DW_LOG
    else
        exit 1
    fi
}

# Install/Update libbitcoin-c:
INSTALL_LIBBITCOINC(){ 
    echo "INSTALL_LIBITCOINC" >> $DW_LOG
    echo "INSTALL_LIBITCOINC"
    if [ ! -d $DW_DSKTP/libbitcoin-c ]; then
        cd $DW_DSKTP
        git clone https://github.com/libbitcoin/libbitcoin-c.git
        cd $DW_DSKTP/libbitcoin-c
        ./autogen.sh >> $DW_LOG
        ./configure --prefix $USR_LOCAL_PATH >> $DW_LOG
        make -j2 install >> $DW_LOG
    elif [ -d $DW_DSKTP/libbitcoin-c ]; then
        rm -rf $DW_DSKTP/libbitcoin-c
        cd $DW_DSKTP
        git clone https://github.com/libbitcoin/libbitcoin-c.git
        cd $DW_DSKTP/libbitcoin-c
        ./autogen.sh >> $DW_LOG
        ./configure --prefix $USR_LOCAL_PATH >> $DW_LOG
        make -j2 install >> $DW_LOG
    else
        exit 1 
    fi
}

# Install/Update python-libbitcoin:
INSTALL_PY_LIBBTC(){
    echo "INSTALL_PY_LIBBTC" >> $DW_LOG
    echo "INSTALL_PY_LIBBTC"
    if [ ! -d $DW_DSKTP/python-libbitcoin ]; then
        cd $DW_DSKTP
        git clone https://github.com/libbitcoin/python-libbitcoin.git
        cd $DW_DSKTP/python-libbitcoin/libbitcoin/bc
        python3 bc_build.py >> $DW_LOG
        export PYTHONPATH=$DW_DSKTP/python-libbitcoin
    elif [ $DW_DSKTP/python-libbitcoin ]; then
        unset PYTHONPATH
        rm -rf $DW_DSKTP/python-libbitcoin
        cd $DW_DSKTP
        git clone https://github.com/libbitcoin/python-libbitcoin.git 
        cd $DW_DSKTP/python-libbitcoin 
        cd $DW_DSKTP/python-libbitcoin/libbitcoin/bc
        python3 bc_build.py >> $DW_LOG
        export PYTHONPATH=$DW_DSKTP/python-libbitcoin
    else
        exit 1
    fi
}

# Python dependencies:---------------------------------------
# Install python cffi 1.9.1.
INSTALL_PY_CFFI(){
    echo "INSTALL_PY_CFFI" >> $DW_LOG
    echo "INSTALL_PY_CFFI"
    sudo pip3 install cffi
}

# Install pyzmq:
INSTALL_PYZMQ(){
    echo "INSTALL_PYZMQ" >> $DW_LOG
    echo "INSTALL_PYZMQ"
    sudo pip3 install pyzmq >> $DW_LOG
}

# Install python tornado:
INSTALL_TORNADO(){
    echo "INSTALL_TORNADO" >> $DW_LOG
    echo "INSTALL_TORNADO"
    sudo pip3 install tornado >> $DW_LOG
}

# Install python websockets:
INSTALL_WEBSOCKETS(){
    echo "INSTALL_WEBSOCKETS" >> $DW_LOG
    echo "INSTALL_WEBSOCKETS"
    sudo pip3 install websockets >> $DW_LOG
}

# Install pysqlcipher:
INSTALL_PYSQLCIPHER(){
    echo "INSTALL_PYSQLCIPHER" >> $DW_LOG
    echo "INSTALL_PYSQLCIPHER"
    sudo pip3 install pysqlcipher3 >> $DW_LOG
}

# Install python peewee:
INSTALL_PEEWEE(){
    echo "INSTALL_PEEWEE" >> $DW_LOG
    echo "INSTALL_PEEWEE"
    sudo pip3 install peewee >> $DW_LOG
}

#-----------------------------------------------------------

# Install/Update darkwallet daemon:
INSTALL_LAUNDERWALLET(){
    echo "INSTALL_LAUNDERWALLET" >> $DW_LOG
    echo "INSTALL_LAUNDERWALLET"
    if [ ! -d $DW_DSKTP/darkwallet ]; then
        cd $DW_DSKTP
        git clone https://github.com/RojavaCrypto/launderwallet
        mv $DW_DSKTP/launderwallet $DW_DSKTP/darkwallet
    elif [ -d $DW_DSKTP/darkwallet ]; then
        rm $DW_DSKTP/darkwallet
        cd $DW_DSKTP
        git clone https://github.com/RojavaCrypto/launderwallet
        mv $DW_DSKTP/launderwallet $DW_DSKTP/darkwallet
    else
        exit 1
    fi    
}

# Install/update darkwallet electron-ui 
INSTALL_ELECTRON_GUI(){
    echo "INSTALL_ELECTRON_GUI" >> $DW_LOG
    echo "INSTALL_ELECTRON_GUI"
    if [ ! -d $DW_DSKTP/darkwallet-electron-ui ]; then
        cd $DW_DSKTP
        git clone https://github.com/thirdicrypto/darkwallet-electron-ui.git
        cd $DW_DSKTP/darkwallet-electron-ui
        npm install
        npm install immutability-helper ws bufferutil utf-8-validate
    elif [ -d $DW_DSKTP/darkwallet-electron-ui ]; then
        rm $DW_DSKTP/darkwallet-electron-ui
        cd $DW_DSKTP
        git clone https://github.com/thirdicrypto/darkwallet-electron-ui.git
        cd $DW_DSKTP/darkwallet-electron-ui
        npm install
        npm install immutability-helper ws bufferutil utf-8-validate
    else
        exit 1
    fi    
}

# Include a darkwallet.desktop Icon to ~/.local: 
INCLUDE_0(){
    mkdir -p /home/genjix/.local/share/icons/hicolor/128x128/
    cp $DW_DSKTP/darkwallet-electron-ui/resources/images/icon_128.png $HOME/.local/share/icons/hicolor/128x128/darkwallet_icon_128.png
    mkdir -p $HOME/.local/share/applications
    touch $HOME/.local/share/applications/darkwallet.desktop
    DESKTOP_FILE=$HOME/.local/share/applications/darkwallet.desktop
    echo "[Desktop Entry]" > $DESKTOP_FILE
    echo "Version=1.0" >> $DESKTOP_FILE
    echo "Name=Darkwallet" >> $DESKTOP_FILE
    echo "Comment=Darkwallet - the bitcoin power wallet." >> $DESKTOP_FILE
    echo "Exec=$DW_DSKTP/run.sh" >> $DESKTOP_FILE
    echo "Path=$DW_DSKTP" >> $DESKTOP_FILE
    echo "Icon=$HOME/.local/share/icons/hicolor/128x128/darkwallet_icon_128.png" >> $DESKTOP_FILE
    echo "Terminal=false" >> $DESKTOP_FILE
    echo "Type=Application" >> $DESKTOP_FILE
    echo "Categories=Utility;Application;Development;Internet;Bitcoin;" >> $DESKTOP_FILE
    chmod +x $DESKTOP_FILE
    touch $DW_DSKTP/run.sh
    RUNSH=$DW_DSKTP/run.sh
    echo "#!/bin/bash" > $RUNSH
    echo "# Script to start DW desktop" >> $RUNSH
    echo "" >> $RUNSH
    echo "EXPORT_VARS(){" >> $RUNSH
    echo "    export PKG_CONFIG_PATH=$USR_LOCAL_PATH/lib/pkgconfig/" >> $RUNSH
    echo "    export LD_LIBRARY_PATH=$USR_LOCAL_PATH/lib" >> $RUNSH
    echo "    export PYTHONPATH=$DW_DSKTP/python-libbitcoin" >> $RUNSH
    echo "}" >> $RUNSH
    echo "" >> $RUNSH
    echo "START_DAEMON(){" >> $RUNSH
    echo "    python3 $DW_DSKTP/darkwallet/darkwallet-daemon.py &" >> $RUNSH
    echo "}" >> $RUNSH
    echo "" >> $RUNSH
    echo "START_WALLET(){" >> $RUNSH
    echo "    cd $DW_DSKTP/darkwallet-electron-ui" >> $RUNSH
    echo "    npm run dev" >> $RUNSH
    echo "}" >> $RUNSH
    echo "" >> $RUNSH
    echo "DAEMON_MUST_DIE(){" >> $RUNSH
    echo "    DMD=$(ps -aux | grep  darkwallet-daemon.py | grep -v grep | awk '{print $2}')"
    echo "    kill -SIGINT $(echo $DMD)" >> $RUNSH
    echo "}" >> $RUNSH
    echo "" >> $RUNSH
    echo "EXPORT_VARS" >> $RUNSH
    echo "START_DAEMON" >> $RUNSH
    echo "    if [ $? = "0" ];then" >> $RUNSH
    echo "        START_WALLET" >> $RUNSH
    echo "    else" >> $RUNSH
    echo "        echo \'error\'" >> $RUNSH
    echo "        exit 1" >> $RUNSH
    echo "    fi" >> $RUNSH
    echo "DAEMON_MUST_DIE" >> $RUNSH
    chmod +x $RUNSH
}



# Finish :D
FINISH(){
    echo "FINISH" >> $DW_LOG
    echo ""
    echo "[+] Logs at $DW_LOG"
    echo ""

}

# Run installation script:
WHOAMI
DW_CREATE_DIR
USR_LOCAL_ENV
if [ $FIRST_INSTALL == true ]; then
    DEPENDENCIES
    INSTALL_PY_CFFI
    INSTALL_PYZMQ
    INSTALL_TORNADO
    INSTALL_WEBSOCKETS
    INSTALL_PYSQLCIPHER
    INSTALL_PEEWEE
    INSTALL_SODIUM
    INSTALL_secp256k1
    INSTALL_LIBITCOIN
    INSTALL_LIBBITCOINC
    INSTALL_PY_LIBBTC
    INSTALL_LAUNDERWALLET
    INSTALL_ELECTRON_GUI
    INCLUDE_0
    FINISH
else
    INSTALL_LIBITCOIN
    INSTALL_LIBBITCOINC
    INSTALL_PY_LIBBTC
    INSTALL_LAUNDERWALLET
    INSTALL_ELECTRON_GUI
    FINISH
fi
exit 0
