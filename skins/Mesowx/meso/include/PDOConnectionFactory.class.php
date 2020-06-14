<?php

class PDOConnectionFactory {

    public static function openConnection( $dbConfig ) {
        $type = $dbConfig['type'];
        switch($type) {
            case 'mysql':
                $db = self::openMySQLConnection($dbConfig);
                break;
            case 'sqlite':
                $db = self::openSQLiteConnection($dbConfig);
                break;
            default:
                throw new RuntimeException("Unsupported data source type: $type");
        }
        // this will make db errors to be exceptions
        $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION); 
        return $db;
    }

    private static function openMySQLConnection( $dbConfig ) {
        $host = $dbConfig['host'];
        $user = $dbConfig['user'];
        $password = $dbConfig['password'];
        $database = $dbConfig['database'];
        $port = '3306';
        if(array_key_exists('port', $dbConfig)) {
            $port = $dbConfig['port'];
        }
        return new MySQLPDOHelper("mysql:host=$host;port=$port;dbname=$database", $user, $password);
    }

    private static function openSQLiteConnection( $dbConfig ) {
        $file = $dbConfig['file'];
        return new SQLitePDOHelper("sqlite:$file");
    }
}

interface DBHelper {
    
    function quoteIdentifier($identifier);
    
    function quoteIdentifiers($identifiers);
}

abstract class AbstractDBHelper extends PDO implements DBHelper {

    public function quoteIdentifiers($identifiers) {
        $quotedIdentifiers = array_map(function($identifier) {
            return $this->quoteIdentifier($identifier);
        }, $identifiers);
        return $quotedIdentifiers;
    }
}

class MySQLPDOHelper extends AbstractDBHelper implements DBHelper {

    const IDENTIFIER_QUOTE = '`';
    
    public function quoteIdentifier($column) {
        return self::IDENTIFIER_QUOTE . $column . self::IDENTIFIER_QUOTE;
    }
}

class SQLitePDOHelper extends AbstractDBHelper implements DBHelper {

    const IDENTIFIER_QUOTE = '"';
    
    public function quoteIdentifier($column) {
        return self::IDENTIFIER_QUOTE . $column . self::IDENTIFIER_QUOTE;
    }
}

?>
