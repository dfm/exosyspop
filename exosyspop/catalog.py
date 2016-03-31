from __future__ import print_function, division

from corner import corner
import pandas as pd
import numpy as np

class Catalog(pd.DataFrame):
    _required_columns = ()

    def __init__(self, *args, **kwargs):
        super(Catalog, self).__init__(*args, **kwargs)

        # ensure all required columns are present
        missing = []
        for c in self._required_columns:
            if c not in self.columns:
                missing.append(c)

        if len(missing) > 0:
            raise ValueError('Must contain all required columns! ' + 
                             '({} missing)'.format(missing))

class ObservedCatalog(Catalog):
    """
    DataFrame containing observed properties

    Must have the following columns:
    
      * primary log10(depth), duration, slope (trapezoidal params)
      * secondary log10(depth), duration, slope (trapezoidal params)
      * secondary phase 

    Primary/secondary are defined observationally: that is,
    the deeper (or only) is called the primary
    """
    _required_columns = ('period', 
                         'n_pri', 'logd_pri', 'dur_pri', 'slope_pri',
                         'n_sec', 'logd_sec', 'dur_sec', 'slope_sec',
                         'phase_sec')

class SimulatedCatalog(Catalog):

    def __init__(self, *args, **kwargs):
        super(SimulatedCatalog, self).__init__(*args, **kwargs)
        
        self._observed = None
        self._trap_regr = True

    def _build_observed(self):
        df = pd.DataFrame()
        for c in ObservedCatalog._required_columns:
            df[c] = np.nan * np.ones(len(self))

        df.period = self.period

        # build primary signals
        d_pri = self.d_pri * self.dilution
        d_sec = self.d_sec * self.dilution

        has_pri = (self.n_pri > 0) & (d_pri > 1e-5)
        has_sec = (self.n_sec > 0) & (d_sec > 1e-5)

        pri = has_pri & (d_pri > d_sec)
        sec_is_pri = (~has_pri & has_sec) | (has_pri & has_sec & (d_pri < d_sec))
        sec = (has_pri & has_sec) & (d_sec <= d_pri)
        pri_is_sec = (has_pri & has_sec) & (d_pri < d_sec)

        pri_masks = [pri, sec_is_pri]
        pri_sources = ['pri', 'sec'] 

        sec_masks = [sec, pri_is_sec]
        sec_sources = ['sec', 'pri']

        tag = '_regr' if self._trap_regr else ''

        # primary properties
        for col, source_base in zip(['logd_pri', 'dur_pri', 'slope_pri', 'n_pri'],
                                    ['trap_depth', 'trap_dur', 'trap_slope', 'n']):
            for m, s in zip(pri_masks, pri_sources):
                if source_base == 'n':
                    source_col = 'n_' + s
                else:
                    source_col = source_base + '_' + s + tag
                df.loc[m, col] = self.loc[m, source_col]
                if col=='logd_pri':
                    df.loc[m, col] = np.log10(df.loc[m, col] * self.loc[m, 'dilution'])

        # secondary properties
        for col, source_base in zip(['logd_sec', 'dur_sec', 'slope_sec', 'n_sec'],
                                    ['trap_depth', 'trap_dur', 'trap_slope', 'n']):
            for m, s in zip(sec_masks, sec_sources):
                if source_base == 'n':
                    source_col = 'n_' + s
                else:
                    source_col = source_base + '_' + s + tag
                df.loc[m, col] = self.loc[m, source_col]
                if col=='logd_sec':
                    df.loc[m, col] = np.log10(df.loc[m, col] * self.loc[m, 'dilution'])

        df.loc[sec | pri_is_sec, 'phase_sec'] = self.loc[sec | pri_is_sec, 'phase_sec'] 
        df.sec_is_pri = sec_is_pri

        self._observed = ObservedCatalog(df).dropna(subset=['n_pri'])

    @property
    def observed(self):
        if self._observed is None:
            self._build_observed()
        return self._observed


    def trap_corner(self, sec=False, **kwargs):
        if sec:
            cols = ['dur_sec', 'logd_sec', 'slope_sec']
        else:
            cols = ['dur_pri', 'logd_pri', 'slope_pri']

        return corner(self.observed[cols], labels=['duration', 'log(d)', 'T/tau'],
                      **kwargs)
