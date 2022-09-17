# Installer for weewx-mesowx (MesoWX)
# Distributed under the terms of the GNU Public License (GPLv3)
# Copyright 2018 - 2020 by Glenn McKechnie
#
# https://github.com/glennmckechnie/weewx-mesowx

from setup import ExtensionInstaller
import random
import string


def loader():
    return MesowxInstaller()


class MesowxInstaller(ExtensionInstaller):
    def __init__(self):
        # generate security keys for access to RemoteSync database
        def random_password():
            chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
            size = 12
            return ''.join(random.choice(chars) for x in range(size, 30))
        arch_key = random_password()
        raw_key = random_password()

        super(MesowxInstaller, self).__init__(
            version='0.6.5',
            name='mesowx',
            description='Weather station console web front-end with'
                        ' real-time updating and dynamic charting.',
            author='Peter Finlay, modified for weewx installation'
                   'by Glenn McKechnie',
            author_email="<glenn.mckechnie@gmail.com>",
            archive_services='user.mesowx.RawService',
            config={
                'StdReport': {
                    'Mesowx': {
                        'HTML_ROOT': 'mesowx',
                        'skin': 'Mesowx',
                        'enable': 'True'}},
                'Mesowx': {
                    'loop_polling_interval': '60',
                    'Raw': {
                        'data_binding': 'mesowx_binding',
                        'data_limit': '48',
                        'skip_loop': '2'},
                    'RemoteSync': {
                        'archive_entity_id': 'weewx_archive',
                        'archive_security_key': arch_key,
                        'raw_entity_id': 'weewx_raw',
                        'raw_security_key': raw_key,
                        'remote_server_url': 'http://192.168.0.100/weewx/mesowx/meso/'}},
                'DataBindings': {
                    'mesowx_binding': {
                        'database': 'mesowx_mysql',
                        'table_name': 'raw',
                        'manager': 'weewx.manager.Manager',
                        'schema': 'user.mesowx.schema'}},
                'Databases': {
                    'mesowx_mysql': {
                        'database_type': 'MySQL',
                        'database_name': 'mesowx'}}},
            files=[('bin/user', ['bin/user/mesowx.py']),
                   ('skins/Mesowx', [
                    'skins/Mesowx/skin.conf',
                    'skins/Mesowx/js/ArchiveChart.js',
                    'skins/Mesowx/js/Compass.js',
                    'skins/Mesowx/js/Config-example.js',
                    'skins/Mesowx/js/Config.js.tmpl',
                    'skins/Mesowx/js/MesoWxApp.js',
                    'skins/Mesowx/js/MesoWxConsole.js',
                    'skins/Mesowx/js/mesowx.js',
                    'skins/Mesowx/js/MesoWxWindCompass.js',
                    'skins/Mesowx/js/RawChart.js.tmpl',
                    'skins/Mesowx/js/RealTimeChart.js',
                    'skins/Mesowx/js/WindCompass.js',
                    'skins/Mesowx/js/lib/d3-v3.5.17.min.js',
                    'skins/Mesowx/js/lib/highstock-v8.1.1.js',
                    'skins/Mesowx/js/lib/jquery-3.5.1.min.js',
                    'skins/Mesowx/js/lib/modules/exporting.js',
                    'skins/Mesowx/meso/data.php',
                    'skins/Mesowx/meso/stats.php',
                    'skins/Mesowx/meso/updateData.php',
                    'skins/Mesowx/meso/include/.htaccess',
                    'skins/Mesowx/meso/include/Agg.class.php',
                    'skins/Mesowx/meso/include/AggregateParameterParser.class.php',
                    'skins/Mesowx/meso/include/AggregateQuery.class.php',
                    'skins/Mesowx/meso/include/AggregateQuerySpec.class.php',
                    'skins/Mesowx/meso/include/config-example.json',
                    'skins/Mesowx/meso/include/config.json.tmpl',
                    'skins/Mesowx/meso/include/config-RemoteSync.json.tmpl',
                    'skins/Mesowx/meso/include/Entity.class.php',
                    'skins/Mesowx/meso/include/EntityRetentionPolicy.class.php',
                    'skins/Mesowx/meso/include/EntityRetentionPolicyFactory.class.php',
                    'skins/Mesowx/meso/include/HttpUtil.class.php',
                    'skins/Mesowx/meso/include/JsonConfig.class.php',
                    'skins/Mesowx/meso/include/JsonUtil.class.php',
                    'skins/Mesowx/meso/include/PDOConnectionFactory.class.php',
                    'skins/Mesowx/meso/include/TableEntity.class.php',
                    'skins/Mesowx/meso/include/Unit.class.php',
                    'skins/Mesowx/meso/include/WindowRetentionPolicy.class.php',
                    'skins/Mesowx/meso/js/AbstractHighstockChart.js',
                    'skins/Mesowx/meso/js/AbstractRealTimeRawDataProvider.js',
                    'skins/Mesowx/meso/js/AggregateDataProvider.js',
                    'skins/Mesowx/meso/js/ChangeIndicatedValue.js',
                    'skins/Mesowx/meso/js/MesoConsole.js',
                    'skins/Mesowx/meso/js/meso.js',
                    'skins/Mesowx/meso/js/PollingRealTimeRawDataProvider.js',
                    'skins/Mesowx/meso/js/SocketIoRealTimeRawDataProvider.js',
                    'skins/Mesowx/meso/js/StatsDataProvider.js',
                    'skins/Mesowx/style/mesowx.css',
                    'skins/Mesowx/README.html',
                    'skins/Mesowx/footnote.inc',
                    'skins/Mesowx/links.inc',
                    'skins/Mesowx/index.html.tmpl'])]
            )
