<?php

require_once('EntityRetentionPolicy.class.php');

class WindowRetentionPolicy implements EntityRetentionPolicy {

    protected $windowSize;

    public function __construct($policyConfig) {
        $windowSize = $policyConfig['windowSize'];
        if(!is_numeric($windowSize) && $windowSize > 0) {
            // XXX throw a different type of exception?
            throw new EntityException("Invalid windowSize, must be numeric: '$windowSize'");
        }
        $this->windowSize = $windowSize;
    }

    public function applyPolicy(Entity $entity) {
        $windowMin = time() - $this->windowSize;
        $entity->deleteRecordsBeforeDateTime($windowMin);
    }
}

?>
