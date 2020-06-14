<?php

require_once('Entity.class.php');

interface EntityRetentionPolicy {

    public function applyPolicy(Entity $entity);
}

?>
