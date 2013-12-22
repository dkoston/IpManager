#!/usr/local/cpanel/3rdparty/bin/perl
#WHMADDON:ipmanager:IP Manager
# IP Manager - Dave Koston - Koston Consulting - All Rights Reserved
#
# This code is subject to the GNU GPL: http://www.gnu.org/licenses/gpl.html
# Version: 1.5

BEGIN { unshift @INC, '/usr/local/cpanel'; }
use strict;
use warnings;
use CGI                            ();
use Cpanel                         ();
use Cpanel::AcctUtils::DomainOwner ();
use Cpanel::AcctUtils::Owner       ();
use Cpanel::Config::CpUserGuard    ();
use Cpanel::Config::LoadCpUserFile ();
use Cpanel::Config::userdata       ();
use Cpanel::DIp                    ();
use Cpanel::DIp::MainIP            ();
use Cpanel::Logger                 ();
use Cpanel::MagicRevision          ();
use Cpanel::PublicAPI              ();
use Fcntl                          ();
use IO::Handle                     ();
use IPC::Open3                     ();
use JSON                           ();
use MIME::Base64                   ();
use Template                       ();

Cpanel::initcp();

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
    security_token          => $ENV{cp_security_token},
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

my $access_Hash = load_accesshash();
my $cgi         = CGI->new();
print $cgi->header();
my $action   = _sanitize( $cgi->param('action') );
my $domain   = _sanitize( $cgi->param('hostname') );
my $user     = _sanitize( $cgi->param('user') );
my $oldip    = _sanitize( $cgi->param('oldip') );
my $customip = _sanitize( $cgi->param('customip') );
my $logger   = Cpanel::Logger->new();

my $ip_aliases = is_nat() ? get_ip_aliases() : {};

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

    if ( is_nat() ) {
        $vars->{aliasip} = $ip_aliases->{ $vars->{oldip} };
    }

    my $subdomains_obj = get_subdomains($user);
    if ( $subdomains_obj->{status} ) {
        $vars->{subdomains} = $subdomains_obj->{subdomains};
    }
    my $parkeddomains_obj = get_parked_domains($user);
    if ( $parkeddomains_obj->{status} ) {
        $vars->{parked_domains} = $parkeddomains_obj->{parked_domains};
    }
    my $available_ips = get_reseller_ip_list( $ENV{'REMOTE_USER'}, $ip_aliases );

    my @domains_per_ip = get_domains_by_ip();

    foreach my $ip (@domains_per_ip) {
        my $domain_ip = $ip->{ip};
        my $domains   = $ip->{domains};
        my @domains   = @{$domains};
        my $ip_match  = 0;

        #See if the IP is on the list of available IPs
        foreach my $key ( keys %{$available_ips} ) {
            if ( $key eq $domain_ip ) {
                $ip_match = 1;

                #The IP is in our list of available IPs, test the domains on it to see if this user owns at least one
                my $counter = 0;
                foreach my $domain (@domains) {
                    if ( $ENV{'REMOTE_USER'} eq get_reseller_by_domain($domain) ) {
                        $counter++;
                    }
                }
                if ( $counter == 1 ) {
                    $available_ips->{$key} .= '-GREY';
                }
                elsif ( $counter >= 2 ) {
                    $available_ips->{$key} .= '-RED';
                }

            }
        }

    }
    $vars->{available_ips} = $available_ips;
    build_template( 'chooseip.tt', $vars );
}
elsif ( $action eq 'changeip' ) {
    $vars->{customip} = $customip;
    $vars->{domain}   = $domain;
    $vars->{oldip}    = $oldip;
    $vars->{user}     = $user;

    if ( is_nat() ) {
        $vars->{aliasip} = $ip_aliases->{ $vars->{customip} };
    }

    my $subdomains_obj = get_subdomains($user);
    if ( $subdomains_obj->{status} ) {
        $vars->{subdomains} = $subdomains_obj->{subdomains};
    }
    my $parkeddomains_obj = get_parked_domains($user);
    if ( $parkeddomains_obj->{status} ) {
        $vars->{parked_domains} = $parkeddomains_obj->{parked_domains};
    }

    #Change IPs
    my $changeip_obj = change_site_ip( $user, $domain, $customip, $vars->{subdomains}, $vars->{parked_domains} );
    $vars->{status}    = $changeip_obj->{status};
    $vars->{statusmsg} = $changeip_obj->{statusmsg};

    #Reload DNS Zones
    run_forked('/scripts/restartsrv_bind');

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
      || $logger->die( 'Template Error 3 - ' . $template->error() );
}

sub get_reseller_by_domain {
    my ($domain)    = @_;
    my $domain_user = Cpanel::AcctUtils::DomainOwner::getdomainowner($domain);
    my $reseller    = Cpanel::AcctUtils::Owner::getowner($domain_user);
    return $reseller;
}

sub get_reseller_ip_list {
    my ( $reseller, $ip_aliases ) = @_;

    my $dips_file = '/var/cpanel/dips/' . $reseller;
    my @reseller_ips;
    my %ip_list;

    if ( -e $dips_file ) {
        if ( sysopen( my $fh, $dips_file, &Fcntl::O_RDONLY ) ) {
            flock( $fh, &Fcntl::LOCK_EX );
            {
                while ( my $line = <$fh> ) {
                    $ip_list{$line} = $line;
                }
            }
            flock( $fh, &Fcntl::LOCK_UN );
            close($fh);

            my $main_ip = Cpanel::DIp::getmainip();
            if ( $ip_list{$main_ip} ) {
                $ip_list{$main_ip} = $main_ip . ' (Main Shared IP Address)';
            }
        }
        else {
            return 0;
            print STDERR "Failed to open file";
        }
    }
    else {
        @reseller_ips = Cpanel::DIp::get_available_ips($reseller);
        foreach my $ip (@reseller_ips) {
            $ip_list{$ip} = $ip;
        }
        if ( $reseller eq 'root' ) {
            my $main_ip = Cpanel::DIp::getmainip();
            $ip_list{$main_ip} = $main_ip . ' (Main Shared IP Address)';
        }
    }

    #set display values for any NAT'd IPs
    if ($ip_aliases) {
        foreach my $ip ( keys %ip_list ) {
            if ( $ip_aliases->{$ip} ) {
                $ip_list{$ip} = $ip_aliases->{$ip};
            }
        }
    }

    return \%ip_list;
}

sub gather_list_of_accounts {
    my $return_vars = { status => 0, accounts => undef };
    my $api_params = {};

    my $pub_api = Cpanel::PublicAPI->new(
        {
            user       => $ENV{'REMOTE_USER'},
            accesshash => $access_Hash
        }
    );

    unless ( $ENV{'REMOTE_USER'} eq 'root' ) {
        $api_params->{searchtype} = 'owner';
        $api_params->{search}     = $ENV{'REMOTE_USER'};
    }

    my $pub_api_response = $pub_api->whm_api( 'listaccts', $api_params, 'json' );
    my $json_obj         = JSON->new();
    my $json             = $json_obj->allow_nonref->utf8->relaxed->decode($pub_api_response);
    my $accts_ref        = $json->{acct};

    if ( $json->{status} eq '1' ) {
        #sort accounts alphabetically
        my @sorted_accounts = sort { $a->{domain} cmp $b->{domain} } @{$accts_ref};

        $return_vars->{status}   = 1;
        $return_vars->{accounts} = \@sorted_accounts;
    }
    else {
        $logger->warn( 'API Error 1 - gather_list_of_accounts() - ' . $json->{cpanelresult}->{error} );
    }

    return $return_vars;
}

sub get_subdomains {
    my ($user) = @_;
    my $return_vars = { status => 0, subdomains => undef };

    my $pub_api = Cpanel::PublicAPI->new(
        {
            user       => $ENV{'REMOTE_USER'},
            accesshash => $access_Hash
        }
    );

    my $api_params = {
        'cpanel_jsonapi_user'       => $user,
        'cpanel_jsonapi_module'     => 'SubDomain',
        'cpanel_jsonapi_func'       => 'listsubdomains',
        'cpanel_jsonapi_apiversion' => '2',
    };

    my $pub_api_response = $pub_api->whm_api( 'cpanel', $api_params, 'json' );
    my $json_obj         = JSON->new();
    my $json             = $json_obj->allow_nonref->utf8->relaxed->decode($pub_api_response);

    if ( $json->{cpanelresult}->{event}->{result} == '1' ) {
        $return_vars->{status}     = 1;
        $return_vars->{subdomains} = $json->{cpanelresult}->{data};
    }
    else {
        $logger->warn( 'API Error 1 - get_subdomains() - ' . $json->{cpanelresult}->{error} );
    }

    return $return_vars;
}

sub get_parked_domains {
    my ($user) = @_;
    my $return_vars = { status => 0, parked_domains => undef };

    my $pub_api = Cpanel::PublicAPI->new(
        {
            user       => $ENV{'REMOTE_USER'},
            accesshash => $access_Hash
        }
    );

    my $api_params = {
        'cpanel_jsonapi_user'       => $user,
        'cpanel_jsonapi_module'     => 'Park',
        'cpanel_jsonapi_func'       => 'listparkeddomains',
        'cpanel_jsonapi_apiversion' => '2',
    };

    my $pub_api_response = $pub_api->whm_api( 'cpanel', $api_params, 'json' );
    my $json_obj         = JSON->new();
    my $json             = $json_obj->allow_nonref->utf8->relaxed->decode($pub_api_response);

    if ( $json->{cpanelresult}->{event}->{result} == '1' ) {
        $return_vars->{status}         = 1;
        $return_vars->{parked_domains} = $json->{cpanelresult}->{data};
    }
    else {
        $logger->warn( 'API Error 1 - get_parked_domains() - ' . $json->{cpanelresult}->{error} );
    }

    return $return_vars;
}

####Need to do this for all addon, parked and subdomains as well
sub change_site_ip {
    my $return_vars = { status => 0, statusmsg => undef };
    my ( $user, $domain, $newip, $subdomains_ref, $parked_domains_ref ) = @_;

    my $cpuser_guard = Cpanel::Config::CpUserGuard->new($user);

    unless ($cpuser_guard) {
        $logger->die( 'Unable to open cPanel user file for: ' . $user );
    }

    my $oldip = $cpuser_guard->{'data'}->{'IP'};
    $cpuser_guard->{'data'}->{'IP'} = $newip;
    $cpuser_guard->save();

    #Change main IP
    change_ip_in_files( $user, $domain, $oldip, $newip );

    #Change parked domain IPs
    foreach my $parked_domain ( @{$parked_domains_ref} ) {
        change_ip_in_files( $user, $parked_domain->{domain}, $oldip, $newip );
    }

    #Change sub domain IPs
    foreach my $sub_domain ( @{$subdomains_ref} ) {
        change_ip_in_files( $user, $sub_domain->{domain}, $oldip, $newip );
    }

    #Update UserDomains
    run_forked('/scripts/updateuserdomains --force');

    #Rebuild httpd.conf
    run_forked('/scripts/rebuildhttpdconf --force');

    #restart apache
    run_forked('/usr/local/apache/bin/apachectl restart');

    $return_vars->{status} = 1;

    return $return_vars;
}

sub change_ip_in_files {
    my ( $user, $domain, $old_ip, $new_ip ) = @_;

    #Replace IP in /var/cpanel/userdata/$user/$domain
    my $cp_userdata = Cpanel::Config::userdata::update_domain_ip_data( $user, $domain, $new_ip );

    #Replace IP in DNS Zone
    run_forked("sed -i 's/$old_ip/$new_ip/g' /var/named/$domain.db && /scripts/dnscluster synczone $domain");
}

sub get_ip_aliases {
    my %ip_aliases   = {};
    my $aliases_file = '/var/cpanel/cpnat';

    if ( sysopen( my $fh, $aliases_file, &Fcntl::O_RDONLY ) ) {
        flock( $fh, &Fcntl::LOCK_EX );
        {
            while ( my $line = <$fh> ) {
                my ( $private_ip, $public_ip ) = split( ' ', $line );
                $ip_aliases{$private_ip} = $public_ip;
            }
        }
        flock( $fh, &Fcntl::LOCK_UN );
        close($fh);
        return \%ip_aliases;
    }
    else {
        return 0;
        print STDERR "Failed to open file";
    }

}

sub get_domains_by_ip {
    my @ips_and_their_domains;
    my @result;

    my $wh  = IO::Handle->new();
    my $rh  = IO::Handle->new();
    my $eh  = IO::Handle->new();
    my $pid = IPC::Open3::open3( $wh, $rh, $eh, '/scripts/ipusage' );
    @result = <$rh>;
    waitpid( $pid, 0 );

    foreach my $ip_usage_line (@result) {
        my @line_contents = split( ' ', $ip_usage_line );
        my $length = @line_contents;

        if ( $length > 2 ) {
            my $domain_string = $line_contents[2];
            my @domains;

            $domain_string = $domain_string =~ /^(.*)(\])$/ ? $1 : $domain_string;
            if ( $domain_string =~ /,/ ) {
                @domains = split( ',', $domain_string );
            }
            else {
                $domains[0] = $domain_string;
            }

            my $ip_and_domain_list = {
                ip      => $line_contents[0],
                domains => \@domains,
            };

            push( @ips_and_their_domains, $ip_and_domain_list );
        }
    }
    return @ips_and_their_domains;
}

sub load_accesshash {

    #Ensure access hash exists
    my ( $access_hash, $hash_file );

    if ( !$ENV{'REMOTE_USER'} || $ENV{'REMOTE_USER'} eq 'root' ) {
        $hash_file = "/root/.accesshash";
    }
    else {
        $hash_file = $ENV{'HOME'} . "/.accesshash";
    }
    unless ( -f $hash_file ) {
        run_forked('/usr/local/cpanel/whostmgr/bin/whostmgr setrhash');
    }

    #get accesshash
    if ( sysopen( my $hash_fh, $hash_file, &Fcntl::O_RDONLY | &Fcntl::O_NOFOLLOW ) ) {
        flock( $hash_fh, &Fcntl::LOCK_EX );
        {
            $access_hash = do { local $/; <$hash_fh>; };
            $access_hash =~ s/\n//g;
        }
        flock( $hash_fh, &Fcntl::LOCK_UN );
        close($hash_fh);
    }
    else {
        $logger->die( "Cannot open access hash: " . $hash_file );
    }

    return $access_hash;
}

sub is_nat {
    return -s '/var/cpanel/cpnat' ? 1 : 0;
}

sub run_forked {

    #No return is provided from this sub
    my ($command) = @_;

    my $wh = IO::Handle->new();
    my $rh = IO::Handle->new();
    my $eh = IO::Handle->new();

    my $pid = IPC::Open3::open3( $wh, $rh, $eh, $command );
    waitpid( 0, $pid );
}

sub _sanitize {
    my $text = shift;
    return '' if !$text;
    $text =~ s/([;<>\*\|`&\$!?#\(\)\[\]\{\}:'"\\])/\\$1/g;
    return $text;
}
