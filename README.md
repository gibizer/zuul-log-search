Tool to search the build results and log files of a Zuul deployment

Install
=======

This tool depends on [``ripgrep``](https://github.com/BurntSushi/ripgrep) a 
fast and efficient ``grep`` clone written in Rust. So you have to first install
``ripgrep``:

```shell
$ sudo apt install ripgrep
```

Then you can install zuul-log-search:

```shell
$ pip install git+http://github.com/gibizer/zuul-log-search  
```

Usage
=====

You can search for builds, search in the logs of such builds, or try to
classify builds by matching them to predefined searches.

```shell
usage: Search Zuul CI results

positional arguments:
  {build-show,build,log,storedsearch,match,cache-show,cache-purge}
    build-show          Show the metadata of a specific build
    build               Search for builds
    log                 Search the logs of the builds
    storedsearch        Run a search defined in the configuration. The command
                        line args can be used to fine tune the stored search
                        where the configuration does not specify a given
                        parameter. If a parameter is specified by the stored
                        search then the corresponding command line parameter
                        will be ignored.
    match               Match builds with stored searches.
    cache-show          Show information of the local build cache.
    cache-purge         Reduce the size of the local build cache.

optional arguments:
  -h, --help            show this help message and exit
  --debug               Print debug logs
  --zuul-api-url ZUUL_API_URL
                        The API url of the Zuul deployment to use. Defaulted
                        to the OpenDev Zuul (https://zuul.opendev.org/api)
  --log-store-dir LOG_STORE_DIR
                        The local directory to download the logs to. Defaulted
                        to .logsearch/
  --config-dir CONFIG_DIR
                        The local directory storing config files and stored
                        queries. Defaulted to .logsearch.conf.d/
  --tenant TENANT       The name of the tenant in the Zuul installation.
                        Defaulted to 'openstack'
```

Searching for builds
--------------------
Search for the last 10 failed builds in openstack/nova on branch master
filtering for only the voting jobs:
```shell
$ logsearch build --project openstack/nova --branch master --result FAILURE --voting
+----------------------------------+---------------------+-----------------------------+---------+-----------------------------------+
| uuid                             | finished            | job                         | result  | review                            |
+----------------------------------+---------------------+-----------------------------+---------+-----------------------------------+
| 885c1872b9e74850a1311ee371b3d96c | 2021-05-29T09:13:52 | nova-grenade-multinode      | FAILURE | https://review.opendev.org/786348 |
| c68a7d516f274227b09090b4bbc3d4e0 | 2021-05-29T08:13:06 | nova-tox-functional-py38    | FAILURE | https://review.opendev.org/786348 |
| 0db18e971c20424d8f526cbe9b99cf46 | 2021-05-29T09:24:19 | nova-next                   | FAILURE | https://review.opendev.org/786348 |
| 3fa2ec000f6b45e7886295144c1751b7 | 2021-05-29T09:30:30 | nova-multi-cell             | FAILURE | https://review.opendev.org/786348 |
| 47cb5fac671d426280ecea3344f346c3 | 2021-05-29T08:46:33 | neutron-tempest-linuxbridge | FAILURE | https://review.opendev.org/786348 |
| 34e923464e5344188e8477d752c6f1b0 | 2021-05-29T09:19:02 | nova-ceph-multistore        | FAILURE | https://review.opendev.org/786348 |
| 6c1a8e0bcaee4a7a9eee72c7ee4d356e | 2021-05-29T08:49:25 | tempest-integrated-compute  | FAILURE | https://review.opendev.org/786348 |
| 5bd42a87bb6e4f739eb7479347a6a8eb | 2021-05-29T04:28:17 | nova-grenade-multinode      | FAILURE | https://review.opendev.org/786348 |
| 27a70ec146fb48e8b4fb74acde91aa38 | 2021-05-29T03:37:01 | nova-tox-functional-py38    | FAILURE | https://review.opendev.org/786348 |
| 24ff9f3f4d124a989bd895f48a4b8cc9 | 2021-05-29T04:34:26 | nova-next                   | FAILURE | https://review.opendev.org/786348 |
+----------------------------------+---------------------+-----------------------------+---------+-----------------------------------+
```

Filtering builds
----------------
You can filter the builds from many aspects: project, branch, job name, result,
pipeline, voting status or review ID and patch set number.

You can limit the search result by the number of builds using the ``--limit``
parameter or by number of days since the build's start date using the
``--days`` parameter.

See ``logsearch build --help`` for details.

Searching in the logs of the builds
-----------------------------------
Search the recent failed nova-next job runs for a certain errors in the 
nova-compute logs: 
```shell
$ logsearch log --project openstack/nova --branch master --job nova-next --result FAILURE --file controller/logs/screen-n-cpu.txt 'ERROR .* iscsiadm -m discoverydb -o show -P 1'
Found matching builds:
+----------------------------------+---------------------+-----------+---------+-----------------------------------+
| uuid                             | finished            | job       | result  | review                            |
+----------------------------------+---------------------+-----------+---------+-----------------------------------+
| 0db18e971c20424d8f526cbe9b99cf46 | 2021-05-29T09:24:19 | nova-next | FAILURE | https://review.opendev.org/786348 |
| 24ff9f3f4d124a989bd895f48a4b8cc9 | 2021-05-29T04:34:26 | nova-next | FAILURE | https://review.opendev.org/786348 |
| 7e6f4bee6d1f4d2d93a5cd5ca1622a1c | 2021-05-28T17:53:15 | nova-next | FAILURE | https://review.opendev.org/793619 |
| e37a107c8b2d42b5b0424f9480d07610 | 2021-05-28T14:26:39 | nova-next | FAILURE | https://review.opendev.org/791504 |
| 5a1275e29ace41df9db8dc42fb5bbd3b | 2021-05-28T14:13:45 | nova-next | FAILURE | https://review.opendev.org/791505 |
| c3dff1b2c7f447b1b7d658d090b15c36 | 2021-05-28T12:57:28 | nova-next | FAILURE | https://review.opendev.org/793219 |
| 794aba9010a549a69c49a928bc678366 | 2021-05-27T17:01:06 | nova-next | FAILURE | https://review.opendev.org/786348 |
| ad572fb9de244a089b2ec302f7b95646 | 2021-05-27T12:16:43 | nova-next | FAILURE | https://review.opendev.org/786348 |
| 9900d0bb9a2f4693bf9fbd7c015d94e6 | 2021-05-26T18:08:26 | nova-next | FAILURE | https://review.opendev.org/773641 |
| 36e4d5a4b95b4879b5bac7c7507a83b8 | 2021-05-26T18:50:53 | nova-next | FAILURE | https://review.opendev.org/773644 |
+----------------------------------+---------------------+-----------+---------+-----------------------------------+
Downloading logs:
0db18e971c20424d8f526cbe9b99cf46: controller/logs/screen-n-cpu.txt
24ff9f3f4d124a989bd895f48a4b8cc9: controller/logs/screen-n-cpu.txt
7e6f4bee6d1f4d2d93a5cd5ca1622a1c: controller/logs/screen-n-cpu.txt
e37a107c8b2d42b5b0424f9480d07610: controller/logs/screen-n-cpu.txt
5a1275e29ace41df9db8dc42fb5bbd3b: controller/logs/screen-n-cpu.txt
c3dff1b2c7f447b1b7d658d090b15c36: controller/logs/screen-n-cpu.txt
794aba9010a549a69c49a928bc678366: controller/logs/screen-n-cpu.txt
ad572fb9de244a089b2ec302f7b95646: controller/logs/screen-n-cpu.txt
9900d0bb9a2f4693bf9fbd7c015d94e6: controller/logs/screen-n-cpu.txt
36e4d5a4b95b4879b5bac7c7507a83b8: controller/logs/screen-n-cpu.txt
Searching logs:
0db18e971c20424d8f526cbe9b99cf46:32078:May 29 08:46:26.211445 ubuntu-focal-rax-iad-0024867410 nova-compute[108320]: ERROR os_brick.initiator.connectors.iscsi Command: iscsiadm -m discoverydb -o show -P 1

7e6f4bee6d1f4d2d93a5cd5ca1622a1c:25141:May 28 17:18:52.785871 ubuntu-focal-inap-mtl01-0024862740 nova-compute[108047]: ERROR os_brick.initiator.connectors.iscsi Command: iscsiadm -m discoverydb -o show -P 1

794aba9010a549a69c49a928bc678366:32803:May 27 16:26:10.920760 ubuntu-focal-rax-dfw-0024846381 nova-compute[108609]: ERROR os_brick.initiator.connectors.iscsi Command: iscsiadm -m discoverydb -o show -P 1

9900d0bb9a2f4693bf9fbd7c015d94e6:34777:May 26 17:39:54.850977 ubuntu-focal-ovh-gra1-0024830767 nova-compute[107587]: ERROR os_brick.initiator.connectors.iscsi Command: iscsiadm -m discoverydb -o show -P 1

36e4d5a4b95b4879b5bac7c7507a83b8:31638:May 26 18:06:49.029138 ubuntu-focal-ovh-bhs1-0024830866 nova-compute[110234]: ERROR os_brick.initiator.connectors.iscsi Command: iscsiadm -m discoverydb -o show -P 1
```

Note that this command download the logfile to the local cache directory so 
this might take a while. However, repeated searches in the same logs will use
the local cache.

Stored searches
---------------
If you have searches that you want to run regularly you can define it in a
configuration file with an alias and then use the ``storedsearch`` command in
the command line to invoke the stored query. See
[example](.logsearch.conf.d/conf_sample.yaml).

When running stored searches you can fine tune the query with same CLI
parameters than in normal logsearch. But note that only those parameters can
be provided via the CLI that is not defined in the stored search. If a
parameter is provided via the CLI that is also defined in the config, the CLI
value will be ignored.

Classifying build results based on stored searches
--------------------------------------------------
If you have a bunch of stored queries and a list of build results, then the
``match`` command can be used to find out if one or more stored search matches
with the builds. For example if you have stored searches for logs that is
unique for a known bug then you can use this subcommand to classify recent
build failures and see if they are a re-occurrence of a known bug.

The ``match`` command takes the same parameters as the ``build`` command to
query builds then it iterates through all the stores searches to see which
matches the build first based on the build parameters (e.g. job name,
project...) then for the matching ones runs the log searching logic.

For example the following command tries to figure out the reason of the failed
job run in review https://review.opendev.org/c/openstack/nova/+/792394/22
```shell
$ logsearch match --review 792394 --patchset 22 --result FAILURE
Found builds to match:
+----------------------------------+---------------------+----------------+----------+--------+---------------------------------+
| uuid                             | finished            | project        | pipeline | branch | job                             |
+----------------------------------+---------------------+----------------+----------+--------+---------------------------------+
| bf050b127c4d4ac7ba477d97d1c97dae | 2021-08-21T13:04:48 | openstack/nova | check    | master | openstack-tox-lower-constraints |
+----------------------------------+---------------------+----------------+----------+--------+---------------------------------+
Matching stored searches for build bf050b127c4d4ac7ba477d97d1c97dae
bf050b127c4d4ac7ba477d97d1c97dae: Search bug-1936849-test_stop_serial_proxy matched build query.
bf050b127c4d4ac7ba477d97d1c97dae:.logsearch/bf050b127c4d4ac7ba477d97d1c97dae/job-output.txt:26054:2021-08-21 13:02:33.513129 | ubuntu-bionic |     b'  File "/home/zuul/src/opendev.org/openstack/nova/nova/tests/unit/virt/hyperv/test_serialproxy.py", line 70, in test_stop_serial_proxy'
bf050b127c4d4ac7ba477d97d1c97dae:.logsearch/bf050b127c4d4ac7ba477d97d1c97dae/job-output.txt:28287:2021-08-21 13:03:25.744852 | ubuntu-bionic |     b'  File "/home/zuul/src/opendev.org/openstack/nova/nova/tests/unit/virt/hyperv/test_serialproxy.py", line 70, in test_stop_serial_proxy'

bf050b127c4d4ac7ba477d97d1c97dae: Search bug-1936849-test_stop_serial_proxy matched signature!
bf050b127c4d4ac7ba477d97d1c97dae: Search bug-1823251 matched build query.


+----------------------------------+---------------------+----------------+----------+--------+---------------------------------+----------------------------------------+
| uuid                             | finished            | project        | pipeline | branch | job                             | matching searches                      |
+----------------------------------+---------------------+----------------+----------+--------+---------------------------------+----------------------------------------+
| bf050b127c4d4ac7ba477d97d1c97dae | 2021-08-21T13:04:48 | openstack/nova | check    | master | openstack-tox-lower-constraints | ['bug-1936849-test_stop_serial_proxy'] |
+----------------------------------+---------------------+----------------+----------+--------+---------------------------------+----------------------------------------+
```

Or you can try to classify recent failed builds on the gate:
```shell
$ logsearch match --job-group nova-devstack --project openstack/nova --branch master --pipeline gate --result FAILURE  --voting
# ...snip long output of matching logs
+----------------------------------+---------------------+-----------------------------------+----------------------------+-------------------------------------------------------------------------------------------------------------+
| uuid                             | finished            | review                            | job                        | matching searches                                                                                           |
+----------------------------------+---------------------+-----------------------------------+----------------------------+-------------------------------------------------------------------------------------------------------------+
| f75060a95aea416bb5474fbda4428fae | 2021-08-20T22:51:44 | https://review.opendev.org/802918 | nova-multi-cell            | ['bug-xxx-virtual-interface-creation-timeout']                                                              |
| db22d92fefcf4819b1fa12c56cd0c3b7 | 2021-08-20T17:12:27 | https://review.opendev.org/796208 | tempest-integrated-compute | []                                                                                                          |
| fb2574989dcd41069df44b37fd74db01 | 2021-08-20T00:35:47 | https://review.opendev.org/804285 | tempest-ipv6-only          | ['bug-1931864']                                                                                             |
| 2f917c70d405484fb7f7d20c667f651d | 2021-08-20T00:33:44 | https://review.opendev.org/804285 | tempest-integrated-compute | ['bug-1931864']                                                                                             |
| a16c68692c57404c8270ac776de63a86 | 2021-08-18T16:07:33 | https://review.opendev.org/771363 | nova-multi-cell            | ['bug-xxx-virtual-interface-creation-timeout']                                                              |
| 8213711612a648a183193f7fedfbc08f | 2021-08-18T12:33:03 | https://review.opendev.org/764435 | tempest-integrated-compute | ['bug-1939108']                                                                                             |
| 1645c07b070a469fb64665cf090d7b5b | 2021-08-18T11:23:12 | https://review.opendev.org/803778 | tempest-integrated-compute | ['bug-1939108']                                                                                             |
| fdbda223dc10456db58f922b6435f680 | 2021-08-18T11:24:46 | https://review.opendev.org/803603 | nova-next                  | ['bug-xxx-metadata-request-timed-out.yaml', 'bug-1940425-port-down-in-test_live_migration_with_trunk.yaml'] |
| 0f71dbe7049f41578c69ae9c96b049f1 | 2021-08-07T13:49:05 | https://review.opendev.org/801285 | nova-multi-cell            | ['bug-xxx-virtual-interface-creation-timeout']                                                              |
| 806b1a4ad1fc4d1cb78bf55644d13781 | 2021-08-06T14:05:53 | https://review.opendev.org/801714 | nova-multi-cell            | ['bug-xxx-virtual-interface-creation-timeout']                                                              |
+----------------------------------+---------------------+-----------------------------------+----------------------------+-------------------------------------------------------------------------------------------------------------+
```

Configuration
=============
The ``logsearch.conf.d`` directory is searched for config files. The directory
location can be also provided via ``--config-dir`` command line parameter.
Every file with names ending in ``.yaml`` or ``.conf`` is read from the
directory as yaml data and the data are merged by the top level key.
So you can separate out different part of the configuration to different files.

Job groups
----------
Instead of listing multiple ``--job`` parameters in the command line to filter
for multiple jobs you can define job groups in the configuration assigning an
alias for a list of jobs and then you can use the ``--job-group`` parameter to
refer to the list of jobs with the alias.
See [example](.logsearch.conf.d/conf_sample.yaml).


Cache management
================
Most of the use cases of the tool requires downloading logs from Zuul. These
logs are cached in the directory under ``--cache-dir`` to avoid repeated
downloading. However, this means that this directory can grow to very big.
With the ``cache-show`` command you can get the size and other statistics of
the cache easily.

With the ``cache-purge`` the local cache size can be reduced either to builds
of the last N days, using the ``--days`` parameter, or to the latest builds
with a maximum total log size in GB,  using the ``--gb`` parameter.
