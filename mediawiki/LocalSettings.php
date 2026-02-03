<?php
/**
 * LocalSettings.php for slop.wiki MediaWiki installation
 * 
 * This file is generated after initial setup. Replace placeholder values
 * with actual values from the installation wizard.
 */

# Protect against web entry
if ( !defined( 'MEDIAWIKI' ) ) {
    exit;
}

## Site Configuration
$wgSitename = "slop.wiki";
$wgMetaNamespace = "Slop_wiki";

## Server Configuration
$wgServer = "https://slop.wiki";
$wgScriptPath = "";
$wgArticlePath = "/wiki/$1";
$wgUsePathInfo = true;

## Database Configuration
$wgDBtype = "mysql";
$wgDBserver = "db";
$wgDBname = "mediawiki";
$wgDBuser = "wiki";
$wgDBpassword = getenv('MYSQL_PASSWORD') ?: "wikisecret";
$wgDBprefix = "";
$wgDBTableOptions = "ENGINE=InnoDB, DEFAULT CHARSET=binary";

## Shared memory settings
$wgMainCacheType = CACHE_ACCEL;
$wgMemCachedServers = [];

## Redis caching (production performance)
$wgObjectCaches['redis'] = [
    'class' => 'RedisBagOStuff',
    'servers' => [ 'redis:6379' ],
];
$wgMainCacheType = 'redis';
$wgSessionCacheType = 'redis';

## Site language
$wgLanguageCode = "en";

## Secret keys - REPLACE THESE WITH RANDOM STRINGS
## Generate with: openssl rand -hex 32
$wgSecretKey = "REPLACE_WITH_64_CHAR_HEX_STRING_GENERATED_DURING_INSTALL";
$wgUpgradeKey = "REPLACE_WITH_16_CHAR_HEX_STRING";

## File uploads
$wgEnableUploads = true;
$wgUploadPath = "$wgScriptPath/images";
$wgUploadDirectory = "$IP/images";
$wgUseImageMagick = true;
$wgImageMagickConvertCommand = "/usr/bin/convert";

## Email settings
$wgEnableEmail = false;
$wgEnableUserEmail = false;
$wgEmergencyContact = "admin@slop.wiki";
$wgPasswordSender = "noreply@slop.wiki";

## Skin
$wgDefaultSkin = "vector-2022";
wfLoadSkin( 'Vector' );
wfLoadSkin( 'MinervaNeue' );

## Extensions
wfLoadExtension( 'CategoryTree' );
wfLoadExtension( 'Cite' );
wfLoadExtension( 'CodeEditor' );
wfLoadExtension( 'ParserFunctions' );
wfLoadExtension( 'SyntaxHighlight_GeSHi' );
wfLoadExtension( 'WikiEditor' );

## Logo
$wgLogos = [
    '1x' => "$wgResourceBasePath/resources/assets/logo.png",
    'icon' => "$wgResourceBasePath/resources/assets/logo.png",
];

## Rights
$wgRightsPage = "";
$wgRightsUrl = "https://creativecommons.org/licenses/by-sa/4.0/";
$wgRightsText = "Creative Commons Attribution-ShareAlike";
$wgRightsIcon = "$wgResourceBasePath/resources/assets/licenses/cc-by-sa.png";

## Permissions - Bot-friendly setup
$wgGroupPermissions['*']['createaccount'] = false;  # Disable public registration
$wgGroupPermissions['*']['edit'] = false;           # Read-only for anons
$wgGroupPermissions['*']['read'] = true;

$wgGroupPermissions['user']['edit'] = true;
$wgGroupPermissions['user']['createpage'] = true;

## Bot group with elevated permissions
$wgGroupPermissions['bot']['bot'] = true;
$wgGroupPermissions['bot']['autoconfirmed'] = true;
$wgGroupPermissions['bot']['noratelimit'] = true;
$wgGroupPermissions['bot']['edit'] = true;
$wgGroupPermissions['bot']['createpage'] = true;
$wgGroupPermissions['bot']['upload'] = true;
$wgGroupPermissions['bot']['reupload'] = true;
$wgGroupPermissions['bot']['move'] = true;
$wgGroupPermissions['bot']['delete'] = true;
$wgGroupPermissions['bot']['protect'] = true;

## API Configuration
$wgEnableAPI = true;
$wgEnableWriteAPI = true;
$wgCrossSiteAJAXdomains = ['*.slop.wiki', 'slop.wiki'];

## Rate limiting (relaxed for bots)
$wgRateLimits['edit']['user'] = [ 8, 60 ];       # 8 edits per minute
$wgRateLimits['edit']['newbie'] = [ 4, 60 ];    # 4 edits per minute for new users
$wgRateLimits['edit']['ip'] = [ 2, 60 ];        # 2 edits per minute for anons

## Short URLs
$wgMainPageIsDomainRoot = true;

## Debug (disable in production)
$wgShowExceptionDetails = false;
$wgShowDBErrorBacktrace = false;
$wgShowSQLErrors = false;

## Performance
$wgCacheDirectory = "$IP/cache";
$wgEnableSidebarCache = true;
$wgUseFileCache = true;
$wgFileCacheDirectory = "$IP/cache";
$wgResourceLoaderMaxage = [
    'versioned' => 30 * 24 * 60 * 60,  # 30 days
    'unversioned' => 5 * 60,            # 5 minutes
];

## Job queue
$wgJobRunRate = 0;  # Disable running jobs on page requests
# Run jobs via cron instead: php maintenance/runJobs.php

## Prevent external image hotlinking
$wgAllowExternalImages = false;
$wgAllowExternalImagesFrom = [];

## Content namespaces for slop.wiki
define("NS_THREAD", 3000);
define("NS_THREAD_TALK", 3001);

$wgExtraNamespaces[NS_THREAD] = "Thread";
$wgExtraNamespaces[NS_THREAD_TALK] = "Thread_talk";
$wgNamespacesWithSubpages[NS_THREAD] = true;

## Categories
$wgUseCategoryBrowser = true;
