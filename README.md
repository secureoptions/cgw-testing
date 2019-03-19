# cgw-testing

## What this tool does
1) Creates a new VPC 
2) Creates single public subnet in the new VPC
3) Creates a Customer Gateway (Strongswan) in the public subnet
4) A script on the Customer Gateway will automatically create VPN tunnels to the VGW id(s) and TGW id(s) that the user specifies in Cloudformation

__Please allow ~10 minutes *after* Cloudformation stack has to deployed for VPNs to be created.__


## Deployment instructions
1) <a href="https://console.aws.amazon.com/cloudformation/#/stacks/new?stackName=CGW-Testing&templateURL=https://s3.amazonaws.com/secure-options/cgw-tester.json"><img src="https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png"/></a>
2) Specify the details needed to deploy a new Strongswan CGW, VPC, subnet, VPNs, etc.

For the *VGWs & Routing* parameter provide any VGW or TGW that you want to establish a new VPN to. The gateway must be owned by your account, but it does not have to be in the same region as the CF stack. For each gateway ID you specify, followed it with a comma and the type of routing you want to create the VPN with. 

For BGP VPNs, use the type 'dynamic' and for static VPNs, provide the *remote* VPC CIDR or network. You can list multiple TGWs/VGWs in the following format:

\<gw id\>,\<type\>,\<gw id\>,\<type\>
  
 for example:
 
 tgw-xxxxxxxx,dynamic, vgw-yyyyyyyy,192.168.0.0/16, tgw-zzzzzzzz,dynamic
 
 ## Adding or Removing Existing VPNs
 1) Select the cloudformation stack
 2) Select __Actions > Update Stack__
 3) Choose __Use current template__ and click __Next__
 4) Add or remove the desired VGWs(remember to remove its routing type as well) and click __Next__
 5) Scroll to the bottom of the next page and click __Next__
 6) Check the box that says *I acknowledge that AWS CloudFormation might create IAM resources.*
 7) click __Update__
 
 You can also update any IPSEC parameters through Cloudformation, but you cannot change the VPN type (ie. Dynamic vs. Static) or the Strongswan version that was installed at deployment. If you wish to create a different VPN type, then you must:
 1) Remove the '\<gw id\>, \<type\>' and update the stack.
 2) After the update has successfully finished, and you see the previous VPN deleted, you may re-add the VPN with the desired type in a second stack update.
  
 It can take 2 or 3 minutes for updates to take effect
