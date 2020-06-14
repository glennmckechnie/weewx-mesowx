<?php

require_once('Entity.class.php');
require_once('PDOConnectionFactory.class.php');

class TableEntity extends Entity {

    protected $db;

    // only number supported for now
    protected static $COLUMN_SQL_TYPES = array(
        'number' => 'real',
    );

    public function __construct($entityId, $config) {
        parent::__construct($entityId, $config);
        // XXX open connection lazily instead of on construction?
        $this->db = $this->openConnection();
    }

    public function openConnection() {
        $db_config = $this->config['dataSource'][$this->entityConfig['dataSource']];
        $db = PDOConnectionFactory::openConnection($db_config);
        return $db;
    }

    public function deleteRecordsBeforeDateTime($dateTime) {
        // XXX dateTime is for now assumed to be the primary key
        $pkColumn = $this->getPrimaryKeyColumn();
        $columns = $this->entityConfig['columns'];
        $pkUnit = $columns[$pkColumn]['unit'];
        // make sure the dateTime is converted to the appropriate unit
        $windowMin = UnitConvert::getSqlFormula($dateTime, Unit::s, $pkUnit);
        $table = $this->getTable();
        $deleteSql = "delete from $table where $pkColumn < $windowMin";
        $this->db->query($deleteSql);
    }

    public function upsert($data) {
        // wrap call to super in a db transaction
        $this->db->beginTransaction();
        try {
            parent::upsert($data);
            $this->db->commit();
        } catch(Exception $e) {
            // catch any exception and rollback the transaction
            $this->db->rollBack();
            throw $e;
        }
    }

    public function getTable() {
        return $this->entityConfig['tableName'];
    }

    public function getColumnConfigs() {
        return $this->entityConfig['columns'];
    }

    public function getColumnNames() {
        $columns = $this->getColumnConfigs();
        $columnNames = array_keys($columns);
        return $columnNames;
    }

    protected function performInsert($data) {

        $columns = $this->getColumnNames();

        // if we just have one row wrap it in an array for easier processing
        // it's assumed to be one row when the first item isn't an array
        if(!is_array(current($data))) {
            $data = array($data);
        }
        // get the keys that are the intersection of columns in the data and defined for the entity
        // use the first entry in the array if more than one (the rest MUST match)
        $insertColumns = array_values(array_intersect(array_keys($data[0]), $columns));

        // TODO how to handle this? is it an error? null missing values?
        /*if( count($insertColumns) !== count($columns) ) {
            echo "There are missing columns";
        }*/

        $table = $this->getTable();
        $insertSql = self::buildInsertSql($this->db, $table, $insertColumns);

        try {
            self::executeInsert($this->db, $insertSql, $insertColumns, $data);
        } catch(PDOException $e) {
            // table doesn't exist eror code: 42S02
            if($e->getCode() == '42S02') {
                // attempt to create the table and retry
                $this->createTable();
                self::executeInsert($this->db, $insertSql, $insertColumns, $data);
            } else {
                // re-throw all other errors encountered
                // XXX wrap in EntityConfigurationException instead?
                throw $e;
            }
        }
    }

    protected static function buildInsertSql($db, $table, $insertColumns) {

        // wrap column names in quotes
        $quoted_column_names = $db->quoteIdentifiers($insertColumns);

        $sql = "insert into $table(". implode(',', $quoted_column_names) .") values (";
        // create ? binding placeholders for each value
        $sql .= implode(',', array_fill(0, count($insertColumns), '?')) . ")";

        return $sql;
    }

    protected static function executeInsert($db, $sql, $insertColumns, $data) {

        $query = $db->prepare($sql);

        foreach($data as $record) {

            $insert_data = array_intersect_key($record, array_flip($insertColumns));

            if(count($insert_data) !== count($insertColumns)) {
                throw new EntityException('All records in the request must have at least the same columns');
            }

            $query->execute(array_values($insert_data));
        }
    }

    // FIXME making this public for now, really should be made abstract on the interface (e.g. autoCreate())
    public function createTable() {
        $table = $this->getTable();
        $columns = $this->entityConfig['columns'];
        $primaryKeyColumn = $this->getPrimarykeyColumn();
        $createTableSql = self::buildCreateTableSql($this->db, $table, $columns, $primaryKeyColumn);
        $this->db->exec($createTableSql);
    }

    protected static function buildCreateTableSql($db, $table, $columns, $primaryKeyColumn) {
        // create the SQL for each column in an array
        $columnSql = array();
        foreach($columns as $columnName => $columnDef) {
            $quotedColName = $db->quoteIdentifier($columnName);
            $typeDef = array_key_exists('type', $columnDef) ? $columnDef['type'] : NULL;
            $typeSql = self::getSqlType($typeDef);
            if(!$typeSql) {
                throw new EntityConfigurationException("Invalid type defined for column '$columnName' of entityId '$this->entityId': '$typeDef'");
            }
            $columnSql[] = "$quotedColName $typeSql";
        }
        // add the primary key (for now required)
        $quotedPrimaryKey = $db->quoteIdentifier($primaryKeyColumn);
        $columnSql[] = "primary key ($quotedPrimaryKey)";
        $columnsSql = join(', ', $columnSql);
        // i.e. "create table $table (`dateTime` real, `outTemp` real, primary key (`dateTime`))"
        $createTableSql = "create table $table ($columnsSql);";

        return $createTableSql;
    }

    public function getPrimaryKeyColumn() {
        // for now a primary key column must be specified
        $primaryKey = $this->entityConfig['constraints']['primaryKey'];
        if(!$primaryKey) {
            throw new Exception("Entity must define a primaryKey constraint");
        }
        if(!array_key_exists($primaryKey, $this->entityConfig['columns'])) {
            throw new Exception("Primary key column $primaryKey is undenfined");
        }
        return $primaryKey;
    }

    protected static function getSqlType($columnDefType) {
        if($columnDefType === NULL) $columnDefType = 'number';
        $sqlType = self::$COLUMN_SQL_TYPES[$columnDefType]; 
        return $sqlType;
    }

}

?>
