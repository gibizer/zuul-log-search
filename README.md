Tool to search the build results and log files of a Zuul deployment

Install
=======

This tool depends on [``ripgrep``](https://github.com/BurntSushi/ripgrep) a 
fast and efficient ``grep`` clone written in Rust. So you have to first 
``ripgrep``:

```shell
$ sudo apt install ripgrep
```

Then you can install zool-log-serach:

```shell
$ pip install git+http://github.com/gibizer/zuul-log-search  
```

Usage
=====

You can either search for builds or search in the logs of such builds.

```shell
$ logseach --help
usage: Search Zuul CI results

positional arguments:
  {build-show,build,log}
    build-show          Show the metadata of a specific build
    build               Search for builds
    log                 Search the logs of the builds

optional arguments:
  -h, --help            show this help message and exit
  --debug               Print debug logs
  --zuul-api-url ZUUL_API_URL
                        The API url of the Zuul deployment to use.
                        Defaulted to the OpenDev Zuul (https://zuul.opendev.org/api)
  --log-store-dir LOG_STORE_DIR
                        The local directory to download the logs to.
                        Defaulted to .logsearch
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