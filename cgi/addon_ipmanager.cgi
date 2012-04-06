#!/usr/bin/perl -w
#WHMADDON:ipmanager:IP Manager <span class=yui-tt>Change Site's IP Address</span>
# IP Manager - Dave Koston - Koston Consulting - All Rights Reserved
#
# This code is subject to the GNU GPL: http://www.gnu.org/licenses/gpl.html
#
# version 0.8

BEGIN { unshift @INC, '/usr/local/cpanel'; }

use strict;

use CGI                            ();
use Cpanel::Locale                 ();
use Cpanel                         ();
use Cpanel::MagicRevision          ();
use Cpanel::UserDomainIp           ();
use Cpanel::Config::LoadCpUserFile ();
use Cpanel::XML                    ();
use Cpanel::DIp                    ();
use Cpanel::DIp::MainIP            ();
use Fcntl                          ();
use HTTP::Request                  ();
use JSON                           ();
use LWP::UserAgent                 ();
use MIME::Base64                   ();
use Template                       ();
use XML::Simple                    ();

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
    my $available_ips = get_reseller_ip_list( $cpanel_data->{WHM_USER} );
    $vars->{available_ips} = $available_ips;
    build_template( 'chooseip.tt', $vars );
}
elsif ( $action eq 'changeip' ) {
    my $changeip_obj = changeSiteIp( $user, $customip );
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

            return \@reseller_ips;
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
        return \@reseller_ips;
    }
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

sub changeSiteIp {
    my $return_vars = { status => 0, statusmsg => undef };
    my ( $user, $newip ) = @_;

    my $url       = 'https://127.0.0.1:2087' . $cpanel_data->{SECURITY_TOKEN} . '/xml-api/cpanel?user=' . $user . '&cpanel_xmlapi_module=Ipmanager&cpanel_xmlapi_func=changesiteip&cpanel_xmlapi_apiversion=2&theuser=' . $user . '&newip=' . $newip . '&security_token=' . $cpanel_data->{SECURITY_TOKEN};
    my $useragent = LWP::UserAgent->new();
    $useragent->ssl_opts( verify_hostname => 0 );
    my $request = HTTP::Request->new( 'GET' => $url );
    $request->authorization_basic( $ENV{REMOTE_USER}, $ENV{REMOTE_PASSWORD} );

    my $response = $useragent->request($request);

    if ( $response->is_success() ) {
        my $parsed_xml = XML::Simple::XMLin( $response->content() );
        $return_vars->{status}    = $parsed_xml->{event}->{result};
        $return_vars->{statusmsg} = $parsed_xml->{error};
    }
    else {
        print STDERR $cpanel_data->{LOCALE}->maketext('API Error') . '2 - ' . $response->content();
    }

    return $return_vars;
}

sub _sanitize {
    my $text = shift;
    return '' if !$text;
    $text =~ s/([;<>\*\|`&\$!?#\(\)\[\]\{\}:'"\\])/\\$1/g;
    return $text;
}
