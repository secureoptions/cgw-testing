# cgw-testing

## Deployment instructions
1) <a href="https://console.aws.amazon.com/cloudformation/#/stacks/new?stackName=CloudShroud&templateURL=https://s3.amazonaws.com/secure-options/cgw-tester.json"><img src="https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png"/></a>
2) Specify the details needed to deploy a new Strongswan CGW, VPC, subnet, VPNs, etc.

For the *VGWs & Routing* parameter provide any VGW that you want to establish a new VPN to. The VGW must be owned by your account, but it does not have to be in the same region as the CF stack. For each VGW you specify, followed it with a comma and the type of routing you want to create the VPN with. 

For BGP VPNs, use the type 'dynamic' and for static VPNs, provide the *remote* VPC CIDR. You can list multiple VGWs in the following format:

\<vgw id\>,\<type\>,\<vgw id\>,\<type\>
  
 for example:
 
 vgw-xxxxxxxx,dynamic,vgw-yyyyyyyy,192.168.0.0/16
 
 Note: Make sure NOT to use spaces between commas and values. Cloudformation will throw an error if you do
 
 ## Adding or Removing Existing VPNs
 1) Select the cloudformation stack
 2) Select __Actions > Update Stack__
 3) Choose __Use current template__ and click __Next__
 4) Add or remove the desired VGWs(remember to remove its routing type as well) and click __Next__
 5) Scroll to the bottom of the next page and click __Next__
 6) Check the box that says *I acknowledge that AWS CloudFormation might create IAM resources.*
 7) click __Update__
 
 It can take 2 or 3 minutes for updates to take effect
