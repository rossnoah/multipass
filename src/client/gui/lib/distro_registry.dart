import 'package:flutter/material.dart';

/// Per-distribution presentation metadata used by both the catalogue cards
/// and the terminal-tab icons. The `os` value comes from the daemon's image
/// manifest and matches `VMImageInfo::os` exactly (case-insensitive).
class DistroInfo {
  final String logoAsset;
  final String displayTitle;
  final String description;

  /// Background colour to draw behind the logo in tab-bar style chips.
  /// `null` means use the SVG's own colours on a transparent background.
  final Color? tabBackground;

  /// Recolour applied to the SVG paths when [tabBackground] is set.
  /// `null` means the SVG should render in its natural colours.
  final Color? tabForeground;

  const DistroInfo({
    required this.logoAsset,
    required this.displayTitle,
    required this.description,
    this.tabBackground,
    this.tabForeground,
  });
}

const _ubuntuOrange = Color(0xffE95420);

const _ubuntuServer = DistroInfo(
  logoAsset: 'assets/ubuntu.svg',
  displayTitle: 'Ubuntu Server',
  description: 'Ubuntu operating system designed as a backbone for the internet',
  tabBackground: _ubuntuOrange,
  tabForeground: Colors.white,
);

const _ubuntuCore = DistroInfo(
  logoAsset: 'assets/ubuntu.svg',
  displayTitle: 'Ubuntu Core',
  description: 'Ubuntu operating system optimised for IoT and Edge',
  tabBackground: _ubuntuOrange,
  tabForeground: Colors.white,
);

const _registry = <String, DistroInfo>{
  'ubuntu': _ubuntuServer,
  'debian': DistroInfo(
    logoAsset: 'assets/debian.svg',
    displayTitle: 'Debian',
    description: 'Debian official cloud image',
  ),
  'fedora': DistroInfo(
    logoAsset: 'assets/fedora.svg',
    displayTitle: 'Fedora',
    description: 'Fedora Cloud Edition',
  ),
  'almalinux': DistroInfo(
    logoAsset: 'assets/alma.svg',
    displayTitle: 'AlmaLinux',
    description: 'Enterprise Linux, forever-free RHEL-compatible distribution',
  ),
  'rocky': DistroInfo(
    logoAsset: 'assets/rocky.svg',
    displayTitle: 'Rocky Linux',
    description: 'Community enterprise Linux, RHEL-compatible',
  ),
  'arch': DistroInfo(
    logoAsset: 'assets/arch.svg',
    displayTitle: 'Arch Linux',
    description: 'Lightweight, rolling-release Linux',
  ),
};

/// Returns presentation info for [os] (the daemon's `VMImageInfo::os`).
///
/// Pass [aliases] when you have them so Ubuntu Core gets the right title and
/// description (Core ships under the same `Ubuntu` os value as Server).
///
/// Falls back to Ubuntu Server styling when [os] is unknown — keeps the UI
/// rendering for new distros added server-side before the GUI knows about them.
DistroInfo distroInfoFor(String os, {Iterable<String> aliases = const []}) {
  final key = os.toLowerCase();
  if (key == 'ubuntu' && aliases.any((a) => a.contains('core'))) {
    return _ubuntuCore;
  }
  return _registry[key] ??
      DistroInfo(
        logoAsset: _ubuntuServer.logoAsset,
        displayTitle: os.isEmpty ? 'Unknown' : os,
        description: '',
        tabBackground: _ubuntuServer.tabBackground,
        tabForeground: _ubuntuServer.tabForeground,
      );
}

/// Like [distroInfoFor] but matches against free-form strings such as
/// `/etc/os-release` PRETTY_NAME values (e.g. `"AlmaLinux 10.1 (Purple Lion)"`).
/// Used by views that read the OS string from the running VM rather than the
/// image manifest.
DistroInfo distroInfoForReleaseString(String prettyName) {
  final lower = prettyName.toLowerCase();
  for (final entry in _registry.entries) {
    if (lower.contains(entry.key)) return entry.value;
  }
  return _ubuntuServer;
}
