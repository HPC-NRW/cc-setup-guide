#!/usr/bin/env perl
use strict;
use warnings;
use utf8;

# Adapted from the RUB migration helper used on cc. The accompanying mapping
# keeps the original key translations; paths and SQL handling are portable.
use DBI;
use Getopt::Long qw(GetOptions);
use JSON::PP qw(decode_json);

my $dbRequired = 11;
my $dbSource = '/opt/monitoring/cc-backend/var/job.db';
my $mapSource = $0;
$mapSource =~ s{[^/]+$}{configmap_v$dbRequired.json};
my ($dryRun, $help) = (0, 0);
GetOptions(
    'database=s' => \$dbSource,
    'mapping=s' => \$mapSource,
    'dry-run' => \$dryRun,
    'help' => \$help,
) or die "Use --help for usage.\n";
die "Unexpected arguments. Use --help for usage.\n" if @ARGV;
if ($help) {
    print "Usage: perl updateUserconfig.pl [--database PATH] [--mapping PATH] [--dry-run]\n";
    print "Rename saved UI preference keys after migration to SQLite schema 11.\n";
    exit 0;
}

open my $mapFile, '<:raw', $mapSource or die "Cannot read mapping: $!\n";
my $rawMap = do { local $/; <$mapFile> };
close $mapFile;
my $jsonMap = decode_json($rawMap);
die "Mapping must target version $dbRequired.\n"
    unless ref($jsonMap) eq 'HASH' && ($jsonMap->{version} // 0) == $dbRequired
        && ref($jsonMap->{confkeys}) eq 'ARRAY';
my %mapping;
for my $item (@{$jsonMap->{confkeys}}) {
    die "Invalid mapping entry.\n"
        unless ref($item) eq 'HASH'
            && defined($item->{old}) && defined($item->{new})
            && !ref($item->{old}) && !ref($item->{new})
            && length($item->{old}) && length($item->{new})
            && $item->{old} !~ /:/ && $item->{new} !~ /:/;
    die "Duplicate source key in mapping.\n" if exists $mapping{$item->{old}};
    $mapping{$item->{old}} = $item->{new};
}
die "Database must be an existing regular file.\n" unless -f $dbSource;

my $dbConn = DBI->connect("dbi:SQLite:dbname=$dbSource", '', '', {
    AutoCommit => 0, RaiseError => 1, PrintError => 0, sqlite_unicode => 1,
});
my ($rowCount, $updateCount) = (0, 0);
eval {
    my $state = $dbConn->selectall_arrayref('SELECT version, dirty FROM schema_migrations');
    die "Run the database migration to schema $dbRequired first.\n"
        unless @$state == 1 && $state->[0][0] == $dbRequired && !$state->[0][1];
    my $rows = $dbConn->selectall_arrayref(
        'SELECT username, confkey FROM configuration ORDER BY username, confkey');
    my %keys = map { ($_->[0] . "\0" . $_->[1]) => 1 } @$rows;
    my @changes;
    for my $row (@$rows) {
        $rowCount++;
        my ($username, $oldKey) = @$row;
        my ($prefix, $suffix) = split /:/, $oldKey, 2;
        next unless exists $mapping{$prefix};
        my $newKey = $mapping{$prefix} . (defined($suffix) ? ":$suffix" : '');
        next if $newKey eq $oldKey;
        die "Old and new preference keys coexist; resolve the conflict before retrying.\n"
            if $keys{$username . "\0" . $newKey};
        $keys{$username . "\0" . $newKey} = 1;
        push @changes, [$newKey, $username, $oldKey];
    }
    $updateCount = scalar @changes;
    if ($dryRun) {
        $dbConn->rollback();
    } else {
        my $update = $dbConn->prepare(
            'UPDATE configuration SET confkey = ? WHERE username = ? AND confkey = ?');
        $update->execute(@$_) for @changes;
        $dbConn->commit();
    }
    1;
} or do {
    my $error = $@ || 'Unknown migration error';
    eval { $dbConn->rollback(); };
    $dbConn->disconnect();
    die $error;
};
$dbConn->disconnect();
print "Scanned $rowCount rows; ", ($dryRun ? 'would rename' : 'renamed'), " $updateCount preference keys.\n";
