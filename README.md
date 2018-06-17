# cgw-testing

## Deployment instructions
1) Download and use the __cgw-deploy.json__ template in Cloudformation to deploy a new CGW
2) Specify the details needed to deploy a new Strongswan CGW, VPC, subnet, VPNs, etc.

For the *VGWs & Routing* parameter provide any VGW that you want to establish a new VPN to. The VGW must be owned by your account, but it does not have to be in the same region as the CF stack. For each VGW you specify, followed it with a comma and the type of routing you want to create the VPN with. 

For BGP VPNs, use the type 'dynamic' and for static VPNs, provide the *remote* VPC CIDR. You can list multiple VGWs in the following format:

<vgw id>,<type>,<vgw id>,<type>
  
 for example:
 
 vgw-xxxxxxxx,dynamic,vgw-yyyyyyyy,192.168.0.0/16
 
 Note: Make sure NOT to use spaces between commas and values. Cloudformation will throw an error if you do
 
 ## Adding or Removing Existing VPNs
 1) Select the cloudformation stack
 2) Select __Actions > Update Stack__
 3) 
