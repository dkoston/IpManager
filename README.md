IpManager
=========

Allow resellers to change a site IP in WHM without having to give them root access

-------------
Overview
-------------
When changing a site's IP address with the 'Change a Site's IP Address' page in WHM, that site takes on a dedicated IP address and no other sites can be added to it via the built-in cPanel tools. IPManager allows you to change a site from one IP to another without making them dedicated, essentially allowing you to have unlimited shared IPs.


-------------
Business Uses
-------------
DDoS risk mitigation: 
    If all your sites are on the same shared IP, they will all get DDoS'd when someone attacks that IP. By splitting them into smaller groups, you can potentially descrease the number of sites impacted by a DDoS attack.

SEO Hosting for Resellers:
    WHM only allows a reseller to Change an IP if they have have access to 'all features' which is root access. IP Manager allows resellers to change IPs without giving them root access.
    
  
