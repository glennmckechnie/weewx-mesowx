<?php

// if display_errors = on, errors will result in a 200 status, so setting the 
// status to 500 ahead of time, then resetting to 200 on success
// see: https://bugs.php.net/bug.php?id=50921
header('HTTP/1.0 500 Internal Server Error');

require_once('include/Unit.class.php');

/*

Add data to an entity.

Input Parameters:
- entity_id - the entity name to update
- data - the data to insert/update in as a json object of key/value pairs (column name->value)
- security_key - the required security key to update the entity data

e.g. /updateData.php?entity_id=test&data={%22a%22:28888888,%22b%22:2,%22c%22:3}&security_key=z

*/

require_once 'include/TableEntity.class.php';
require_once 'include/HttpUtil.class.php';
require_once 'include/JsonUtil.class.php';
require_once 'include/JsonConfig.class.php';

$request_method = $_SERVER['REQUEST_METHOD'];
if($request_method != 'GET' && $request_method != 'POST') {
    HttpUtil::send405('Request must be a GET or POST method');
    exit;
}

if(!array_key_exists('entity_id', $_REQUEST)) {
    HttpUtil::send400('Must specify an entity_id');
    exit;
}
$entity_id = $_REQUEST['entity_id'];

if(!array_key_exists('data', $_REQUEST)) {
    HttpUtil::send400('Must specify data');
    exit;
}
$dataJson = $_REQUEST['data'];

if(!array_key_exists('security_key', $_REQUEST)) {
    HttpUtil::send400('Must specify a security_key');
    exit;
}
$security_key = $_REQUEST['security_key'];

$config = JsonConfig::getInstance();

try {
    // TODO need a factory to create this, only support TableEnity for now
    $entity = new TableEntity($entity_id, $config);
    $entity->canUpdate($security_key);
    // parse data into associative array
    $data = JsonUtil::parseJson($dataJson);
    $entity->upsert($data);
    // success!
    header('HTTP/1.0 200 OK');

} catch(EntitySecurityException $e) {
    HttpUtil::send403("Unable to update entity: " . $e->getMessage());
} catch(EntityException $e) {
    HttpUtil::send400("Unable to update entity: " . $e->getMessage());
} catch(JsonParseException $e) {
    HttpUtil::send400("Unable to parse data as JSON: ". $e->getMessage() .":". $dataJson);
} catch(Exception $e) {
    HttpUtil::send500("Unable to update entity due to unexpected error: " . $e->getMessage());
}

?>
