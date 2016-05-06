IpManager
=========

Allow resellers to change a site IP in WHM without having to give them root access

Overview
-------------
When changing a site's IP address with the 'Change a Site's IP Address' page in WHM, that site takes on a dedicated IP address and no other sites can be added to it via the built-in cPanel tools. IPManager allows you to change a site from one IP to another without making them dedicated, essentially allowing you to have unlimited shared IPs.

Installation
------------
1. SSH to your cPanel/WHM server and gain root access
2. Run the following command:
        ```wget -N https://github.com/kostonconsulting/IpManager/raw/master/installer/IP-Manager-2.2.sea;chmod +x IP-Manager-2.2.sea;./IP-Manager-2.2.sea```

3. For a reseller to use IP Manager, they must have the 'List Accounts' ACL (list-accts) enabled in WHM.



Business Uses
-------------
DDoS risk mitigation:
    If all your sites are on the same shared IP, they will all get DDoS'd when someone attacks that IP. By splitting them into smaller groups, you can potentially decrease the number of sites impacted by a DDoS attack.

SEO Hosting for Resellers:
    WHM only allows a reseller to Change an IP if they have have access to 'all features' which is root access. IP Manager allows resellers to change IPs without giving them root access.

Warranty
-------------
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Errors
-------------
Errors are logged to /usr/local/cpanel/logs/error_log

Run the following via shell when using the plugin to see any errors:

```tail -f /usr/local/cpanel/logs/error_log```

Debugging
---------
An additional debug mode can be entered by running the following command:

```touch /usr/local/cpanel/whostmgr/docroot/cgi/addons/ipmanager/debug```

Now, you'll see api call output when running:

```tail -f /usr/local/cpanel/logs/error_log```

Make sure to run the following to turn off debug mode as it will print out information about accounts and their sub/parked/addon domains:

```rm /usr/local/cpanel/whostmgr/docroot/cgi/addons/ipmanager/debug```
