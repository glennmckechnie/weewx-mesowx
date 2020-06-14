<?php

require_once('WindowRetentionPolicy.class.php');

class EntityRetentionPolicyFactory {

    public static function createEntityRetentionPolicy($policyConfig) {
        $type = $policyConfig['type'];
        switch($type) {
            case 'window':
                $policy = self::createWindowRetentionPolicy($policyConfig);
                break;
            default:
                throw new RuntimeException("Unsupported entity retention policty type: $type");
        }
        return $policy;
    }

    private static function createWindowRetentionPolicy($policyConfig) {
        return new WindowRetentionPolicy($policyConfig);
    }
}

?>
