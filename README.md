# Zabbix Script for Monitoring XenServer

Monitoring Citrix XENSERVER Host and VMs based on Python XENApi. Orginal library taken from:
https://share.zabbix.com/cat-app/cluster/monitoring-citrix-xenserver-host-and-vms-based-on-pyton-xenapi

Installation notes

1. XenAPi attached to repo, was taken from: https://github.com/xapi-project/xen-api/tree/master/scripts/examples/python.

2. Copy file XENApi.py to directory /usr/local/lib/python3.9 (or similar existing) to the zabbix host or the zabbix proxy host.
If you want to change, please change line sys.path.append('/usr/local/lib/python3.9') to sys.path.append('<yourpath>') on line 98 also!


3. Copy citrix.xenserver.py from this repository to you externel script path and set userrights (chmod 755).
Default is /usr/lib/zabbix/externalscripts to the zabbix host or the zabbix proxy host.

4. Remember that script will be run as zabbix user not the root.

5. Import the templates
zbx_export_templates.xml --> contains both templates for VM and Host
### Please note, the the name in zabbix and the name in xen have to be the same!

6. Set macros (Global on on all host you use this templates)
{$XENMASTER} -->Masterserver of XENCLUSTER
{$XENUSERNAME} --> Username for connect to XENCLUSTER
{$XENPASSWORD} --> Password for connect to XENCLUSTER

7. Troubleshooting:
Run the script as zabbix user from your zabbix or zabbix proxy host.

Example:
/usr/lib/zabbix/externalscripts/citrix.xenserver.py -m "<xenmaster>" -u "<xen/xcp root>" -p "<password>" -t "host" -H "<hostname>" -c "value" -f "memory_free_kib"

Check if you see data gathered from xenmaster in /tmp/xenapi.<hostname>... log files. 
There should be 3 per hostname. 
