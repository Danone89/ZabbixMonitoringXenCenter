# Zabbix Script for Monitoring XenServer

Monitoring Citrix XENSERVER Host and VMs based on Python XENApi. Orginal library taken from:
https://share.zabbix.com/cat-app/cluster/monitoring-citrix-xenserver-host-and-vms-based-on-pyton-xenapi

Installation notes

1. Download Pyton XENApi.py from https://github.com/xapi-project/xen-api/tree/master/scripts/examples/python. Please use the last version, becaus of ssl support changes in pyton

 

2. Copy file XENApi.py to directory /usr/local/lib/python3.4 (or similar existing)

If you want to change, please change line sys.path.append('/usr/local/lib/python') to sys.path.append('<yourpath') on line 98 also!

 

3. Copy citrix.xenserver.py from this repository to you externel script path and set userrights (chmod 755).
Default is /usr/lib/zabbix/externalscripts

4. Import the templates

zbx_template_xenserver_host.xml -->Monitoring XEN Host

zbx_template_xenserver_vm.xml --> Monitoring XEN VMs

Please note, the the name in zabbix and the name in xen have to be the same!

 

5. Set macros (Global on on all host you use this templates)

{$XENMASTER} -->Masterserver of XENCLUSTER

{$XENUSERNAME} --> Username for connect to XENCLUSTER

{$XENPASSWORD} --> Password for connect to XENCLUSTER
