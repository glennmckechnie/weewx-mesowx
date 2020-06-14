<?php
class Unit {
    const f = "f"; // fahrenheit
    const c = "c"; // celsius

    const inHg = "inHg"; // inches of mercury
    const mb = "mb"; // millibar
    const mmHg = "mmHg"; // millimeters of mercury
    const hPa = "hPa"; // hectopascal
    const kPa = "kPa"; // kilopascal

    const in = "in"; // inches
    const mm = "mm"; // millimeters
    const cm = "cm"; // centimeters

    const inHr = "inHr"; // inches per hour
    const mmHr = "mmHr"; // millimeters per hour
    const cmHr = "cmHr"; // centimeters per hour
    /*const inDay = "inDay"; // inches per day
    const mmDay = "mmDay"; // millimeters per day
    const cmDay = "cmDay"; // centimeters per day*/

    const mph = "mph"; // miles per hour
    const kph = "kph"; // killometers per hour
    const knot = "knot";
    const mps = "mps"; // meters per second

    const deg = "deg"; // degrees

    const perc = "perc"; // perc

    const s = "s"; // seconds
    const ms = "ms"; // milliseconds
}

class UnitConvert {

    public static $FORMULA = array(

        // temperature
        Unit::f => array(
            Unit::c => "(5.0/9.0) * (#-32)"
        ),
        Unit::c => array(
            Unit::f => "(9.0/5.0) * # + 32"
        ),

        // pressure
        Unit::inHg => array(
            Unit::mb => "# * 33.86",
            Unit::mmHg => "# * 25.4",
            Unit::hPa => "# * 33.86",
            Unit::kPa => "# * 3.386"
        ),
        Unit::mb => array(
            Unit::inHg => "# * 0.0295333727",
            Unit::mmHg => "# * 0.750061683",
            Unit::hPa => "#",
            Unit::kPa => "# * 0.1"
        ),
        Unit::mmHg => array(
            Unit::inHg => "# * 0.039374592",
            Unit::mb => "# * 1.33322368",
            Unit::hPa => "# * 1.33322368",
            Unit::kPa => "# * 0.1333223684"
        ),
        Unit::hPa => array(
            Unit::inHg => "# * 0.0295333727",
            Unit::mb => "#",
            Unit::mmHg => "# * 0.750061683",
            Unit::kPa => "# * 0.1"
        ),
        Unit::kPa => array(
            Unit::inHg => "# * 0.295333727",
            Unit::mb => "# * 10",
            Unit::mmHg => "# * 7.50061683",
            Unit::hPa => "# * 10"
        ),  

        // length
        Unit::in => array(
            Unit::mm => "# * 25.4",
            Unit::cm => "# * 2.54"
        ),
        Unit::mm => array(
            Unit::in => "# * 0.0393700787",
            Unit::cm => "# * 0.1"
        ),
        Unit::cm => array(
            Unit::in => "# * 0.393700787",
            Unit::mm => "# * 10.0"
        ),

        // speed (small scale)
        Unit::inHr => array(
            Unit::mmHr => "# * 25.4",
            Unit::cmHr => "# * 2.54"
        ),
        Unit::mmHr => array(
            Unit::inHr => "# * 0.0393700787",
            Unit::cmHr => "# * 0.10"
        ),
        Unit::cmHr => array(
            Unit::inHr => "# * 0.393700787",
            Unit::mmHr => "# * 10.0"
        ),

        // speed (large scale)
        Unit::mph => array(
            Unit::kph => "# * 1.609344",
            Unit::knot => "# * 0.868976242",
            Unit::mps => "# * 0.44704"
        ),
        Unit::kph => array(
            Unit::mph => "# * 0.621371192",
            Unit::knot => "# * 0.539956803",
            Unit::mps => "# * 0.277777778"
        ),
        Unit::knot => array(
            Unit::mph => "# * 1.15077945",
            Unit::kph => "# * 1.85200",
            Unit::mps => "# * 0.514444444"
        ),
        Unit::mps => array(
        //bitbucket.org/lirpa/mesowx/issues/39/wrong-unit-conversion
            Unit::mph => "# * 2.23693629",
            Unit::knot => "# * 1.94384449",
            Unit::kph => "# * 3.6"
        ),

        // time
        Unit::s => array(
            Unit::ms => "# * 1000",
        ),
        Unit::ms => array(
            Unit::s => "# * 0.001",
        )
    );

    private static $conversionFunctions = array();

    private static $NO_CONVERT_FUNCTION;

    public static function getSqlFormula($value, $fromUnit, $toUnit) {
        if ($fromUnit == $toUnit || !$toUnit) {
            return $value;
        }
        $formula = self::$FORMULA[$fromUnit][$toUnit];
        return str_replace('#', $value, $formula);
    }

    public static function getConverter($fromUnit, $toUnit) {
        if ($fromUnit == $toUnit) {
            return self::getNoConvertFunction();
        }
        $functions =& self::$conversionFunctions;
        if (!array_key_exists($fromUnit, $functions)) {
            $functions[$fromUnit] = array();
        }
        $fromFunctions =& $functions[$fromUnit];
        if (!array_key_exists($toUnit, $fromFunctions)) {
            $formula = self::$FORMULA[$fromUnit][$toUnit];
            $functionBody = 'return '. str_replace('#', '$v', $formula) .';';
            $fromFunctions[$toUnit] = create_function('$v', $functionBody);
        }
        return $fromFunctions[$toUnit];
    }

    public static function convert($value, $fromUnit, $toUnit) {
        $convertFunction = self::getConverter($fromUnit, $toUnit);
        return $convertFunction($value);
    }

    private static function getNoConvertFunction() {
        if (!self::$NO_CONVERT_FUNCTION) {
            self::$NO_CONVERT_FUNCTION = function($v) {
                return $v;
            };
        }
        return self::$NO_CONVERT_FUNCTION;
    }
}
?>
