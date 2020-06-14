<?php

class JsonConfig {

    private $parsedConfig;

    private static $instance = NULL;

    private static $DEFAULT_CONFIG_FILE = "include/config.json";

    private function __construct($configFile=NULL) {
        if( !$configFile ) $configFile = self::$DEFAULT_CONFIG_FILE;
        // TODO check if file exists and is readable
        $jsonString = file_get_contents($configFile);
        $jsonString = preg_replace("#(//.*)|(?s:/\*.*?\*/)#", '', $jsonString);
        $this->parsedConfig = json_decode($jsonString, true);
        if( json_last_error() !== JSON_ERROR_NONE ) {
            throw new RuntimeException("Unable to parse json config file: $configFile");
        }
    }

    public static function getInstance() {
        if( !self::$instance ) {
            self::$instance = new JsonConfig();
        }
        return self::$instance->parsedConfig;
    }
}

?>
