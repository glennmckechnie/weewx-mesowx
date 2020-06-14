<?php

class HttpUtil {

    public static function sendPreventCacheHeaders() {
        // see http://php.net/manual/en/function.header.php and http://support.microsoft.com/kb/234067
        header("Cache-Control: no-cache, must-revalidate"); // HTTP/1.1
        header("Expires: Sat, 26 Jul 1997 05:00:00 GMT"); // Date in the past
        header("Pragma: no-cache");
    }

    public static function send405($message) {
        self::sendError("HTTP/1.0 405 Method Not Allowed", $message);
    }

    public static function send400($message) {
        self::sendError("HTTP/1.0 400 Bad Request", $message);
    }

    public static function send403($message) {
        self::sendError("HTTP/1.0 403 Forbidden", $message);
    }

    public static function send500($message) {
        self::sendError("HTTP/1.0 500 Internal Server Error", $message);
    }

    private static function sendError($header, $message) {
        header($header);
        echo $message;
    }
}

?>
