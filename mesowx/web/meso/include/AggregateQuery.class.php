<?php

require('Unit.class.php');

class AggregateQuery {

    public $sql;

    protected $spec;

    function __construct( AggregateQuerySpec $spec, DBHelper $dbHelper ) {
        $this->spec = $spec;
        $this->dbHelper = $dbHelper;
        $this->dateTimeColumnQuoted = $this->quote($spec->dateTimeColumn);
        $this->tableNameQuoted = $this->quote($spec->table);
        $this->build();
    }

    protected function build() {
        $this->sql = "select \n"
            . $this->buildSelects() ."\n"
            . $this->buildFrom() ."\n"
            . $this->buildWhere() ."\n"
            . $this->buildGroupBy() ."\n"
            . $this->buildOrderBy();
        $limit = $this->buildLimit();
        if( $limit ) $this->sql .= "\n$limit";
    }

    protected function buildSelects() {
        $selects = array();
        // return the group value if grouped and not returning a single group
        if($this->isGrouped() && !$this->isSingleGroup()) {
            $selects[] = $this->buildGroupSelect();
        }
        foreach( $this->spec->data as $data ) {
            $selects[] = $this->buildFieldSelect($data);
        }
        return join(",\n", $selects );
    }

    protected function buildGroupSelect() {
        $groupSelect = NULL;
        $type = $this->spec->group->type;
        $value = $this->spec->group->value;
        if($type == GroupType::groups || $type == GroupType::seconds ) {
            $groupSelect = "{$this->buildSecondsGroup()} * {$this->getSecondsGroupSlice()}";
        } else if($type == GroupType::days) {
            // FIXME this is mysql-specific
            $groupDayOfYear = "{$this->buildDayOfYearGroup()} * $value - ". ($value-1);
            $groupSelect = "unix_timestamp(concat(makedate({$this->buildYearGroup()}, $groupDayOfYear), ' 00:00:00'))";
        } else if($type == GroupType::months) {
            // FIXME this is mysql-specific
            $groupMonth = "{$this->buildMonthGroup()} * $value - ". ($value-1);
            $groupSelect = "unix_timestamp(concat({$this->buildYearGroup()}, '-', $groupMonth, '-01 00:00:00'))";
        } else if($type == GroupType::years) {
            // FIXME this is mysql-specific
            $groupYear = "{$this->buildYearGroup()} * $value - ". ($value-1);
            $groupSelect = "unix_timestamp(concat($groupYear, '-01-01 00:00:00'))";
        } else {
            throw new Exception("Unsupporting group type: $type");
        }
        return UnitConvert::getSqlFormula($groupSelect, Unit::s, $this->spec->group->unit);
    }

    protected function buildFieldSelect($data) {
        $field = $data->field;
        $agg = $data->agg;
        $unit = $data->unit;
        $decimals = $data->decimals;

        $select = $this->quote($field);
        if( $this->isGrouped() ) {
            $select = "$agg($select)";
        }
        $select = $this->buildUnitConversion($select, $field, $unit);
        $alias = $this->buildDataSelectAlias($field, $agg);
        if($decimals !== NULL) {
            $select = "round($select, $decimals) $alias";
        }
        return $select;
    }

    protected function buildUnitConversion($value, $field, $unit) {
        if( $unit == NULL ) {
            return $value;
        }
        $columnUnit = $this->spec->entityConfig['columns'][$field]['unit'];
        return UnitConvert::getSqlFormula($value, $columnUnit, $unit);
    }

    protected function buildDataSelectAlias($baseAlias, $agg) {
        $alias = $baseAlias;
        if( $this->isGrouped() ) {
            $alias .= "_$agg";
        }
        return $alias;
    }

    protected function buildFrom() {
        return "from {$this->tableNameQuoted}";
    }

    protected function buildWhere() {
        $where = array();
        $start = $this->spec->start;
        $end = $this->spec->end;
        if( $start != NULL ) {
            $where[] = "{$this->dateTimeColumnQuoted} >= $start";
        }
        if( $end != NULL ) {
            $where[] = "{$this->dateTimeColumnQuoted} <= $end";
        }
        return 
            count($where) > 0 
                ? "where " . join(" and ", $where) . "\n"
                : "";
    }

    protected function buildGroupBy() {
        if( $this->isGrouped() && !$this->isSingleGroup() ) {
            return "group by " . $this->buildGroup() . "\n";
        }
        return "";
    }

    protected function buildGroup() {
        if( $this->isGrouped() ) {
            $type = $this->spec->group->type;
            if($type == GroupType::groups || $type == GroupType::seconds ) {
                return $this->buildSecondsGroup();
            } else if($type == GroupType::days) {
                return $this->buildYearGroup() .", ". $this->buildDayOfYearGroup();
            } else if($type == GroupType::months) {
                return $this->buildYearGroup() .", ". $this->buildMonthGroup();
            } else if($type == GroupType::years) {
                return $this->buildYearGroup();
            }
        }
        return NULL;
    }

    protected function buildSecondsGroup() {
        $slice = $this->getSecondsGroupSlice();
        // FIXME floor is mysql-specific
        return "floor({$this->dateTimeColumnQuoted} / $slice)";
    }

    protected function getSecondsGroupSlice() {
        $value = $this->spec->group->value;
        // groups
        if( $this->spec->group->type == GroupType::groups ) {
            $start = $this->spec->start;
            $end = $this->spec->end;
            // the sub-select for the min/max is an SQLite query optimization
            // http://www.sqlite.org/optoverview.html#minmax
            $start = ($start == NULL) ? $this->buildSubSelect( "min({$this->dateTimeColumnQuoted})" ) : $start;
            $end = ($end == NULL) ? $this->buildSubSelect( "max({$this->dateTimeColumnQuoted})" ) : $end;
            // i.e. cast((dateTime / (select (max(dateTime) - min(dateTime)) / 5.0 from archive) ) as int)
            //$slice = "(select ($end - $start) / cast($value as real) from {$this->tableNameQuoted})";
            // FIXME cast: sqlite uses REAL, mysql uses decimal
            return "(($end - $start) / cast($value as decimal))";
        }
        // seconds
        else {
            return $value;
        }
    }

    protected function buildGroupSlice() {
        return $slice;
    }

    // FIXME this is mysql-specific
    protected function buildYearGroup() {
        $group = "year(from_unixtime({$this->dateTimeColumnQuoted}))";
        if($this->spec->group->type == GroupType::years && $this->spec->group->value !== 1) {
            $group = "ceil($group / {$this->spec->group->value})";
        }
        return $group;
    }

    // FIXME this is mysql-specific
    protected function buildMonthGroup() {
        $group = "month(from_unixtime({$this->dateTimeColumnQuoted}))";
        if($this->spec->group->type == GroupType::months && $this->spec->group->value !== 1) {
            $group = "ceil($group / {$this->spec->group->value})";
        }
        return $group;
    }

    // FIXME this is mysql-specific
    protected function buildDayOfYearGroup() {
        $group = "dayofyear(from_unixtime({$this->dateTimeColumnQuoted}))";
        if($this->spec->group->type == GroupType::days && $this->spec->group->value !== 1) {
            $group = "ceil($group / {$this->spec->group->value})";
        }
        return $group;
    }

    protected function buildSubSelect($expression) {
        return "(select $expression from {$this->tableNameQuoted})";
    }

    protected function buildOrderBy() {
        // always ordered by dateTime for now
        return "order by {$this->dateTimeColumnQuoted} {$this->spec->order}";
    }

    protected function buildLimit() {
        $limit = $this->spec->limit;
        return $limit ? "limit $limit" : NULL;
    }

    protected function isGrouped() {
        return $this->spec->isGrouped();
    }

    protected function isSingleGroup() {
        return $this->spec->group->isSingle();
    }

    protected function quote($identifier) {
        return $this->dbHelper->quoteIdentifier($identifier);
    }
}

?>
