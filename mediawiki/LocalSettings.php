<?php
if ( !defined( 'MEDIAWIKI' ) ) exit;

$wgSitename = "slop.wiki";
$wgServer = "https://slop.wiki";
$wgScriptPath = "";

$wgDBtype = "mysql";
$wgDBserver = "db";
$wgDBname = "mediawiki";
$wgDBuser = "wiki";
$wgDBpassword = "riis3eGAobFRDvjtRsJr";

$wgMainCacheType = CACHE_NONE;
$wgSessionCacheType = CACHE_DB;
$wgMemCachedServers = [];

$wgSecretKey = "abc123def456abc123def456abc123def456abc123def456abc123def456abcd";
$wgUpgradeKey = "abc123def456";

$wgLanguageCode = "en";
$wgEnableUploads = true;

wfLoadSkin( 'Vector' );
$wgDefaultSkin = "vector";

$wgGroupPermissions['*']['createaccount'] = false;
$wgGroupPermissions['*']['edit'] = false;

## Branding
$wgLogo = "/logo.svg";
$wgFavicon = "/favicon.svg";
