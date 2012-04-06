package Cpanel::Ipmanager;

use Cpanel::AdminBin ();

sub api2_changesiteip {
    my %OPTS = @_;
    my $result = Cpanel::AdminBin::adminrun( 'ipmanager', 'CHANGEIP', $OPTS{'theuser'}, $OPTS{'newip'}, $OPTS{'security_token'} ) || die 'not working';
    return { 'result' => '1', 'reason' => $result };
}

sub api2 {
    my $func = shift;
    $API{'changesiteip'}{'func'}       = 'api2_changesiteip';
    $API{'changesiteip'}{'engine'}     = 'hasharray';
    return $API{$func};
}

1;