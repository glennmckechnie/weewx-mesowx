<?php

require_once('EntityRetentionPolicyFactory.class.php');

abstract class Entity {
    
    protected $config;
    protected $entityId;
    protected $entityConfig;

    public function __construct($entityId, $config) {
        if(!array_key_exists($entityId, $config['entity'])) {
            throw new EntityException("Entity couldn't be found with id: $entityId");
        }
        $this->config = $config;
        $this->entityId = $entityId;
        $this->entityConfig = $config['entity'][$entityId];
    }

    public function canUpdate($securityKey) {
        // check if updating in enabled
        if(!$this->entityConfig['accessControl']['update']['allow']) {
            throw new EntitySecurityException("Update not allowed for this entity");
        }
        // make sure security key matches
        $entitySecurityKey = $this->entityConfig['accessControl']['update']['securityKey'];
        if(!$entitySecurityKey) {
            throw new EntityConfigurationException("You must configure the securityKey for entity ID: $this->entityId");
        }
        if($entitySecurityKey !== $securityKey) {
            throw new EntitySecurityException("Provided security key doesn't match.");
        }
    }

    public function upsert($data) {
        // TODO add support for update and determine insert or update here, for now just supporting insert
        $this->performInsert($data);
        // apply retention policy
        $this->applyRetentionPolicy();
    }

    /**
     * Delete records before a certain time.
     *
     * @param dateTime the date in seconds since epoch
     */
    public abstract function deleteRecordsBeforeDateTime($dateTime);

    protected function applyRetentionPolicy() {
        
        if(array_key_exists('retentionPolicy', $this->entityConfig)) {
            $policyConfig = $this->entityConfig['retentionPolicy'];
            if($policyConfig['trigger'] == 'update') {
                $policy = EntityRetentionPolicyFactory::createEntityRetentionPolicy($policyConfig);
                $policy->applyPolicy($this);
            }
        }
    }

    protected abstract function performInsert($data);
}


class EntityException extends Exception { }

class EntitySecurityException extends EntityException { }

class EntityConfigurationException extends EntityException { }

?>
