from keckdrpframework.primitives.base_primitive import BasePrimitive
from kcwidrp.primitives.kcwi_file_primitives import kcwi_fits_writer
import numpy as np
from astroscrappy import detect_cosmics
import os
from astropy.io import fits


def config_flag(config, name, default=False):
    """
    Read a boolean option from the instrument config.

    Values set on ``framework.config.instrument`` from a config *section*
    (``kcwi_config.RED['crmsk']``) arrive as strings, while values read as
    attributes are already converted, so accept both. ``'False'``, ``'0'``,
    ``'no'`` and ``'off'`` are False; a missing option returns ``default``.
    """
    value = getattr(config, name, None)
    if value is None:          # ConfigClass returns None for unknown options
        return default
    if isinstance(value, str):
        return value.split('#')[0].strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(value)


class RemoveCosmicRays(BasePrimitive):
    """
    Remove cosmic rays and generate a flag image recording their location.

    Two sources of cosmic-ray masks are supported:

    1. **astroscrappy** (default, and always for the blue camera). When the
       ``bcrmsk`` option is on and a protection mask
       ``<frame>_intf_bcrmsk.fits`` (1 = protect; made with
       ``kcwi_automask --bcrmsk`` / ``kcwi_masksky_ds9_bcrr``) exists, those
       pixels are passed to astroscrappy as ``inmask`` so that bright, variable
       sources (a QSO core) are not cleaned as cosmic rays.
    2. **a pre-computed mask** ``<frame>_crmsk.fits`` from ``kcrm_create_crmsk``
       (red camera only, ``crmsk = True``): flagged pixels are replaced by the
       scaled median of the other frames of the group (``MEDSCI`` extension).
       With ``extra_crr = True`` an astroscrappy pass follows to catch what the
       frame comparison missed, with the same protection mask as in (1).

    Updates the following FITS header keywords:

        * CRCLEAN: set to ``True`` if operation performed.
        * NCRCLEAN: set to the number of cosmic ray pixels cleaned.

    Uses the following configuration parameters:

        * saveintims: if set to ``True`` write out a CR cleaned version of image in \\*_crr.fits.  Defaults to ``False``.
        * CRR_MINEXPTIME - exposure time below which no CR cleaning is done.
        * CRR\\_\\* - see kcwi.cfg file for parameters controlling CR cleaning.
        * crmsk, extra_crr, bcrmsk - see above (booleans; strings 'True'/'False' accepted).

    Updates image in returned arguments with CR cleaned image and adds flags
    indicating where changes were made.

    """

    def __init__(self, action, context):
        BasePrimitive.__init__(self, action, context)
        self.logger = context.pipeline_logger

    # ------------------------------------------------------------------ helpers
    def _output_path(self, suffix):
        name = self.action.args.name.replace('.fits', suffix)
        return os.path.join(self.config.instrument.output_directory, name)

    def _read_noise(self, header):
        namps = header['NVIDINP']
        bsec, dsec, tsec, direc, amps, aoff = self.action.args.map_ccd
        read_noise = 0.
        if len(amps) != namps:
            self.logger.warning("Amp count disagreement!")
        for ia in amps:
            if 'BIASRN%d' % ia in header:
                read_noise += header['BIASRN%d' % ia]
            elif 'OSCNRN%d' % ia in header:
                read_noise += header['OSCNRN%d' % ia]
            else:
                read_noise += 3.
        return read_noise / float(namps)

    def _sigclip(self, header):
        """Sigma clip threshold for astroscrappy, set according to image type."""
        sigclip = self.config.instrument.CRR_SIGCLIP
        if 'FLATLAMP' in header['IMTYPE']:
            sigclip = 10. if self.action.args.nasmask else 7.
        if 'OBJECT' in header['IMTYPE'] and header['TTIME'] < 300.:
            sigclip = 10.
        return sigclip

    def _protection_mask(self, header):
        """
        Boolean inmask for astroscrappy (True = do not touch), or None.

        Read from <frame>_intf_bcrmsk.fits, written as uint8 with 1 = protect,
        when the bcrmsk option is on and the frame is a science frame.
        """
        if 'OBJECT' not in header['IMTYPE']:
            return None
        if not config_flag(self.config.instrument, 'bcrmsk', False):
            return None
        bcrmsk_path = self._output_path('_intf_bcrmsk.fits')
        if not os.path.isfile(bcrmsk_path):
            self.logger.info('No CR protection mask (%s) found'
                             % os.path.basename(bcrmsk_path))
            return None
        with fits.open(bcrmsk_path) as bcr:
            inmask = (bcr[0].data == 1)
        self.logger.info('CR protection mask %s: %d pixel(s) protected'
                         % (os.path.basename(bcrmsk_path), int(inmask.sum())))
        header['history'] = "%s protected from astroscrappy" % os.path.basename(bcrmsk_path)
        return inmask

    def _run_astroscrappy(self, header, inmask, label):
        """Run astroscrappy on the current image; flag and clean. Returns the pixel count."""
        read_noise = self._read_noise(header)
        sigclip = self._sigclip(header)
        kwargs = dict(
            inmask=inmask, gain=1.0, readnoise=read_noise,
            psffwhm=self.config.instrument.CRR_PSFFWHM,
            sigclip=sigclip,
            sigfrac=self.config.instrument.CRR_SIGFRAC,
            objlim=self.config.instrument.CRR_OBJLIM,
            fsmode=self.config.instrument.CRR_FSMODE,
            psfmodel=self.config.instrument.CRR_PSFMODEL,
            verbose=self.config.instrument.CRR_VERBOSE,
            sepmed=self.config.instrument.CRR_SEPMED,
            cleantype=self.config.instrument.CRR_CLEANTYPE)
        niter = getattr(self.config.instrument, 'CRR_NITER', None)
        if niter is not None:
            kwargs['niter'] = int(niter)

        mask, clean = detect_cosmics(self.action.args.ccddata.data, **kwargs)

        self.logger.info("Astroscrappy (%s): cleaned cosmic rays" % label)
        header['history'] = "Astroscrappy (%s): cleaned cosmic rays" % label
        header['history'] = \
            "Astroscrappy params: sigclip=%5.2f sigfrac=%5.2f objlim=%5.2f" % (
                sigclip, self.config.instrument.CRR_SIGFRAC,
                self.config.instrument.CRR_OBJLIM)
        header['history'] = \
            "Astroscrappy params: fsmode=%s psfmodel=%s psffwhm=%5.2f" % (
                self.config.instrument.CRR_FSMODE,
                self.config.instrument.CRR_PSFMODEL,
                self.config.instrument.CRR_PSFFWHM)
        header['history'] = "Astroscrappy params: sepmed=%s minexptime=%f" % (
            self.config.instrument.CRR_SEPMED,
            self.config.instrument.CRR_MINEXPTIME)

        mask = mask.astype(bool)
        try:
            self.action.args.ccddata.flags[mask] += 4
        except AttributeError:
            self.logger.warning("Flags array not found!")
        # DN 2023-may-28: not updating ccddata.mask because it causes bad things
        self.action.args.ccddata.data = clean
        return int(mask.sum())

    def _apply_crmsk(self, header, crmsk_path):
        """Apply a pre-computed <frame>_crmsk.fits. Returns the pixel count."""
        self.logger.info('Opening %s' % os.path.basename(crmsk_path))
        with fits.open(crmsk_path) as cr:
            crmsk = np.array(cr['PRIMARY'].data)   # 1 where a cosmic ray was found
            crmed = np.array(cr['MEDSCI'].data)    # mask * scaled median of the group
        hit = crmsk > 1e-3
        self.logger.info("CR mask cleaned cosmic rays")
        header['history'] = "%s cleaned cosmic rays" % os.path.basename(crmsk_path)

        self.action.args.ccddata.flags[hit] += 4
        # replace CR pixels by the (scaled) median of the other frames
        self.logger.info("Replacing CR pixels by median values")
        self.action.args.ccddata.data[hit] = 0
        self.action.args.ccddata.data += crmed
        return int(hit.sum())

    # ------------------------------------------------------------------ main
    def _perform(self):
        # TODO: implement parameter options from kcwi_stage1.pro
        self.logger.info("Cleaning and flagging cosmic rays")

        # Header keyword to update
        key = 'CRCLEAN'
        keycom = 'cosmic rays cleaned?'

        header = self.action.args.ccddata.header

        exptime = header['TELAPSE']
        nshuf = header['NSHFUP']
        ttime = header['TTIME']
        if nshuf * ttime > exptime:
            exptime = nshuf * ttime

        is_blue = 'BLUE' in header['CAMERA'].upper()
        crmsk_path = self._output_path('_crmsk.fits')
        use_crmsk = (config_flag(self.config.instrument, 'crmsk', False)
                     and not is_blue and os.path.isfile(crmsk_path))

        if not use_crmsk:
            self.logger.info('No custom CR mask, proceeding with astroscrappy')
            if exptime >= self.config.instrument.CRR_MINEXPTIME:
                inmask = self._protection_mask(header)
                n_crs = self._run_astroscrappy(header, inmask, 'first pass')
                header[key] = (True, keycom)
                header['NCRCLEAN'] = (n_crs, "number of cosmic ray pixels")
            else:
                self.logger.info("Astroscrappy: exptime < minexptime=%.1f" %
                                 self.config.instrument.CRR_MINEXPTIME)
                header['history'] = \
                    "Astroscrappy: exptime < minexptime=%.1f" % \
                    self.config.instrument.CRR_MINEXPTIME
                header[key] = (False, keycom)
                header['NCRCLEAN'] = (0, "number of cosmic ray pixels")
        else:
            n_crs = self._apply_crmsk(header, crmsk_path)
            if config_flag(self.config.instrument, 'extra_CRR', False) or \
                    config_flag(self.config.instrument, 'extra_crr', False):
                # second pass for what the frame comparison missed. Without the
                # protection mask this pass sees a bright QSO core, which varies
                # from frame to frame with seeing and transparency, as a cosmic
                # ray and replaces it -- the same failure the bcrmsk exists to
                # stop in the first pass.
                self.logger.info("Astroscrappy: running extra CRR")
                inmask = self._protection_mask(header)
                n_crs += self._run_astroscrappy(header, inmask, 'extra pass')
            header[key] = (True, keycom)
            header['NCRCLEAN'] = (n_crs, "number of cosmic ray pixels")

        log_string = RemoveCosmicRays.__module__
        self.action.args.ccddata.header['HISTORY'] = log_string
        self.logger.info(log_string)

        if self.config.instrument.saveintims:
            kcwi_fits_writer(self.action.args.ccddata,
                             table=self.action.args.table,
                             output_file=self.action.args.name,
                             output_dir=self.config.instrument.output_directory,
                             suffix="crr")

        return self.action.args
    # END: class RemoveCosmicRays()
