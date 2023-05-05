#!/usr/bin/python3.9
"""
Autor:      Robert Gladewitz
Change Autor: Daniel Bośnjak, Kamil Seweryn
Version :   1.1b
Change:     05 May 2023
Change info: 
    1. [bug fix] added separate log files for each/based on the host name 
    2. changed interpreter to python3.9 - currently used on Debian 11

Description
This script is based on XENApi, You can query performance counter for zabbix as external script.

Args:
   -h               Command line help
   -H <hostname>    Hostname of xenserver (-t host) or vm (-t vm)
   -m <hostname>    Hostname of xenserver master (ca be the same)
   -u <username>    Username for connect xenserver (local or domain user)
   -p <password>    Password for connect xenserver
   -c <command>     Command can be list, value  
   -f <filter>      filter for values or lists
                    (for list you can use regular expression, for values only the key)
   -t <host|vm>     querytype
   [-a <maxage>]    time of seconds, the cachefile will be use

Examles:
   List all CPUs
   citrix.xenserver.py -m myxenserver1 -u root -p "rootpass" -c list -f "cpu\d+" -t host -H myxenserver2

   List all network interfaces
   citrix.xenserver.py -m myxenserver1 -u root -p "rootpass" -c listni -f ".*" -t host -H myxenserver2
   
   List all network interfaces
   citrix.xenserver.py -m myxenserver1 -u root -p "rootpass" -c listsr -f ".*" -t host -H myxenserver2
   
   List all vbd in a vm
   citrix.xenserver.py -m myxenserver1 -u root -p "rootpass" -c listvbd -f ".*" -t host -H myvmhost

   Get value of cpu2
   citrix.xenserver.py -m myxenserver1 -u root -p "rootpass" -c value -f cpu2 -t host -H myxenserver2


Some knowing error.

DNS
The XENApi functions returns the short name of xencluster server. So, if you are not have dns domain in search list, the resultion 
do not work. 

Execution and filesystem rights for cache file
If you test this script as root it will be created an cachefile. So, if zabbix later start this script as user user zabbix or 
www-data, the old cache file (creates by user root) can not open for writing. This script will exit with error.

#################################################################################################################################
"""

#import urllib2
import urllib.request as request
import xml.dom.minidom
import sys, time
import itertools
import re
import shutil
import ssl
import getopt
import os
import fcntl
import logging
import logging.handlers


"""
default paramater as global vars
if you use multibly xencluster, please change this

Attributes:
	temphostfile: tempfile for store rrd values of xenhosts
	tempvmfile:   tempfile for store rrd values of vms
	maxage:       time in seconds, the maximal age before the date will be requery
"""

temphostfile = '/tmp/xenapi.hostperformance.tmp'
tempvmfile   = '/tmp/xenapi.vmperformance.tmp'
tempsrfile   = '/tmp/xenapi.srlist.tmp'
maxage       = 60

"""
#################################################################################################################################
Other default setting
ssl._create_default_https_context = ssl._create_unverified_context

In most installation, the admin interface of xen servers use a self signed certificate. In this case, we need to disable
verifications.


sys.path.append('/usr/local/lib/python')
Path where the XENApi is located.

"""
ssl._create_default_https_context = ssl._create_unverified_context

sys.path.append('/usr/local/lib/python3.9')
import XenAPI
"""
#################################################################################################################################
# Additional Classes
#
"""
class Lock:
    """
    Lock class s for a system wide unix lock
    """
    def __init__(self, filename):
        """
        init of class Lock

        Args:
        filename (str): path of file will be use for locking (eg. /tmp/mylockfile)
        """
        self.filename = filename
        self.handle = open(filename, 'w')
 
    def acquire(self):
        """
        class function acuire - start lock
        """
        fcntl.flock(self.handle, fcntl.LOCK_EX)

    def release(self):
        """
        class function release - end lock
        """
        fcntl.flock(self.handle, fcntl.LOCK_UN)
 
    def __del__(self):
        """
        del of class Lock
        """
        self.handle.close()
        if os.path.isfile(self.filename): os.remove(self.filename)


#################################################################################################################################
def getHostsVms(xenmaster, username, password, xenhosts, xenvms, xensrs):
    """
    function getHostsVms get all available virtual machines in a xencluster
    """

    url = 'https://%s/' % xenmaster
    session = XenAPI.Session(url, ignore_ssl=True)
    try:
        session.login_with_password(username,password,"1.0","citrix.py")
    except XenAPI.Failure as e:
        if (e.details[0] == 'HOST_IS_SLAVE'):
            session=XenAPI.Session("https://" + e.details[1])
            session.login_with_password(username,password)
        else:
            raise
    sx = session.xenapi
    retval = False

    for host in sx.host.get_all():
        xenhosts[sx.host.get_uuid(host)] = sx.host.get_hostname(host)
        for pbd in sx.host.get_PBDs(host):
             sr = sx.PBD.get_SR(pbd)
             srname = sx.SR.get_name_label(sr).replace(' ','_')
             if (re.match(r"(DVD_drives|Removable_storage|XenServer_Tools)", srname)):
                continue
             xensrs[sx.SR.get_uuid(sr)] = srname

        for vm in sx.host.get_resident_VMs(host):
            xenvms[sx.VM.get_uuid(vm)] = sx.VM.get_name_label(vm)
      
        retval = True

    sx.logout()

    return retval

#################################################################################################################################
def getStatsXML(hostname, username, password, delay):
    start = int(time.time()) - 2 * int(delay)
    theurl = 'https://%s/rrd_updates?start=%s&host=true&cf=ave&interval=%s' % (hostname, start, delay)
    passman = request.HTTPPasswordMgrWithDefaultRealm()
    passman.add_password(None, theurl, username, password)
    authhandler = request.HTTPBasicAuthHandler(passman)
    opener = request.build_opener(authhandler)
    request.install_opener(opener)
    pagehandle = request.urlopen(theurl)
    return pagehandle.read()

#################################################################################################################################
def getStats(xenhosts, username, password, delay):
    legendArr = []
    valueArr = []

    for hostname in xenhosts.values():
        page = getStatsXML(hostname, username, password, delay)

        dom = xml.dom.minidom.parseString(page)
        legends = dom.getElementsByTagName("legend")[0]
        for legend in legends.getElementsByTagName("entry"):
            legendArr.append(legend.childNodes[0].data)

        values = dom.getElementsByTagName("row")[0]
        for v in values.getElementsByTagName("v"):
            valueArr.append(v.childNodes[0].data)

    return dict(zip(legendArr,valueArr))

#################################################################################################################################
def printMetric(f, host, hostsCpu, hostsCpuCount, metric, value):
    # only for summarize cpu usage
    if (re.match(r"cpu\d+", metric)):
        if ( host in hostsCpu):
            hostsCpuCount[host] += 1
            hostsCpu[host] += float(value)
        else:
            hostsCpuCount[host] = 1
            hostsCpu[host] = float(value)

    # put all values in cache file	
    f.write("%s %s %s\n" % (host, metric, value))

#################################################################################################################################
def printHostCpu(f, hostsCpu, hostsCpuCount):
    for key, value in hostsCpu.items():
        f.write("%s cpu %s\n" % (key, value))

    for key, value in hostsCpuCount.items():
        f.write("%s cpu_count %s\n" % (key, value))

#################################################################################################################################
def printStats(values, hosts, vms, srs, filename, vmfilename, srfilename):
    hostsCpu = dict()
    vmsCpu = dict()
    hostsCpuCount = dict()
    vmsCpuCount = dict()
    virtual = False

    f  =open(filename, 'w')
    vf = open(vmfilename, 'w')
    sf = open(srfilename, 'w')


    for key, value in srs.items():
        match = re.match(r"([0-9aAbBcCdDeEfF]+)-", key)
        sf.write("%s %s %s\n" % (match.group(1), key, value))

    for key, value in values.items(): 
        match = re.match(r"(\S+)\:(\S+)\:(\S+)\:(\S+)", key)
        if (match.group(1) == 'AVERAGE'):
            metric = match.group(4)

            # find hostname
            if (match.group(2) == 'host'):
                if ( match.group(3)  in hosts):
                    host = hosts[match.group(3)]
                else:
                    continue
                printMetric(f, host, hostsCpu, hostsCpuCount, metric, value)
            elif (match.group(2) == 'vm'):
                if (match.group(3) in vms):
                    host = vms[match.group(3)]
                else:
                    continue
                # skip control domain
                if ('Control domain on host' in host):
                    continue
                printMetric(vf, host, vmsCpu, vmsCpuCount, metric, value)
            else:
                continue

    printHostCpu(f, hostsCpu, hostsCpuCount)
    printHostCpu(vf, vmsCpu, vmsCpuCount)

    f.close()
    vf.close()

#################################################################################################################################
def refreshdatefiles(xenmaster, username, password, maxage):
    xenhosts  = dict()
    xenvms    = dict()
    xensrs    = dict()
    global temphostfile
    global tempvmfile
    global tempsrfile

    try:
        lock = Lock(temphostfile+".lock")
        lock.acquire()
        if os.path.isfile(temphostfile) and os.path.isfile(tempvmfile) and time.time() - os.path.getmtime(temphostfile) < maxage:
            lock.release()
            return
        elif (not getHostsVms(xenmaster, username, password, xenhosts, xenvms, xensrs) ):
            print ("ERROR: xenmaster not found or not available")
            sys.exit(254)
        else:
            values = getStats(xenhosts, username, password, maxage)

            printStats(values, xenhosts, xenvms, xensrs, temphostfile + '.cache', tempvmfile + '.cache', tempsrfile + '.cache')

            shutil.move(temphostfile + '.cache', temphostfile)
            shutil.move(tempvmfile + '.cache', tempvmfile)
            shutil.move(tempsrfile + '.cache', tempsrfile)

    finally:
        lock.release()

#################################################################################################################################
def printoutKeysByRegex(filename, hostname, rexreg):
    f = open(filename, 'r')
    lines = f.readlines()
    f.close()
    first = True

    print ('{')
    sys.stdout.write ('   "data":[')
    
    for line in lines:
        match = re.match(r"(\S+) (\S+) (\S+)", line)
        if ( match.group(1) == '' or  match.group(2) == '' or  match.group(3) == ''): continue 
        if (match.group(1) == hostname):
            if (re.match(rexreg, match.group(2))):
                if (first): 
                    sys.stdout.write('\n')
                else: 
                    sys.stdout.write(',\n')
            outstring = '        { "{#CPUNAME}":"' + match.group(2) + '" }' 
        sys.stdout.write (outstring)
        first = False

    print ('\n    ]')
    print ('}')

#################################################################################################################################
def printoutNetinterfaces(filename, hostname, rexreg):
    f = open(filename, 'r')
    lines = f.readlines()
    f.close()
    first = True
    ni = dict()


    for line in lines:
        match = re.match(r"(\S+) (\S+) (\S+)", line)
        if ( match.group(1) == '' or  match.group(2) == '' or  match.group(3) == ''): continue
        if (match.group(1) == hostname and re.match(r"^[vp]if.*",match.group(2))):
            matchinterfaces = re.match(r"([vp]if)_(\S+)_(\S+)$",match.group(2))
            ni[matchinterfaces.group(1)+"_"+matchinterfaces.group(2)] = matchinterfaces.group(2)

    print ('{')
    sys.stdout.write ('   "data":[')

    for key, value in ni.items():
        if (re.match(rexreg,key)):
            if (first): sys.stdout.write('\n')
            else: sys.stdout.write(',\n')
            outstring = '        { "{#KEY}":"%s", "{#NAME}":"%s" }' % ( key, value)
            sys.stdout.write (outstring)
            first = False

    print ('\n    ]')
    print ('}')

#################################################################################################################################
def printoutVirtualdisks(filename, hostname, rexreg):
    f = open(filename, 'r')
    lines = f.readlines()
    f.close()
    first = True
    ni = dict()


    for line in lines:
        match = re.match(r"(\S+) (\S+) (\S+)", line)
        if ( match.group(1) == '' or  match.group(2) == '' or  match.group(3) == ''): continue
        if (match.group(1) == hostname and re.match(r"^vbd.*",match.group(2))):
            matchinterfaces = re.match(r"vbd_([^_]+)_.*",match.group(2))
        ni["vbd_"+matchinterfaces.group(1)] = matchinterfaces.group(1)

    print ('{')
    sys.stdout.write ('   "data":[')

    for key, value in ni.items():
        if (re.match(rexreg,key)):
            if (first): sys.stdout.write('\n')
            else: sys.stdout.write(',\n')
            outstring = '        { "{#KEY}":"%s", "{#NAME}":"%s" }' % ( key, value)
            sys.stdout.write (outstring)
            first = False

    print ('\n    ]')
    print ('}')



#################################################################################################################################
def printoutValueByKeyname(filename, hostname, keyname):
    f = open(filename, 'r')
    lines = f.readlines()
    f.close()

    for line in lines:
        match = re.match(r"(\S+) (\S+) (\S+)", line)
        if ( match.group(1) == '' or  match.group(2) == '' or  match.group(3) == ''): continue 
        if (match.group(1) == hostname):
            if ( match.group(2) == keyname):
                print (match.group(3))
                break
 
#################################################################################################################################
def printoutSrs(filename, rexreg):
    f = open(filename, 'r')
    lines = f.readlines()
    f.close()
    first = True
 
    print ('{')
    sys.stdout.write ('   "data":[')
    for line in lines:
        match = re.match(r"(\S+) (\S+) (\S+)", line)
        if ( match.group(1) == '' or  match.group(2) == '' or  match.group(3) == ''): continue
        if (re.match(rexreg, match.group(2))):
            if (first): sys.stdout.write('\n')
            else: sys.stdout.write(',\n')
            outstring = '        { "{#KEY}":"%s", "{#UUID}":"%s", "{#NAME}":"%s" }' % ( match.group(1), match.group(2), match.group(3))
            sys.stdout.write (outstring)
            first = False 

    print ('\n    ]')
    print ('}')
        

            
#################################################################################################################################
#################################################################################################################################
#################################################################################################################################
def main(argv):
    xenmaster = ''
    username  = ''
    password  = ''
    command   = ''
    filter    = ''
    host      = ''
    type      = ''
    global maxage
    global temphostfile
    global tempvmfile
    global tempsrfile

    # get commandline args
    try:
        opts, args = getopt.getopt(argv,"ham:u:p:c:f:t:H:")
    except getopt.GetoptError as err:
        print (sys.argv[0], " -m <master> -u <username> -p <password> -c <command> -f <filter> -t <host|vm> -H <hostname|vmname> [-a <maxage>]")
        sys.exit(255)

    for opt, arg in opts:
        if opt == '-h':
            print (sys.argv[0], " -m <master> -u <username> -p <password> -c <command> -f <filter> -t <host|vm> -H <hostname|vmname> [-a <maxage>]")
            sys.exit(0)
        elif opt == '-m':
            xenmaster = arg
        elif opt == '-u': 
            username = arg
        elif opt == '-p':
            password = arg
        elif opt == '-a':
            maxage = arg
        elif opt == '-c':
            command = arg
        elif opt == '-f':
            filter = arg
        elif opt == '-t':
            type = arg
        elif opt == '-H':
            host = arg
            temphostfile = "/tmp/xenapi." + host + ".hostperformance.tmp"
            tempvmfile   = "/tmp/xenapi." + host + ".vmperformance.tmp"
            tempsrfile   = "/tmp/xenapi." + host + ".srlist.tmp"
            
    if (xenmaster == '' or username == '' or password == '' or command == '' or filter == '' or type == '' or host == '' ):
        print (sys.argv[0], " -m <master> -u <username> -p <password> -c <command> -f <filter> -t <host|vm> -H <hostname|vmname> [-a <maxage>] (Parameter missing)")
        sys.exit(3)

    # check for refresh data
    refreshdatefiles(xenmaster, username, password, maxage)

    filename = '';
    if ( type == 'host' ): filename = temphostfile
    elif (type == 'vm' ): filename = tempvmfile
    else:
        print ("Parameter t must be host or vm")
        sys.exit(2)

    if   ( command == 'list' ):    printoutKeysByRegex(filename,host,filter)
    elif ( command == 'listsr' ):  printoutSrs(tempsrfile,filter)
    elif ( command == 'listni' ):  printoutNetinterfaces(filename,host,filter)
    elif ( command == 'listvbd' ): printoutVirtualdisks(filename,host,filter)
    elif ( command == 'value' ):   printoutValueByKeyname(filename,host,filter)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1:])

    else:
        print ("Usage:")
        print (sys.argv[0], " -m <master> -u <username> -p <password> -a <maxage>")
        sys.exit(1)

