<?php

class SlopKarmaGate {
    
    private static function getUserKarma($user) {
        if ($user->isAnon()) {
            return 0;
        }
        
        $apiUrl = MediaWiki\MediaWikiServices::getInstance()
            ->getMainConfig()->get('SlopApiUrl');
        
        $username = $user->getName();
        
        // Check karma via slop.wiki API
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $apiUrl . "/karma?username=" . urlencode($username));
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 5);
        $response = curl_exec($ch);
        curl_close($ch);
        
        if ($response) {
            $data = json_decode($response, true);
            return $data['karma'] ?? 0;
        }
        
        return 0;
    }
    
    public static function onUserCan(&$title, &$user, $action, &$result) {
        // Only gate read access
        if ($action !== 'read') {
            return true;
        }
        
        // Allow main page and login/special pages
        if ($title->isMainPage() || $title->isSpecialPage()) {
            return true;
        }
        
        // Allow category and file description pages (just metadata)
        if ($title->getNamespace() == NS_CATEGORY) {
            return true;
        }
        
        $karmaRequired = MediaWiki\MediaWikiServices::getInstance()
            ->getMainConfig()->get('SlopKarmaRequired');
        
        $userKarma = self::getUserKarma($user);
        
        if ($userKarma < $karmaRequired) {
            $result = false;
            return false;
        }
        
        return true;
    }
    
    public static function onBeforePageDisplay($out, $skin) {
        $user = $out->getUser();
        $title = $out->getTitle();
        
        if ($user->isAnon() && !$title->isMainPage() && !$title->isSpecialPage()) {
            // Show paywall message for anon users
            $out->prependHTML(
                '<div class="slop-paywall" style="background:#ffe4e4;padding:1em;margin:1em 0;border-radius:8px;">' .
                '<strong>🔒 Content requires karma ≥ 10</strong><br>' .
                'Get verified at <a href="https://api.slop.wiki">api.slop.wiki</a> and earn karma by contributing.' .
                '</div>'
            );
        }
    }
}
