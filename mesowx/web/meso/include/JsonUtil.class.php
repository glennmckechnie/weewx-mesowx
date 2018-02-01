<?php

// TODO make this a JsonParser instead of static util
class JsonUtil {

    /**
     * Parse a JSON string into a associative array.
     */
    public static function parseJson($jsonString) {
        $data = json_decode($jsonString, true);
        $jsonError = json_last_error();
        if($jsonError !== JSON_ERROR_NONE) {
            throw new JsonParseException(self::getJsonErrorCodeMessage($jsonError));
        }
        return $data;
    }

    public static function getJsonErrorCodeMessage($errorCode) {
        switch ($errorCode) {
            case JSON_ERROR_NONE:
                return 'No errors';
                break;
            case JSON_ERROR_DEPTH:
                return 'Maximum stack depth exceeded';
                break;
            case JSON_ERROR_STATE_MISMATCH:
                return 'Underflow or the modes mismatch';
                break;
            case JSON_ERROR_CTRL_CHAR:
                return 'Unexpected control character found';
                break;
            case JSON_ERROR_SYNTAX:
                return 'Syntax error, malformed JSON';
                break;
            case JSON_ERROR_UTF8:
                return 'Malformed UTF-8 characters, possibly incorrectly encoded';
                break;
            default:
                return 'Unknown error';
                break;
        }
    }
}

class JsonParseException extends Exception { }

?>
