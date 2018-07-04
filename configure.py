import boto3
from swvars import APIMODEL,ASN,VGWS,LOCAL_ROUTES,IKEVERSION,IKEPARAMETERS,IKELIFETIME,ESPPARAMETERS,ESPLIFETIME,MARGIN,FUZZ
from botocore.exceptions import ClientError
import xml.etree.ElementTree as ET
import sys
import os
import re
import fileinput
from ec2_metadata import ec2_metadata
from subprocess import call
from time import sleep

try:
	# Enable API support for TGW
	APIMODEL = APIMODEL.split('/')
	s3.meta.client.download_file(APIMODEL[0], '/'.join(APIMODEL[1:len(APIMODEL)]), '/tmp/service-2.json')
	call(["aws", "configure", "add-model", "--service-model", "file:///tmp/service-2.json", "--service-name", "ec2"])
except:
	print "User's model was either inaccessible or non-existent"
	continue

EIP = ec2_metadata.public_ipv4
client = boto3.client('ec2',region_name = 'us-east-2')

# Stop the strongswan service so we can update its configuration smoothly
call(["service","strongswan","stop"])

# Get rid of possible whitespaces in the VGWs string and then turn the string into a iterable list
VGWS = VGWS.replace(" ", "")
VGWS = VGWS.split(',')

# Other needed variables
SWCONF='/etc/strongswan/ipsec.conf'
SWSECRET='/etc/strongswan/ipsec.secrets'
UPDOWN='/etc/strongswan/aws.updown'
BGPDCONF='/etc/quagga/bgpd.conf'
TRACKFILE='/etc/strongswan/.vpntrackfile'

# We'll be removing certain lines (config) from different files later on, so creating a function for that
def remove_stuff(item,file,num):
	counter = 0
	for line in fileinput.input(file, inplace=True):
		if not counter:
			if line.startswith(str(item)):
				counter = num
			else:
				print line, 
		else:
			counter -= 1

def make_vpn(x,y,z):
	# Get a list of all AWS Regions
	response = client.describe_regions()

	# Now iterate through regions, and see if any of the specified VGWs are located in that region. If so, build a VPN to it
	for i in response['Regions']:
			EC2 = boto3.client('ec2',region_name=i['RegionName'])
			try:
					# Find if we're working with a VGW or TGW
					TGWEXISTS = re.search('tgw-',x)
					if TGWEXISTS:
						GATEWAYS = EC2.describe_transit_gateways(TransitGatewayIds=[x],ResourceOwner='self')
					else:
						GATEWAYS = EC2.describe_vpn_gateways(VpnGatewayIds=[x])
					
					# The VGW exists in this region, so let's create a CGW in the same region so we can create a VPN to it
					CGW = EC2.create_customer_gateway(
						BgpAsn=ASN,
						PublicIp=EIP,
						Type='ipsec.1',
					)
					CGW = CGW['CustomerGateway']['CustomerGatewayId']
					
					if TGWEXISTS:
						# Create a new VPN with the above information
						VPNCONNECTION = EC2.create_vpn_connection(
								CustomerGatewayId=CGW,
								Type='ipsec.1',
								TransitGatewayId = x,
								Options={
									'StaticRoutesOnly': y
								}
							)
					else:
						VPNCONNECTION = EC2.create_vpn_connection(
								CustomerGatewayId=CGW,
								Type='ipsec.1',
								VpnGatewayId = x,
								Options={
									'StaticRoutesOnly': y
								}
							)
					VPNCONNECTIONID=VPNCONNECTION['VpnConnection']['VpnConnectionId']
					
					# We need to track this VPN id in case we need to delete it later
					with open(TRACKFILE,'ab') as f:
						f.write(VPNCONNECTIONID + '\n')
					
					DOWNLOADCONFIG=VPNCONNECTION['VpnConnection']['CustomerGatewayConfiguration']
					
					if y:
						# We'll also need to update the VPN with these static routes if it is static.
						VPNROUTE = EC2.create_vpn_connection_route(
							DestinationCidrBlock=LOCAL_ROUTES,
							VpnConnectionId=VPNCONNECTION['VpnConnection']['VpnConnectionId']
						)
					
					# Let's extract our information to build the VPN in strongswan and openswan
					root = ET.fromstring(DOWNLOADCONFIG)
					
					# The download config file is formatted different for dynamic vs static. Extract data according to format
					if z.lower() == 'dynamic':
						# TUNNEL 1 INFO
						CGW_OUTSIDE = root[3][0][0][0].text
						LOCAL_INSIDE1 = root[3][0][1][0].text
						REMOTE_OUTSIDE1 = root[3][1][0][0].text
						REMOTE_INSIDE1 = root[3][1][1][0].text
						PSK1 = root[3][2][5].text
						
						# TUNNEL 2 INFO
						LOCAL_INSIDE2 = root[4][0][1][0].text
						REMOTE_OUTSIDE2 = root[4][1][0][0].text
						REMOTE_INSIDE2 = root[4][1][1][0].text
						PSK2 = root[4][2][5].text
						REMOTE_ASN = root[3][1][2][0].text
					else:
						# TUNNEL 1 INFO
						CGW_OUTSIDE = root[4][0][0][0].text
						LOCAL_INSIDE1 = root[4][0][1][0].text
						REMOTE_OUTSIDE1 = root[4][1][0][0].text
						REMOTE_INSIDE1 = root[4][1][1][0].text
						PSK1 = root[4][2][5].text
						
						# TUNNEL 2 INFO
						LOCAL_INSIDE2 = root[5][0][1][0].text
						REMOTE_OUTSIDE2 = root[5][1][0][0].text
						REMOTE_INSIDE2 = root[5][1][1][0].text
						PSK2 = root[5][2][5].text
						REMOTE_ASN = z
					
					def unique_num():
						# Generate a unique mark and vti number that is not already in use
						num = 10
						file = open(SWCONF, 'r').read()
						global VTINUM
						VTINUM = file.count('conn') + 10
						return VTINUM
						
						
					
					# Function to append a new ipsec configuration with appropriate parameters
					def add_config(li,ro,ri,vtinum,psk,num):
						with open(SWCONF,'ab') as f:
							f.write('conn ' + str(x) + '-' + num + '\n')
							f.write('\tkeyexchange=' + str(IKEVERSION) + '\n')
							f.write('\tauto=start\n')
							f.write('\ttype=tunnel\n')
							f.write('\tauthby=secret\n')
							f.write('\tleftid=' + str(CGW_OUTSIDE) + '\n')
							f.write('\tleft=%defaultroute\n')
							f.write('\tright=' + str(ro) + '\n')
							f.write('\tikelifetime='+ str(IKELIFETIME) + '\n')
							f.write('\tlifetime=' + str(ESPLIFETIME) + '\n')
							f.write('\tmargintime=' + str(MARGIN) + '\n')
							f.write('\trekeyfuzz=' + str(FUZZ) + '\n')
							f.write('\tesp=' + str(ESPPARAMETERS) + '\n')
							f.write('\tike=' + str(IKEPARAMETERS) + '\n')
							f.write('\tkeyingtries=%forever\n')
							f.write('\tleftsubnet=0.0.0.0/0\n')
							f.write('\trightsubnet=0.0.0.0/0\n')
							f.write('\tdpddelay=10s\n')
							f.write('\tdpdtimeout=30s\n')
							f.write('\tdpdaction=restart\n')
							f.write('\tmark=' + str(vtinum) + '\n')
							f.write('\tleftupdown="/etc/strongswan/aws.updown -ln vti' + str(vtinum) + ' -ll ' + li + ' -lr ' + ri + ' -m ' + str(vtinum) + ' -t ' + z +' -a ' + REMOTE_ASN + '"\n')
							
						with open(SWSECRET,'ab') as f:
							f.write(ro + ' : PSK "' + psk + '"\n')
							
					# Add first tunnel
					unique_num()
					add_config(LOCAL_INSIDE1,REMOTE_OUTSIDE1,REMOTE_INSIDE1,VTINUM,PSK1,'0')
					
					# Add second tunnel
					unique_num()
					add_config(LOCAL_INSIDE2,REMOTE_OUTSIDE2,REMOTE_INSIDE2,VTINUM,PSK2,'1')
					
					
			except ClientError as e:
				print e
				if e.response['Error']['Code'] == 'InvalidVpnGatewayID.NotFound' or e.response['Error']['Code'] == 'InternalError':
					pass

def delete_vpn(vgw):
		# Get a list of all AWS Regions
		response = client.describe_regions()
		# Delete VPN if user has removed the VGW
		for i in response['Regions']:
			EC2 = boto3.client('ec2',region_name=i['RegionName'])
			
			# Find if we're working with a VGW or TGW
			TGWEXISTS = re.search('tgw-',vgw)
			if TGWEXISTS:
				VPNGWID = 'transit-gateway-id'
			else:
				VPNGWID = 'vpn-gateway-id'
			
			VPNCONNECTIONS = EC2.describe_vpn_connections(
				 Filters=[{'Name': VPNGWID,'Values': [vgw]}]
				 )
			# Get the list of VPNs that were created with by this solution
			with open(TRACKFILE) as t:
				local_list_of_vpns = t.read().split('\n')
				
			# Create a list of VPNs that are currently associated with the VGW in question
			vgw_associated_vpns = []
			for i in VPNCONNECTIONS['VpnConnections']:
				vgw_associated_vpns.append(i['VpnConnectionId'])
				
			# Now see if there are any VPNs that were returned from API match what we have in local list. If a match, delete it
			vpns_to_delete = [x for x in vgw_associated_vpns if x in local_list_of_vpns]
			for vpnid in vpns_to_delete:
				try:
					# Get the CGW id that is associated with the VPN so we can delete it as well
					VPNCONNNECTIONS = EC2.describe_vpn_connections(
						VpnConnectionIds=[vpnid]
					 )
					CGWID=VPNCONNECTIONS['VpnConnections'][0]['CustomerGatewayId']
					
					# Delete both the VPN and CGW
					EC2.delete_vpn_connection(
						VpnConnectionId=vpnid,
					)
					
					# wait for VPN to become completely 'deleted' before trying to delete the CGW
					while True:
						vpnstate = EC2.describe_vpn_connections(
							VpnConnectionIds=[vpnid]
								)
						if vpnstate['VpnConnections'][0]['State'] == 'deleted':				
							EC2.delete_customer_gateway(
								CustomerGatewayId=CGWID
							)
							break
						else:
							sleep(10)
					
					# Remove the PSK config for this VPN peers from the ipsec.secrets file
					DOWNLOADCONFIG = VPNCONNECTIONS['VpnConnections'][0]['CustomerGatewayConfiguration']
					root = ET.fromstring(DOWNLOADCONFIG)
					
					try:
						# Try removing BGP formatted config/VPN if this doesn't work, then try removing static formatted config/VPN
						PEER1 = root[3][1][0][0].text
						PEER2 = root[4][1][0][0].text
						
						remove_stuff(str(PEER1),SWSECRET,0)
						remove_stuff(str(PEER2),SWSECRET,0)
					
					except:
						PEER1 = root[4][1][0][0].text
						PEER2 = root[5][1][0][0].text
						
						remove_stuff(str(PEER1),SWSECRET,0)
						remove_stuff(str(PEER2),SWSECRET,0)
					
					#Finally remove the VPN id from the tracking file since we have deleted it
					remove_stuff(vpnid,TRACKFILE,0)
					
				except Exception as e:
						print e
						pass
		
'''
See if there added, subtracted, or the same VGWs as from the initial launch.
This will help determine if we should add, remove, or leave our strongswan config alone.
'''
for i in VGWS:
	if VGWS.index(i) % 2 != 0:
		# First see if there is already a VPN configuration for the VGW. If so skip that VGW
		if VGWS[VGWS.index(i)-1] + '-0' in open(SWCONF).read():
			print "A VPN is already created for this VGW"
		else:
			# If user decides to create a VPN to this particular VGW as 'dynamic' then specify appropriate parameters for the create VPN function (set StaticRoutesOnly to 'false')
			if i.lower() == 'dynamic':
				make_vpn(VGWS[VGWS.index(i)-1],False,i)

			# else set 'StaticRoutesOnly to 'true'.
			else:
				make_vpn(VGWS[VGWS.index(i)-1],True,i)
		
# Now let's see if the ipsec.conf has any VGWs(VPNs) that the user has removed from the stack		
with open(SWCONF) as s:
	content = s.readlines()
	ACTIVEVGWS = []
	for line in content:
		pattern = re.search('.*([t|v]gw-[a-zA-Z0-9]*)-0', line)
		if pattern:
			print pattern.group(1)
			ACTIVEVGWS.append(pattern.group(1))

VGWS_TO_REMOVE = [x for x in ACTIVEVGWS if x not in VGWS]
for v in VGWS_TO_REMOVE:
	delete_vpn(v)
	remove_stuff('conn ' + v, SWCONF, 43)
	
# Start the strongswan service back up again
call(["service","strongswan","start"])
