.. Django Q documentation master file, created by
   sphinx-quickstart on Fri Jun 26 22:18:36 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Django Q
====================
Django Q is a native Django task queue, scheduler and worker application using Python multiprocessing.

.. note::
    Django Q used to be unmainainted. A new fork was created called Django Q2. The owner of the Django Q2 repo has since been added to the Django Q repo and the package are now in sync.


Features
--------

-  Multiprocessing worker pools
-  Asynchronous tasks
-  Scheduled, cron and repeated tasks
-  Signed and compressed packages
-  Failure and success database or cache
-  Result hooks, groups and chains
-  Django Admin integration
-  PaaS compatible with multiple instances
-  Multi cluster monitor
-  Redis, IronMQ, SQS, MongoDB or ORM
-  Rollbar and Sentry support


Django Q is tested with: Python 3.8, 3.9, 3.10, 3.11 and 3.12. Works with Django 3.2.x, 4.1.x, 4.2.x and 5.0.x

Currently available in English, German and French.

Contents:

.. toctree::
   :maxdepth: 2

    Installation <install>
    Configuration <configure>
    Brokers <brokers>
    Tasks <tasks>
    Groups <group>
    Iterable <iterable>
    Chains <chain>
    Schedules <schedules>
    Cluster <cluster>
    Monitor <monitor>
    Admin <admin>
    Errors <errors>
    Signals <signals>
    Architecture <architecture>
    Examples <examples>

* :ref:`genindex`
