# CGW Tester version2.0

import boto3
from botocore.exceptions import ClientError
import re
import cgwdependencies.aws_resources as a
import cgwdependencies.swvars as b
import sqlite3
import subprocess


ec2 = boto3.client('ec2', region_name='us-east-1')

# stop strongswan before continuing
subprocess.call(['ipsec','stop'])

# Setup sqlite3 
conn = sqlite3.connect('/etc/strongswan/cgw-db.sqlite3')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS resources(gateway text PRIMARY KEY, cgw text, vpn text, region text)''')
conn.commit()

# Clean up user input and create list out of vgws string
gws = b.vgws.replace(' ','').lower()
gws = gws.split(',')

# Create dict out of list of gateways and their routing type
gws_dict={}
for x,y in zip(gws[::2], gws[1::2]):
        gws_dict[x] = y

# Check each AWS region for each TGW/VGW in our list
regions = ec2.describe_regions()
regions = regions['Regions']

def strongswan_config(*args):
    # configure strongswan
    with open('/etc/ipsec.conf', 'ab+') as f:
        f.write('conn %s\n'
                '\tkeyexchange=%s\n'
                '\tauto=start\n'
                '\ttype=tunnel\n'
                '\tauthby=secret\n'
                '\tleftid=%s\n'
                '\tleft=%%defaultroute\n'
                '\tright=%s\n'
                '\tikelifetime=%s\n'
                '\tlifetime=%s\n'
                '\tmargintime=%s\n'
                '\trekeyfuzz=%s\n'
                '\tesp=%s\n'
                '\tike=%s\n'
                '\tkeyingtries=%%forever\n'
                '\tleftsubnet=0.0.0.0/0\n'
                '\trightsubnet=0.0.0.0/0\n'
                '\tdpddelay=10s\n'
                '\tdpdtimeout=30s\n'
                '\tdpdaction=restart\n'
                '\tmark=%s\n'
                '\tleftupdown="/etc/strongswan/cgwdependencies/updown.bash -ln %s -ll %s -lr %s -m %s -t %s"\n\n' % args)

def psk_config(remote_ip, psk):
    # configure ipsec PSK
    with open('/etc/ipsec.secrets', 'ab+') as f:
        f.write('%%any %s : PSK "%s"\n' % (remote_ip, psk))

def configure_quagga(remote_asn, remote_tunnel_ip):
    # configure quagga
    with open('/etc/quagga/bgpd.conf', 'ab+') as f:
        f.write('\tneighbor {0} remote-as {1}\n'
		        '\tneighbor {0} soft-reconfiguration inbound\n' .format (remote_tunnel_ip, remote_asn))

# Iterate through all gateways and see if they exist in a AWS region           
mark = 0
for g in gws_dict:
    match = re.match(r'tgw.*', g)
    for r in regions:
        ec2 = boto3.client('ec2', region_name=r['RegionName'])
        if match:
            try:
                ec2.describe_transit_gateways(
                    TransitGatewayIds=[g]
                )

                # Check whether a VPN should be static or dynamic. Use variable when creating VPN
                if gws_dict[g] == 'dynamic':
                    rtype = False
                else:
                    rtype = True
                
                cgw = a.Cgw(b.asn, region_name=r['RegionName'])
                vpn = a.Vpn(cgw.id, g, rtype, b.localRoute, region_name=r['RegionName'])

                # Configure tunnel 1
                mark = int(mark)
                mark += 10
                mark = str(mark)
                
                strongswan_config(vpn.name + '-0', b.ikeVersion, vpn.cgw_outside, vpn.remote_outside1, b.ikeLifeTime, b.espLifeTime, b.margin, b.fuzz, b.espParameters, b.ikeParameters, mark,
                'vti' + mark, vpn.local_inside1, vpn.remote_inside1, mark, gws_dict[g])

                psk_config(vpn.remote_outside1, vpn.psk1)

                # see if the VPN is dynamic or static. If dynamic create entry in BGP config
                if gws_dict[g] == 'dynamic':
                    configure_quagga(vpn.remote_asn, vpn.remote_inside1)

                # Configure tunnel 2
                mark = int(mark)
                mark += 10
                mark = str(mark)
                
                strongswan_config(vpn.name + '-1', b.ikeVersion, vpn.cgw_outside, vpn.remote_outside2, b.ikeLifeTime, b.espLifeTime, b.margin, b.fuzz, b.espParameters, b.ikeParameters, mark,
                'vti'+ mark, vpn.local_inside2, vpn.remote_inside2, mark, gws_dict[g])

                psk_config(vpn.remote_outside2, vpn.psk2)
                if gws_dict[g] == 'dynamic':
                    configure_quagga(vpn.remote_asn, vpn.remote_inside2)

                break
            except ClientError as e:
                if e.response['Error']['Code'] == 'InvalidTransitGatewayID.NotFound':
                    pass
    
        else:
            try:
                ec2.describe_vpn_gateways(
                    VpnGatewayIds=[g]
                )
                # Check whether a VPN should be static or dynamic. Use variable when creating VPN
                if gws_dict[g] == 'dynamic':
                    rtype = False
                else:
                    rtype = True
                cgw = a.Cgw(b.asn, region_name=r['RegionName'])
                vpn = a.Vpn(cgw.id, g, rtype, b.localRoute, region_name=r['RegionName'])
                

                # Configure tunnel 1
                mark = int(mark)
                mark += 10
                mark = str(mark)
                
                strongswan_config(vpn.name + '-0', b.ikeVersion, vpn.cgw_outside, vpn.remote_outside1, b.ikeLifeTime, b.espLifeTime, b.margin, b.fuzz, b.espParameters, b.ikeParameters, mark,
                'vti'+ mark, vpn.local_inside1, vpn.remote_inside1, mark, gws_dict[g])

                psk_config(vpn.remote_outside1, vpn.psk1)

                if gws_dict[g] == 'dynamic':
                    configure_quagga(vpn.remote_asn, vpn.remote_inside1)

                # Configure tunnel 2
                mark = int(mark)
                mark += 10
                mark = str(mark)
                
                strongswan_config(vpn.name + '-1', b.ikeVersion, vpn.cgw_outside, vpn.remote_outside2, b.ikeLifeTime, b.espLifeTime, b.margin, b.fuzz, b.espParameters, b.ikeParameters, mark,
                'vti'+ mark, vpn.local_inside2, vpn.remote_inside2, mark, gws_dict[g])

                psk_config(vpn.remote_outside2, vpn.psk2)

                if gws_dict[g] == 'dynamic':
                    configure_quagga(vpn.remote_asn, vpn.remote_inside2)


                break
            except ClientError as e:
                if e.response['Error']['Code'] == 'InvalidVpnGatewayID.NotFound':
                    pass

# Compare each VPN in the DB against each gw in the list. Delete VPNs that user removed
c.execute("SELECT vpn, gateway, region FROM resources")
existing_conns = c.fetchall()

for vpn in existing_conns:
    if vpn[1] not in gws:
        a.del_vpn(vpn[0], region_name=vpn[2])
        c.execute('''DELETE FROM resources WHERE gateway=?''', (vpn[1],))

conn.commit()
conn.close()
subprocess.call(['ipsec','start'])
