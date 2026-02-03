<?php
# Dev environment LocalSettings

if ( !defined( 'MEDIAWIKI' ) ) { exit; }

$wgSitename = "Slop Wiki (DEV)";
$wgMetaNamespace = "Slop_Wiki";

$wgScriptPath = "";
$wgServer = "http://localhost:3000";
$wgResourceBasePath = $wgScriptPath;

$wgLogos = [
    '1x' => "/logo.svg",
    'icon' => "/logo.svg",
];

$wgEnableEmail = false;
$wgEnableUserEmail = false;

$wgDBtype = "mysql";
$wgDBserver = "db";
$wgDBname = "mediawiki";
$wgDBuser = "wiki";
$wgDBpassword = "devpass";
$wgDBprefix = "";

$wgMainCacheType = CACHE_NONE;
$wgEnableUploads = false;
$wgUseImageMagick = true;
$wgImageMagickConvertCommand = "/usr/bin/convert";
$wgUseInstantCommons = false;
$wgPingback = false;
$wgLanguageCode = "en";
$wgLocaltimezone = "UTC";

$wgSecretKey = "devsecretkey12345678901234567890123456789012345678901234567890";
$wgAuthenticationTokenVersion = "1";
$wgUpgradeKey = "devupgrade123";

$wgDefaultSkin = "vector-2022";
wfLoadSkin( 'MinervaNeue' );
wfLoadSkin( 'MonoBook' );
wfLoadSkin( 'Timeless' );
wfLoadSkin( 'Vector' );

# Karma gate extension (testing)
wfLoadExtension( "SlopKarmaGate" );
$wgSlopApiUrl = "http://backend:8000";
$wgSlopKarmaRequired = 10;
