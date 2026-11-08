==============================================
Keck Cosmic Web Imager Data Reduction Pipeline
==============================================

This pipeline is the official DRP for the Keck Cosmic Web Imager at the W. M. 
Keck Observatory. It is built on the 
`KeckDRPFramework <https://github.com/Keck-DataReductionPipelines/KeckDRPFramework>`_,
and is a port of the old 
`IDL pipeline <https://github.com/Keck-DataReductionPipelines/KcwiDRP>`_.

The pipeline has only been thoroughly tested on MacOS, Ubuntu, and CentOS, although it
should run smoothly on any unix-like system that runs Python. Unfortunately, Windows 
is not currently supported.

01-Apr-2021

Documentation
-------------

Documentation for this project is maintained with ReadTheDocs at the following link:

`https://kcwi-drp.readthedocs.io`


.. image:: https://readthedocs.org/projects/kcwi-drp/badge/?version=latest
   :target: https://kcwi-drp.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

Tests
-----

Status of tests:
`<https://travis-ci.com/github/Keck-DataReductionPipelines/KCWI_DRP>`_


.. image:: https://travis-ci.com/Keck-DataReductionPipelines/KCWI_DRP.svg?branch=master
   :target: https://travis-ci.com/Keck-DataReductionPipelines/KCWI_DRP


KCWIKit fork
------------

This repository is the fork of the official DRP maintained alongside
`KCWIKit <https://github.com/yuanzeding/kcwi>`_. Relative to the official
1.1.1 release it adds sine clock-pattern subtraction, a flat-field priority
list, configurable interpolation orders and DAR options (``DAR_wref``,
``DAR_apply``), red-channel cosmic-ray masks from a comparison of frames
(``crmsk``, ``extra_crr``), a protection mask that keeps astroscrappy from
cleaning bright variable sources (``bcrmsk``), camera-specific saturation
levels and the partial-run stages ``-st ff`` / ``-st cr``. All options are
set in ``kcwidrp/configs/kcwi.cfg``; the full list with dates is in
``changelog.txt`` (section "KCWIKit fork"), and the reduction workflow is
described in the KCWIKit documentation
(`blue <https://github.com/yuanzeding/kcwi/blob/dev/kcwikit/docs/Running_blue_DRP.md>`_,
`red <https://github.com/yuanzeding/kcwi/blob/dev/kcwikit/docs/Running_red_DRP.md>`_).

Some of these features have not been tested beyond the data they were
written for; please report problems through the KCWIKit issue tracker.

Dependencies
------------

Please see 'Installing KCWIDRP' in the documentation above for details about
dependencies and how to satisfy them. 



Developed by Luca Rizzi, Don Neill, Max Brodheim (04/2021)
