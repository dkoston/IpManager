#!/usr/bin/perl -w
#WHMADDON:ipmanager:IP Manager
# IP Manager - Dave Koston - Koston Consulting - All Rights Reserved
#
# This code is subject to the GNU GPL: http://www.gnu.org/licenses/gpl.html
# Version: 1.2

BEGIN { unshift @INC, '/usr/local/cpanel'; }
use strict;
use CGI                            ();
use Cpanel::Locale                 ();
use Cpanel                         ();
use Cpanel::MagicRevision          ();
use Cpanel::Config::LoadCpUserFile ();
use Cpanel::Config::SaveCpUserFile ();
use Cpanel::DIp                    ();
use Cpanel::DIp::MainIP            ();
use Cpanel::AcctUtils::DomainOwner ();
use Cpanel::Config::userdata       ();
use Cpanel::AcctUtils::Owner       ();
use Fcntl                          ();
use HTTP::Request                  ();
use IO::Handle                     ();
use IPC::Open3                     ();
use JSON                           ();
use LWP::UserAgent                 ();
use MIME::Base64                   ();
use Template                       ();

Cpanel::initcp();

my $cpanel_data = {
    SECURITY_TOKEN => $ENV{cp_security_token},
    WHM_USER       => $ENV{REMOTE_USER},
    WHM_PASS       => $ENV{REMOTE_PASSWORD},
    AUTHORIZATION  => 'Basic ' . MIME::Base64::encode_base64( $ENV{REMOTE_USER} . ':' . $ENV{REMOTE_PASSWORD} ),
    LOCALE         => Cpanel::Locale->get_handle(),
};

my $vars = {
    status                  => undef,
    statusmsg               => undef,
    accts                   => undef,
    oldip                   => undef,
    user                    => undef,
    domain                  => undef,
    subdomains              => undef,
    parked_domains          => undef,
    available_ips           => undef,
    shared_ips              => undef,
    custom_ip               => undef,
    security_token          => $cpanel_data->{SECURITY_TOKEN},
    favicon_mrlink          => Cpanel::MagicRevision::calculate_magic_url('../favicon.ico'),
    ie7_css_mrlink          => Cpanel::MagicRevision::calculate_magic_url('../themes/x/css/ie7.css'),
    ie6_css_mrlink          => Cpanel::MagicRevision::calculate_magic_url('../themes/x/css/ie6.css'),
    combopt_css_mrlink      => Cpanel::MagicRevision::calculate_magic_url('../combined_optimized.css'),
    styleopt_css_mrlink     => Cpanel::MagicRevision::calculate_magic_url('../themes/x/style_optimized.css'),
    utilcontainer_js_mrlink => Cpanel::MagicRevision::calculate_magic_url('../../yui-gen/utilities_container/utilities_container.js'),
    cpallmin_js_mrlink      => Cpanel::MagicRevision::calculate_magic_url('../../cjt/cpanel-all-min.js'),
    chngsiteip_jpeg_mrlink  => Cpanel::MagicRevision::calculate_magic_url('../themes/x/icons/change_site_ipaddress.gif'),
    autocomplete_css_mrlink => Cpanel::MagicRevision::calculate_magic_url('../../yui/assets/skins/sam/autocomplete.css'),
    pkghover_js_mrlink      => Cpanel::MagicRevision::calculate_magic_url('../js/pkg_hover.js'),
    datasource_js_mrlink    => Cpanel::MagicRevision::calculate_magic_url('../../yui/datasource/datasource.js'),
    autocomplete_js_mrlink  => Cpanel::MagicRevision::calculate_magic_url('../../yui/autocomplete/autocomplete.js'),
};

my $cgi = CGI->new();
print $cgi->header();
my $action   = _sanitize( $cgi->param('action') );
my $domain   = _sanitize( $cgi->param('hostname') );
my $user     = _sanitize( $cgi->param('user') );
my $oldip    = _sanitize( $cgi->param('oldip') );
my $customip = _sanitize( $cgi->param('customip') );

if ( $action eq '' || $action eq 'acctlist' ) {
    my $accounts_obj = gather_list_of_accounts();
    if ( $accounts_obj->{status} ) {
        $vars->{accts}  = $accounts_obj->{accounts};
        $vars->{status} = 1;
    }
    else {
        $vars->{status} = 0;
    }
    build_template( 'choosesite.tt', $vars );
}
elsif ( $action eq 'selectip' ) {
    $vars->{user}   = $user;
    $vars->{domain} = $domain;
    my $cp_userref = Cpanel::Config::LoadCpUserFile::loadcpuserfile($user);
    $vars->{oldip} = $cp_userref->{IP};
    my $subdomains_obj = getSubdomains($user);
    if ( $subdomains_obj->{status} ) {
        $vars->{subdomains} = $subdomains_obj->{subdomains};
    }
    my $parkeddomains_obj = getParkedDomains($user);
    if ( $parkeddomains_obj->{status} ) {
        $vars->{parked_domains} = $parkeddomains_obj->{parked_domains};
    }
    my @available_ips = get_reseller_ip_list( $cpanel_data->{WHM_USER} );

    my @domains_per_ip = getDomainsByIp();

    foreach my $ip (@domains_per_ip) {
        my $domain_ip = $ip->{ip};
        my $domains   = $ip->{domains};
        my @domains   = @{$domains};
        my $ip_match  = 0;

        #See if the IP is on the list of available IPs
        foreach my $available_ip ( 0 .. $#available_ips ) {
            if ( $available_ips[$available_ip] eq $domain_ip ) {
                $ip_match = 1;

                #The IP is in our list of available IPs, test the domains on it to see if this user owns at least one
                my $counter = 0;
                foreach my $domain (@domains) {
                    if ( $ENV{'REMOTE_USER'} eq get_reseller_by_domain($domain) ) {
                        $counter++;
                    }
                }
                if ( $counter == 1 ) {
                    $available_ips[$available_ip] .= '-GREY';
                }
                elsif ( $counter >= 2 ) {
                    $available_ips[$available_ip] .= '-RED';
                }
            }
        }
    }
    $vars->{available_ips} = \@available_ips;
    build_template( 'chooseip.tt', $vars );
}
elsif ( $action eq 'changeip' ) {
    $vars->{user}   = $user;
    $vars->{domain} = $domain;
    my $cp_userref = Cpanel::Config::LoadCpUserFile::loadcpuserfile($user);
    $vars->{oldip} = $oldip;
    my $subdomains_obj = getSubdomains($user);
    if ( $subdomains_obj->{status} ) {
        $vars->{subdomains} = $subdomains_obj->{subdomains};
    }
    my $parkeddomains_obj = getParkedDomains($user);
    if ( $parkeddomains_obj->{status} ) {
        $vars->{parked_domains} = $parkeddomains_obj->{parked_domains};
    }

    #Change IPs
    my $changeip_obj = changeSiteIp( $user, $domain, $customip, $vars->{subdomains}, $vars->{parked_domains} );

    my $rh = IO::Handle->new();
    my $wh = IO::Handle->new();
    my $eh = IO::Handle->new();

    #Reload DNS Zones
    my $resdns_pid = IPC::Open3::open3( $wh, $rh, $eh, '/scripts/restartsrv_bind' );
    waitpid( 0, $resdns_pid );

    $vars->{status}    = $changeip_obj->{status};
    $vars->{statusmsg} = $changeip_obj->{statusmsg};
    $vars->{user}      = $user;
    $vars->{customip}  = $customip;
    $vars->{oldip}     = $oldip;
    build_template( 'ipchanged.tt', $vars );
}

sub build_template {
    my ( $template_name, $vars ) = @_;

    my $template = Template->new(
        {
            INCLUDE_PATH => '/usr/local/cpanel/whostmgr/docroot/cgi/ipmanager/',
        }
    );
    $template->process( $template_name, $vars )
      || die $cpanel_data->{LOCALE}->maketext('Template Error') . '3 - ' . $template->error();
}

sub get_reseller_by_domain {
    my $domain      = shift;
    my $domain_user = Cpanel::AcctUtils::DomainOwner::getdomainowner($domain);
    my $reseller    = Cpanel::AcctUtils::Owner::getowner($domain_user);
    return $reseller;
}

sub get_reseller_ip_list {
    my $reseller  = shift;
    my $dips_file = '/var/cpanel/dips/' . $reseller;
    my @reseller_ips;
    if ( -e $dips_file ) {
        if ( sysopen( my $fh, $dips_file, &Fcntl::O_RDONLY ) ) {
            flock( $fh, &Fcntl::LOCK_EX );
            {
                local $/;    #read until forever -- $/ is usually \n
                @reseller_ips = split( ' ', readline($fh) );
                my $length = @reseller_ips;
                for ( my $i = 0; $i < $length; $i++ ) {
                    if ( $reseller_ips[$i] eq Cpanel::DIp::getmainip() ) {
                        $reseller_ips[$i] .= ' (Main Shared IP Address)';
                    }
                }
            }
            flock( $fh, &Fcntl::LOCK_UN );
        }
        else {
            return 0;
            print STDERR "Failed to open file";
        }
    }
    else {
        @reseller_ips = Cpanel::DIp::get_available_ips($reseller);
        if ( $reseller eq 'root' ) {
            push( @reseller_ips, Cpanel::DIp::MainIP::getmainip() );
        }
    }

    return @reseller_ips;
}

sub gather_list_of_accounts {
    my $return_vars = { status => 0, accounts => undef };

    my $url       = 'https://127.0.0.1:2087' . $cpanel_data->{SECURITY_TOKEN} . '/json-api/listaccts';
    my $useragent = LWP::UserAgent->new();
    $useragent->ssl_opts( verify_hostname => 0 );
    my $request = HTTP::Request->new( 'GET' => $url );
    $request->authorization_basic( $ENV{REMOTE_USER}, $ENV{REMOTE_PASSWORD} );

    my $response = $useragent->request($request);

    if ( $response->is_success() ) {
        my $json_obj = JSON->new();
        my $json     = $json_obj->allow_nonref->utf8->relaxed->decode( $response->content() );
        if ( $json->{status} == '1' ) {
            $return_vars->{status}   = 1;
            $return_vars->{accounts} = $json->{acct};

            #sort accounts alphabetically

        }
        else {
            print STDERR $cpanel_data->{LOCALE}->maketext('API Error') . '1 - ' . $response->content();
        }
    }
    else {
        print STDERR $cpanel_data->{LOCALE}->maketext('API Error') . '2 - ' . $response->content();
    }

    return $return_vars;
}

sub getSubdomains {
    my $user = shift;
    my $return_vars = { status => 0, subdomains => undef };

    my $url       = 'https://127.0.0.1:2087' . $cpanel_data->{SECURITY_TOKEN} . '/json-api/cpanel?user=' . $user . '&cpanel_jsonapi_module=SubDomain&cpanel_jsonapi_func=listsubdomains&cpanel_jsonapi_apiversion=2';
    my $useragent = LWP::UserAgent->new();
    $useragent->ssl_opts( verify_hostname => 0 );
    my $request = HTTP::Request->new( 'GET' => $url );
    $request->authorization_basic( $ENV{REMOTE_USER}, $ENV{REMOTE_PASSWORD} );

    my $response = $useragent->request($request);

    if ( $response->is_success() ) {
        my $json_obj = JSON->new();
        my $json     = $json_obj->allow_nonref->utf8->relaxed->decode( $response->content() );
        if ( $json->{cpanelresult}->{event}->{result} == '1' ) {
            $return_vars->{status}     = 1;
            $return_vars->{subdomains} = $json->{cpanelresult}->{data};
        }
        else {
            print STDERR $cpanel_data->{LOCALE}->maketext('API Error') . '1 - ' . $response->content();
        }
    }
    else {
        print STDERR $cpanel_data->{LOCALE}->maketext('API Error') . '2 - ' . $response->content();
    }

    return $return_vars;
}

sub getParkedDomains {
    my $user = shift;
    my $return_vars = { status => 0, parked_domains => undef };

    my $url = 'https://127.0.0.1:2087' . $cpanel_data->{SECURITY_TOKEN} . '/json-api/cpanel?user=' . $user . '&cpanel_jsonapi_module=Park&cpanel_jsonapi_func=listparkeddomains&cpanel_jsonapi_apiversion=2';

    my $useragent = LWP::UserAgent->new();
    $useragent->ssl_opts( verify_hostname => 0 );
    my $request = HTTP::Request->new( 'GET' => $url );
    $request->authorization_basic( $ENV{REMOTE_USER}, $ENV{REMOTE_PASSWORD} );

    my $response = $useragent->request($request);

    if ( $response->is_success() ) {
        my $json_obj = JSON->new();
        my $json     = $json_obj->allow_nonref->utf8->relaxed->decode( $response->content() );
        if ( $json->{cpanelresult}->{event}->{result} == '1' ) {
            $return_vars->{status}         = 1;
            $return_vars->{parked_domains} = $json->{cpanelresult}->{data};
        }
        else {
            print STDERR $cpanel_data->{LOCALE}->maketext('API Error') . '1 - ' . $response->content();
        }
    }
    else {
        print STDERR $cpanel_data->{LOCALE}->maketext('API Error') . '2 - ' . $response->content();
    }

    return $return_vars;
}

####Need to do this for all addon, parked and subdomains as well
sub changeSiteIp {
    my $return_vars = { status => 0, statusmsg => undef };
    my ( $user, $domain, $newip, $subdomainsRef, $parkeddomainsRef ) = @_;

    my $cp_userref = Cpanel::Config::LoadCpUserFile::loadcpuserfile($user);
    my $oldip      = $cp_userref->{IP};

    #Replace IP in /var/cpanel/users/$user
    $cp_userref->{IP} = $newip;
    Cpanel::Config::SaveCpUserFile::savecpuserfile( $user, $cp_userref );

    #Change main IP
    changeIPInFiles( $user, $domain, $oldip, $newip );

    #Change parked domain IPs
    foreach my $parked_domain ( @{$parkeddomainsRef} ) {
        changeIPInFiles( $user, $parked_domain->{domain}, $oldip, $newip );
    }

    #Change sub domain IPs
    foreach my $sub_domain ( @{$subdomainsRef} ) {
        changeIPInFiles( $user, $sub_domain->{domain}, $oldip, $newip );
    }

    my $wh2 = IO::Handle->new();
    my $wh3 = IO::Handle->new();
    my $wh4 = IO::Handle->new();
    my $rh2 = IO::Handle->new();
    my $rh3 = IO::Handle->new();
    my $rh4 = IO::Handle->new();
    my $eh2 = IO::Handle->new();
    my $eh3 = IO::Handle->new();
    my $eh4 = IO::Handle->new();

    #Update UserDomains
    my $pid2 = IPC::Open3::open3( $wh2, $rh2, $eh2, '/scripts/updateuserdomains --force' );
    waitpid( 0, $pid2 );

    #Rebuild httpd.conf
    my $pid3 = IPC::Open3::open3( $wh3, $rh3, $eh3, '/scripts/rebuildhttpdconf --force' );
    waitpid( 0, $pid3 );

    #restart apache
    my $pid4 = IPC::Open3::open3( $wh4, $rh4, $eh4, '/usr/local/apache/bin/apachectl restart' );
    waitpid( 0, $pid4 );

    $return_vars->{status} = 1;

    return $return_vars;
}

sub changeIPInFiles {
    my ( $user, $domain, $oldip, $newip ) = @_;

    #Replace IP in /var/cpanel/userdata/$user/$domain
    my $cp_userdata = Cpanel::Config::userdata::update_domain_ip_data( $user, $domain, $newip );

    my $wh = IO::Handle->new();
    my $rh = IO::Handle->new();
    my $eh = IO::Handle->new();

    #Replace IP in DNS Zone
    my $pid = IPC::Open3::open3( $wh, $rh, $eh, "sed -i 's/$oldip/$newip/g' /var/named/$domain.db" );
    waitpid( 0, $pid );
}

sub getDomainsByIp {
    my @ips_and_their_domains;
    my @result;
    my $pid = IPC::Open3::open3( my $wh, my $rh, my $eh, '/scripts/ipusage' );
    @result = <$rh>;
    waitpid( $pid, 0 );
    foreach my $ipLine (@result) {
        my @info = split( ' ', $ipLine );
        my $length = @info;

        if ( $length > 2 ) {
            my $domainstring = $info[2];
            my @domains;

            $domainstring = $domainstring =~ /^(.*)(\])$/ ? $1 : $domainstring;
            if ( $domainstring =~ /,/ ) {
                @domains = split( ',', $domainstring );
            }
            else {
                $domains[0] = $domainstring;
            }

            my $ipAndDomains = {
                ip      => $info[0],
                domains => \@domains,
            };

            push( @ips_and_their_domains, $ipAndDomains );
        }
    }
    return @ips_and_their_domains;
}

sub _sanitize {
    my $text = shift;
    return '' if !$text;
    $text =~ s/([;<>\*\|`&\$!?#\(\)\[\]\{\}:'"\\])/\\$1/g;
    return $text;
}
