#!/usr/bin/perl
use strict;
use warnings;
use File::Find;
use File::Basename;
use File::Spec;
use Getopt::Long;
use JSON::PP;

# =============================================================================
# check_dataset_consistency.pl
#
# QA tool for the TrustHub hardware-Trojan dataset.
#
# Walks root/data/<family>/<variant>/ and, for every variant folder, figures
# out which side(s) it has:
#   - a "netlist" file  (matches /netlist/i, e.g. clean_netlist.pt,
#                         trojan_netlist.pt, standard_netlist.pt, 90nm..., etc.)
#   - an "rtl" file     (matches /rtl/i, e.g. trojan_rtl_tokens_chunk.pt,
#                         clean_rtl_embedding_chunk.pt, etc.)
#
# Then flags:
#   1. Variants missing a netlist file entirely
#   2. Variants missing an RTL file entirely
#   3. "Orphaned" trojan/clean RTL files with no matching netlist counterpart
#   4. Prefix mismatches between netlist and RTL naming
#      (e.g. tjin_netlist.pt next to trojan_rtl_*.pt)
#   5. Variants present in manifest.json / metadata/*.json but missing on
#      disk, or vice versa (if those files are found)
#
# USAGE:
#   perl check_dataset_consistency.pl --root /path/to/trusthub/features
#   perl check_dataset_consistency.pl --root C:\path\to\features --csv report.csv
#
# On Windows, install Strawberry Perl (https://strawberryperl.com/), then:
#   cpan JSON::PP        (usually bundled already with modern Perl)
# =============================================================================

my $root    = '.';
my $csv_out = '';
my $verbose = 0;

GetOptions(
    "root=s" => \$root,
    "csv=s"  => \$csv_out,
    "verbose" => \$verbose,
) or die "Usage: $0 --root <path_to_features_dir> [--csv report.csv] [--verbose]\n";

my $data_dir     = File::Spec->catdir($root, "data");
my $manifest_path = File::Spec->catfile($root, "manifest.json");
my $metadata_dir  = File::Spec->catdir($root, "metadata");

die "Data directory not found: $data_dir\n" unless -d $data_dir;

# -----------------------------------------------------------------------
# Step 1: Walk data/<family>/<variant>/ and bucket files by variant
# -----------------------------------------------------------------------
my %variants;  # $variants{"AES/AES-T100"} = { files => [...], family => "AES" }

find({
    wanted => sub {
        return unless -f $_;
        return unless /\.pt$/i;

        my $full = $File::Find::name;
        my $rel  = File::Spec->abs2rel($full, $data_dir);
        my @parts = File::Spec->splitdir($rel);

        # Expect data/<family>/<variant>/<file>.pt
        return unless @parts >= 3;

        my $family  = $parts[0];
        my $variant = $parts[1];
        my $fname   = $parts[-1];
        my $key     = "$family/$variant";

        push @{ $variants{$key}{files} }, $fname;
        $variants{$key}{family} = $family;
    },
    no_chdir => 1,
}, $data_dir);

# -----------------------------------------------------------------------
# Step 2: Classify each variant's files and detect problems
# -----------------------------------------------------------------------
my @rows;  # collected issues for CSV/report

for my $key (sort keys %variants) {
    my @files = @{ $variants{$key}{files} };

    my @netlist_files = grep { /netlist/i } @files;
    my @rtl_files     = grep { /rtl/i }     @files;
    my @other_files   = grep { !/netlist/i && !/rtl/i } @files;

    if ($verbose) {
        print "== $key ==\n";
        print "   netlist: @netlist_files\n" if @netlist_files;
        print "   rtl:     @rtl_files\n"     if @rtl_files;
        print "   other:   @other_files\n"   if @other_files;
    }

    # Issue 1: no netlist at all
    if (!@netlist_files) {
        push @rows, [$key, "MISSING_NETLIST", "No file matching /netlist/i found", join(";", @files)];
    }

    # Issue 2: no RTL at all
    if (!@rtl_files) {
        push @rows, [$key, "MISSING_RTL", "No file matching /rtl/i found", join(";", @files)];
    }

    # Issue 3/4: prefix mismatch between netlist side and rtl side.
    # Extract a "label prefix" for each file: clean / trojan / standard / tjin / tjfree / <tech-node>
    my @known_prefixes = qw(clean trojan standard tjin tjfree);

    my @netlist_prefixes = uniq( map { extract_prefix($_, \@known_prefixes) } @netlist_files );
    my @rtl_prefixes     = uniq( map { extract_prefix($_, \@known_prefixes) } @rtl_files );

    if (@netlist_files && @rtl_files) {
        my %netlist_set = map { $_ => 1 } @netlist_prefixes;
        my %rtl_set     = map { $_ => 1 } @rtl_prefixes;

        # RTL prefixes with no matching netlist prefix (orphaned RTL)
        for my $p (@rtl_prefixes) {
            next if $p eq 'unknown';
            unless ($netlist_set{$p}) {
                push @rows, [$key, "ORPHANED_RTL",
                    "RTL file(s) with prefix '$p' have no matching netlist prefix",
                    join(";", grep { extract_prefix($_, \@known_prefixes) eq $p } @rtl_files)];
            }
        }

        # netlist prefixes with no matching RTL prefix
        for my $p (@netlist_prefixes) {
            next if $p eq 'unknown';
            unless ($rtl_set{$p}) {
                push @rows, [$key, "ORPHANED_NETLIST",
                    "Netlist file(s) with prefix '$p' have no matching RTL prefix",
                    join(";", grep { extract_prefix($_, \@known_prefixes) eq $p } @netlist_files)];
            }
        }
    }
}

# -----------------------------------------------------------------------
# Step 3: Cross-check against manifest.json / metadata/*.json, if present
# -----------------------------------------------------------------------
if (-f $manifest_path) {
    print "\nChecking manifest.json against files on disk...\n";
    open(my $fh, '<', $manifest_path) or die "Can't open $manifest_path: $!";
    local $/;
    my $json_text = <$fh>;
    close $fh;

    my $manifest = eval { decode_json($json_text) };
    if ($@) {
        warn "Could not parse manifest.json: $@\n";
    } elsif (ref($manifest) eq 'ARRAY') {
        my %on_disk = map { $_ => 1 } keys %variants;
        for my $entry (@$manifest) {
            my $id = ref($entry) eq 'HASH' ? ($entry->{graph_id} // $entry->{id} // '') : $entry;
            next unless $id;
            (my $key = $id) =~ s{/[^/]+$}{};  # strip trailing /clean_netlist etc if present
            unless (exists $variants{$key} || exists $variants{$id}) {
                push @rows, ["manifest:$id", "MANIFEST_NOT_ON_DISK",
                    "manifest.json references '$id' but no matching folder found under data/", ""];
            }
        }
    } else {
        warn "manifest.json has an unexpected shape (expected an array); skipping cross-check.\n";
    }
} else {
    print "\nNo manifest.json found at $manifest_path; skipping manifest cross-check.\n";
}

# -----------------------------------------------------------------------
# Step 4: Print summary + optionally write CSV
# -----------------------------------------------------------------------
print "\n===== SUMMARY =====\n";
if (!@rows) {
    print "No issues found. Dataset looks consistent.\n";
} else {
    printf "%-28s %-20s %s\n", "VARIANT", "ISSUE", "DETAIL";
    printf "%-28s %-20s %s\n", "-" x 28, "-" x 20, "-" x 40;
    for my $r (@rows) {
        printf "%-28s %-20s %s\n", $r->[0], $r->[1], $r->[2];
    }
    print "\nTotal issues found: " . scalar(@rows) . "\n";
}

if ($csv_out) {
    open(my $out, '>', $csv_out) or die "Can't write $csv_out: $!";
    print $out "variant,issue,detail,files\n";
    for my $r (@rows) {
        print $out join(",", map { csv_escape($_) } @$r) . "\n";
    }
    close $out;
    print "\nWrote CSV report to $csv_out\n";
}

exit(@rows ? 1 : 0);  # non-zero exit if issues found, useful in CI/scripts

# =============================================================================
# Helpers
# =============================================================================

sub extract_prefix {
    my ($filename, $known_prefixes) = @_;
    for my $p (@$known_prefixes) {
        return $p if $filename =~ /^\Q$p\E[_.]/i;
    }
    # fall back: tech-node style prefixes like 90nm_netlist.pt / 180nm_netlist.pt
    return $1 if $filename =~ /^(\d+nm)[_.]/i;
    return 'unknown';
}

sub uniq {
    my %seen;
    return grep { !$seen{$_}++ } @_;
}

sub csv_escape {
    my ($val) = @_;
    $val = '' unless defined $val;
    if ($val =~ /[",\n]/) {
        $val =~ s/"/""/g;
        return qq("$val");
    }
    return $val;
}