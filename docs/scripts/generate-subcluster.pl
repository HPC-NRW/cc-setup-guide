#!/usr/bin/env perl

use strict;
use warnings;
use utf8;
use JSON::PP ();
use File::Spec ();

# No shell interpolation: only these two checked LIKWID executables are invoked.
sub executable {
    my ($name) = @_;
    for my $dir (File::Spec->path()) {
        my $path = File::Spec->catfile($dir, $name);
        return $path if -f $path && -x $path;
    }
    die "Required program $name was not found in PATH\n";
}
my $topology_program = executable('likwid-topology');
my $bench_program = executable('likwid-bench');

sub run_command {
    my (@args) = @_;
    open(my $child, '-|', @args) or die "Cannot execute $args[0]: $!\n";
    local $/;
    my $output = <$child>;
    close($child) or die "$args[0] failed (exit " . ($? >> 8) . ", signal " . ($? & 127) . ")\n";
    return $output // '';
}
sub positive_integer {
    my ($value, $label) = @_;
    die "Missing or invalid $label in likwid-topology output\n"
        unless defined($value) && $value =~ /\A[1-9][0-9]*\z/;
    return 0 + $value;
}
sub benchmark_value {
    my ($output, $label) = @_;
    my @values = ($output =~ /^\s*\Q$label\E:\s*([0-9]+(?:\.[0-9]*)?(?:[Ee][+-]?[0-9]+)?)\s*$/mg);
    die "Expected one positive finite $label result from likwid-bench\n"
        unless @values == 1 && $values[0] > 0 && $values[0] < 1e100;
    return int($values[0] / 1000 + 0.5);
}

my %INFO;
my %DOMAINS;

my $SMT;
$DOMAINS{socket} = [];
$DOMAINS{memoryDomain} = [];
$DOMAINS{core} = [];
$DOMAINS{gpu} = [];

my $gpuID=-1;
my $id = -2;

# Step 1 : Extract system information
my $topo = run_command($topology_program, '-O', '-G');
$INFO{numGPUs} = 0;

foreach my $ln (split("\n", $topo)) {
    if ( $ln =~ /^STRUCT,NUMA Topology ([0-9]+)/ ) {
        $id = $1;
    }
    if ( $ln =~ /^Processors/ ) {
        my @fields = split(",", $ln);
        shift @fields;
        $DOMAINS{memoryDomain}[$id] = [ @fields ];
    }
    if ( $ln =~ /^STRUCT,Cache Topology L1/ ) {
        $id = -1;
    }
    if ( $ln =~ /^Cache groups/ ) {
        if ( $id == -1 ) {
            my @fields = split(",", $ln);
            shift @fields;
            my $i = 0;
            foreach my $core ( @fields ) {
                $DOMAINS{core}[$i++] = [ split(" ", $core) ];
            }
            $id = 0;
        }
    }
    if ( $ln =~ /^ID:/ ) {
        my @fields = split(",", $ln);
        die "Invalid GPU ID in likwid-topology output\n"
            unless defined($fields[1]) && $fields[1] =~ /\A[0-9]+\z/;
        $gpuID = $fields[1];
    }
    if ( $gpuID >= 0 ) {
        if ( $ln =~ /^Name:/ ) {
            my @fields = split(",", $ln);
            $DOMAINS{gpu}[$gpuID] = {function => 0};
            $DOMAINS{gpu}[$gpuID]{model} = $fields[1];
            if ( $fields[1] =~ /nvidia/i ) {
                $DOMAINS{gpu}[$gpuID]{type} = "Nvidia GPU";
            } elsif  ( $fields[1] =~ /amd/i ) {
                $DOMAINS{gpu}[$gpuID]{type} = "AMD GPU";
            } elsif  ( $fields[1] =~ /intel/i ) {
                $DOMAINS{gpu}[$gpuID]{type} = "Intel GPU";
            }
        }
        if ( $ln =~ /^PCI bus:/ ) {
            my @fields = split(",", $ln);
            $fields[1] =~ s/0x//;
            $DOMAINS{gpu}[$gpuID]{bus} = $fields[1];
        }
        if ( $ln =~ /^PCI domain:/ ) {
            my @fields = split(",", $ln);
            $fields[1] =~ s/0x//;
            $DOMAINS{gpu}[$gpuID]{domain} = $fields[1];
        }
        if ( $ln =~ /^PCI device/ ) {
            my @fields = split(",", $ln);
            $fields[1] =~ s/0x//;
            $DOMAINS{gpu}[$gpuID]{device} = $fields[1];
        }
        if ( $ln =~ /^PCI function:/ ) {
            my @fields = split(",", $ln);
            $fields[1] =~ s/0x//;
            $DOMAINS{gpu}[$gpuID]{function} = $fields[1];
            $gpuID = -1;
        }
    }
    if ( $ln =~ /^CPU name:/ ) {
        my @fields = split(",", $ln);
        $INFO{processor} = $fields[1];
    }
    if ( $ln =~ /^CPU type/ ) {
        my @fields = split(",", $ln);
        $INFO{family} = $fields[1];
        $INFO{family} =~ s/[\(\)]//g;
    }
    if ( $ln =~ /^Sockets:/ ) {
        my @fields = split(",", $ln);
        $INFO{socketsPerNode} = $fields[1];
    }
    if ( $ln =~ /^Cores per socket:/ ) {
        my @fields = split(",", $ln);
        $INFO{coresPerSocket} = $fields[1];
    }
    if ( $ln =~ /^GPU count:/ ) {
        my @fields = split(",", $ln);
        $INFO{numGPUs} = $fields[1];
    }
    if ( $ln =~ /^Threads per core:/ ) {
        my @fields = split(",", $ln);
        $SMT = $fields[1];
        $INFO{threadsPerCore} = $SMT;
    }
    if ( $ln =~ /^NUMA domains:/ ) {
        my @fields = split(",", $ln);
        $INFO{memoryDomainsPerNode} = $fields[1];
    }
    if ( $ln =~ /^Socket ([0-9]+)/ ) {
        my @fields = split(",", $ln);
        shift @fields;
        $DOMAINS{socket}[$1] = [ @fields ];
    }
}

# Validate all topology data before benchmarking or printing any JSON.
for my $key (qw(socketsPerNode coresPerSocket threadsPerCore memoryDomainsPerNode)) {
    $INFO{$key} = positive_integer($INFO{$key}, $key);
}
die "Missing CPU name in likwid-topology output\n"
    unless defined($INFO{processor}) && $INFO{processor} =~ /\S/;
die "Invalid GPU count in likwid-topology output\n"
    unless defined($INFO{numGPUs}) && $INFO{numGPUs} =~ /\A[0-9]+\z/;
my $numCoresPerNode = $INFO{coresPerSocket} * $INFO{socketsPerNode};
my $numThreads = $numCoresPerNode * $INFO{threadsPerCore};
die "Non-uniform cores per NUMA domain are unsupported; configure this topology manually\n"
    if $numCoresPerNode % $INFO{memoryDomainsPerNode};
my %expected_groups = (
    socket => $INFO{socketsPerNode},
    memoryDomain => $INFO{memoryDomainsPerNode},
    core => $numCoresPerNode,
);
my %node_ids;
for my $kind (qw(socket memoryDomain core)) {
    my %seen;
    die "Unexpected $kind group count\n" unless @{$DOMAINS{$kind}} == $expected_groups{$kind};
    for my $group (@{$DOMAINS{$kind}}) {
        die "Empty $kind group\n" unless ref($group) eq 'ARRAY' && @$group;
        for my $thread (@$group) {
            die "Invalid or duplicate HWThread in $kind topology\n"
                unless defined($thread) && $thread =~ /\A[0-9]+\z/ && !$seen{$thread}++;
            $thread = 0 + $thread;
        }
        die "Unexpected $kind group size\n"
            if ($kind eq 'core' && @$group != $INFO{threadsPerCore})
            || ($kind eq 'socket' && @$group != $INFO{coresPerSocket} * $INFO{threadsPerCore});
    }
    die "Incomplete $kind topology\n" unless keys(%seen) == $numThreads;
    if ($kind eq 'socket') { %node_ids = %seen; }
    else { die "Inconsistent $kind HWThreads\n" if grep { !exists($node_ids{$_}) } keys(%seen); }
}
my @accelerators;
for my $gpu_index (0 .. $INFO{numGPUs} - 1) {
    my $gpu = $DOMAINS{gpu}[$gpu_index];
    die "Incomplete GPU $gpu_index description\n"
        unless ref($gpu) eq 'HASH' && defined($gpu->{model}) && defined($gpu->{type});
    for my $key (qw(domain bus device function)) {
        die "Invalid GPU $gpu_index PCI $key\n"
            unless defined($gpu->{$key}) && $gpu->{$key} =~ /\A[0-9a-fA-F]+\z/
                && hex($gpu->{$key}) <= ($key eq 'domain' ? 0xffffffff : $key eq 'bus' ? 255 : $key eq 'device' ? 31 : 7);
    }
    push @accelerators, {
        id => sprintf('%08x:%02x:%02x.%x', hex($gpu->{domain}), hex($gpu->{bus}), hex($gpu->{device}), hex($gpu->{function})),
        type => $gpu->{type}, model => $gpu->{model},
    };
}
my $numCoresPerMemoryDomain = $numCoresPerNode / $INFO{memoryDomainsPerNode};
my @memory_args = map { ('-w', "M$_:1GB:$numCoresPerMemoryDomain:1:$SMT") }
    0 .. $INFO{memoryDomainsPerNode} - 1;
print STDERR "Using: @memory_args\n";
my $memBw = benchmark_value(run_command($bench_program, '-t', 'clload', @memory_args), 'MByte/s');
my $flopsScalar = benchmark_value(
    run_command($bench_program, '-t', 'peakflops', '-w', "N:24kB:$numCoresPerNode"), 'MFlops/s');

my $simd = '';
open(my $cpuinfo, '<', '/proc/cpuinfo') or die "Cannot read /proc/cpuinfo: $!\n";
while (my $line = <$cpuinfo>) {
    next unless $line =~ /^flags\s*:/;
    $simd = '_avx_fma' if $line =~ /\bavx2\b/ && $line =~ /\bfma\b/;
    $simd = '_avx512_fma' if $line =~ /\bavx512f\b/;
    last;
}
close($cpuinfo) or die "Cannot close /proc/cpuinfo: $!\n";
print STDERR "Using peakflops variant $simd\n";
my $flopsSimd = benchmark_value(
    run_command($bench_program, '-t', "peakflops$simd", '-w', "N:500kB:$numCoresPerNode"), 'MFlops/s');

my $topology = {
    node => [sort { $a <=> $b } keys(%node_ids)],
    socket => $DOMAINS{socket}, memoryDomain => $DOMAINS{memoryDomain}, core => $DOMAINS{core},
};
# Force numeric JSON identifiers (hash keys otherwise remain Perl strings).
$topology->{node} = [map { 0 + $_ } @{$topology->{node}}];
$topology->{accelerators} = \@accelerators if @accelerators;
my $subcluster = {
    name => '<FILL IN>', nodes => '<FILL IN NODE RANGES>', processorType => $INFO{processor},
    socketsPerNode => $INFO{socketsPerNode}, coresPerSocket => $INFO{coresPerSocket},
    threadsPerCore => $INFO{threadsPerCore}, topology => $topology,
    flopRateScalar => {unit => {base => 'F/s', prefix => 'G'}, value => $flopsScalar},
    flopRateSimd => {unit => {base => 'F/s', prefix => 'G'}, value => $flopsSimd},
    memoryBandwidth => {unit => {base => 'B/s', prefix => 'G'}, value => $memBw},
};
# Exactly one complete JSON object on stdout; diagnostics go to stderr.
print JSON::PP->new->utf8->canonical->pretty->encode($subcluster);
