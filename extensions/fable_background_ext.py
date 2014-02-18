#!/usr/bin/env python
#
# fable_background_ext.py
#
#  Copyright (C) 2013 Diamond Light Source
#
#  Author: James Parkhurst
#
#  This code is distributed under the BSD license, a copy of which is
#  included in the root directory of this package.
from __future__ import division

from dials.interfaces import BackgroundIface


class FableBackgroundExt(BackgroundIface):
  ''' An extension implementing background algorithm in fable. '''

  name = 'fable'

  def __init__(self, params, experiment):
    ''' Initialise the algorithm. '''
    from dials.algorithms.background import FableSubtractorAlgorithm
    self._subtractor = FableSubtractorAlgorithm(
      min_data = params.background.fable.min_data,
      n_sigma = params.background.fable.n_sigma)

  def compute_background(self, reflections):
    ''' Compute the background. '''
    from dials.util.command_line import Command

    # Do the background subtraction
    Command.start('Calculating reflection background')
    mask = self._subtractor(reflections['shoebox'])
    reflections.del_selected(mask != True)
    Command.end('Calculated {0} background values'.format(len(reflections)))
