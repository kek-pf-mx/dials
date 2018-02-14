from __future__ import absolute_import, division
import libtbx.load_env
from os.path import join, isdir

have_dials_regression = libtbx.env.has_module("dials_regression")
if have_dials_regression:
  dials_regression = libtbx.env.find_in_repositories(relative_path="dials_regression", test=isdir)

class TestRayPredictor:
  def __init__(self):
    from dials.algorithms.spot_prediction import IndexGenerator
    from dials.algorithms.spot_prediction import ScanStaticRayPredictor
    from iotbx.xds import xparm, integrate_hkl
    from dials.util import ioutil
    from math import ceil
    import dxtbx
    from rstbx.cftbx.coordinate_frame_converter import \
        coordinate_frame_converter
    from scitbx import matrix

    # The XDS files to read from
    integrate_filename = join(dials_regression, 'data/sim_mx/INTEGRATE.HKL')
    gxparm_filename = join(dials_regression, 'data/sim_mx/GXPARM.XDS')

    # Read the XDS files
    self.integrate_handle = integrate_hkl.reader()
    self.integrate_handle.read_file(integrate_filename)
    self.gxparm_handle = xparm.reader()
    self.gxparm_handle.read_file(gxparm_filename)

    # Get the parameters we need from the GXPARM file
    models = dxtbx.load(gxparm_filename)
    self.beam = models.get_beam()
    self.gonio = models.get_goniometer()
    self.detector = models.get_detector()
    self.scan = models.get_scan()

    # Get crystal parameters
    self.space_group_type = ioutil.get_space_group_type_from_xparm(self.gxparm_handle)
    cfc = coordinate_frame_converter(gxparm_filename)
    a_vec = cfc.get('real_space_a')
    b_vec = cfc.get('real_space_b')
    c_vec = cfc.get('real_space_c')
    self.unit_cell = cfc.get_unit_cell()
    self.ub_matrix = matrix.sqr(a_vec + b_vec + c_vec).inverse()

    # Get the minimum resolution in the integrate file
    d = [self.unit_cell.d(h) for h in self.integrate_handle.hkl]
    self.d_min = min(d)
    # extend the resolution shell by epsilon>0
    # to account for rounding artifacts on 32-bit platforms
    self.d_min = self.d_min - 1e-15

    # Get the number of frames from the max z value
    xcal, ycal, zcal = zip(*self.integrate_handle.xyzcal)
    self.scan.set_image_range((self.scan.get_image_range()[0], self.scan.get_image_range()[0] + int(ceil(max(zcal)))))

    # Print stuff
    #        print self.beam
    #        print self.gonio
    #        print self.detector
    #        print self.scan

    # Create the index generator
    self.generate_indices = IndexGenerator(self.unit_cell, self.space_group_type, self.d_min)

    s0 = self.beam.get_s0()
    m2 = self.gonio.get_rotation_axis()
    fixed_rotation = self.gonio.get_fixed_rotation()
    setting_rotation = self.gonio.get_setting_rotation()
    UB = self.ub_matrix
    dphi = self.scan.get_oscillation_range(deg=False)

    # Create the ray predictor
    self.predict_rays = ScanStaticRayPredictor(s0, m2, fixed_rotation, setting_rotation, dphi)

    # Predict the spot locations
    self.reflections = self.predict_rays(self.generate_indices.to_array(), UB)

  def test_miller_index_set(self):
    """Ensure we have the whole set of miller indices"""
    gen_hkl = {r['miller_index'] for r in self.reflections}
    missing = []
    for hkl in self.integrate_handle.hkl:
      if hkl not in gen_hkl:
        missing.append(hkl)
    assert len(missing) == 0, "%d out of %d reflections not in set, including %s" % (len(missing),
                                                                                     len(self.integrate_handle.hkl),
                                                                                     str(missing[0]))

  def test_rotation_angles(self):
    """Ensure the rotation angles agree with XDS"""

    # Create a dict of lists of xy for each hkl
    gen_phi = {}
    for r in self.reflections:
      hkl = r['miller_index']
      phi = r['phi']
      try:
        a = gen_phi[hkl]
        a.append(phi)
        gen_phi[hkl] = a
      except KeyError:
        gen_phi[hkl] = [phi]

    # For each hkl in the xds file
    for hkl, xyz in zip(self.integrate_handle.hkl, self.integrate_handle.xyzcal):

      # Calculate the XDS phi value
      xds_phi = self.scan.get_oscillation(deg=False)[0] + \
                xyz[2]*self.scan.get_oscillation(deg=False)[1]

      # Select the nearest xy to use if there are 2
      my_phi = gen_phi[hkl]
      if len(my_phi) == 2:
        my_phi0 = my_phi[0]
        my_phi1 = my_phi[1]
        diff0 = abs(xds_phi - my_phi0)
        diff1 = abs(xds_phi - my_phi1)
        if diff0 < diff1:
          my_phi = my_phi0
        else:
          my_phi = my_phi1
      else:
        my_phi = my_phi[0]

      # Check the Phi values are the same
      assert (abs(xds_phi - my_phi) < 0.1)

    print "OK"

  def test_beam_vectors(self):
    """Ensure |s1| == |s0|"""
    from scitbx import matrix
    s0_length = matrix.col(self.beam.get_s0()).length()
    for r in self.reflections:
      s1 = r['s1']
      s1_length = matrix.col(s1).length()
      assert (abs(s0_length - s1_length) < 1e-7)

    print "OK"

  def test_new(self):

    from dials.algorithms.spot_prediction import ScanStaticRayPredictor
    from dials.algorithms.spot_prediction import IndexGenerator
    # Create the index generator
    self.generate_indices = IndexGenerator(self.unit_cell, self.space_group_type, self.d_min)

    s0 = self.beam.get_s0()
    m2 = self.gonio.get_rotation_axis()
    fixed_rotation = self.gonio.get_fixed_rotation()
    setting_rotation = self.gonio.get_setting_rotation()
    UB = self.ub_matrix
    dphi = self.scan.get_oscillation_range(deg=False)

    # Create the ray predictor
    self.predict_rays = ScanStaticRayPredictor(s0, m2, fixed_rotation, setting_rotation, dphi)

    # Predict the spot locations
    self.reflections2 = []
    for h in self.generate_indices.to_array():
      rays = self.predict_rays(h, UB)
      for ray in rays:
        if ray.angle >= dphi[0] and ray.angle <= dphi[1]:
          self.reflections2.append(ray)

    eps = 1e-7
    assert (len(self.reflections) == len(self.reflections2))
    for r1, r2 in zip(self.reflections, self.reflections2):
      assert (all(abs(a - b) < eps for a, b in zip(r1['s1'], r2.s1)))
      assert (abs(r1['phi'] - r2.angle) < eps)
      assert (r1['entering'] == r2.entering)
    print 'OK'

  def test_new_from_array(self):
    from dials.algorithms.spot_prediction import ScanStaticRayPredictor
    from dials.algorithms.spot_prediction import IndexGenerator
    # Create the index generator
    self.generate_indices = IndexGenerator(self.unit_cell, self.space_group_type, self.d_min)

    s0 = self.beam.get_s0()
    m2 = self.gonio.get_rotation_axis()
    fixed_rotation = self.gonio.get_fixed_rotation()
    setting_rotation = self.gonio.get_setting_rotation()
    UB = self.ub_matrix
    dphi = self.scan.get_oscillation_range(deg=False)

    # Create the ray predictor
    self.predict_rays = ScanStaticRayPredictor(s0, m2, fixed_rotation, setting_rotation, dphi)

    # Predict the spot locations
    h = self.generate_indices.to_array()
    reflections = self.predict_rays(h, UB)
    self.reflections3 = []
    for r in reflections:
      if r['phi'] >= dphi[0] and r['phi'] <= dphi[1]:
        self.reflections3.append(r)

    eps = 1e-7
    assert (len(self.reflections) == len(self.reflections3))
    for r1, r2 in zip(self.reflections, self.reflections3):
      assert (all(abs(a - b) < eps for a, b in zip(r1['s1'], r2['s1'])))
      assert (abs(r1['phi'] - r2['phi']) < eps)
      assert (r1['entering'] == r2['entering'])
    print 'OK'

  def test_scan_varying(self):
    from dials.algorithms.spot_prediction import ScanVaryingRayPredictor
    from dials.algorithms.spot_prediction import ReekeIndexGenerator
    from scitbx import matrix
    import scitbx.math
    from libtbx.test_utils import approx_equal
    from math import pi

    s0 = self.beam.get_s0()
    m2 = self.gonio.get_rotation_axis()
    UB = self.ub_matrix
    dphi = self.scan.get_oscillation_range(deg=False)

    # For quick comparison look at reflections on one frame only
    frame = 0
    angle_beg = self.scan.get_angle_from_array_index(frame, deg=False)
    angle_end = self.scan.get_angle_from_array_index(frame + 1, deg=False)
    frame0_refs = self.reflections.select((self.reflections['phi'] >= angle_beg) &
                                          (self.reflections['phi'] <= angle_end))

    # Get UB matrices at beginning and end of frame
    r_osc_beg = matrix.sqr(scitbx.math.r3_rotation_axis_and_angle_as_matrix(axis=m2, angle=angle_beg, deg=False))
    UB_beg = r_osc_beg * self.ub_matrix
    r_osc_end = matrix.sqr(scitbx.math.r3_rotation_axis_and_angle_as_matrix(axis=m2, angle=angle_end, deg=False))
    UB_end = r_osc_end * self.ub_matrix

    # Get indices
    r = ReekeIndexGenerator(UB_beg, UB_end, self.space_group_type, m2, s0, self.d_min, margin=1)
    h = r.to_array()

    # Fn to loop through hkl applying a prediction function to each and testing
    # the results are the same as those from the ScanStaticRayPredictor
    def test_each_hkl(hkl_list, predict_fn):
      DEG2RAD = pi / 180.
      count = 0
      for hkl in hkl_list:
        ray = predict_fn(hkl)
        if ray is not None:
          count += 1
          ref = frame0_refs.select(frame0_refs['miller_index'] == hkl)[0]
          assert ref['entering'] == ray.entering
          assert approx_equal(ref['phi'], ray.angle * DEG2RAD) # ray angle is in degrees (!)
          assert approx_equal(ref['s1'], ray.s1)
      # ensure all reflections were matched
      assert count == len(frame0_refs)

    # Create the ray predictor
    sv_predict_rays = ScanVaryingRayPredictor(s0, m2,
                                              self.scan.get_array_range()[0], self.scan.get_oscillation(), self.d_min)

    # Test with the method that allows only differing UB matrices
    test_each_hkl(h, lambda x: sv_predict_rays(x, UB_beg, UB_end, frame))

    # Now repeat prediction using the overload that allows for different s0
    # at the beginning and end of the frame. Here, pass in the same s0 each time
    # and the result should be the same as before
    test_each_hkl(h, lambda x: sv_predict_rays(x, UB_beg, UB_end, s0, s0, frame))

    print "OK"

  def run(self):
    self.test_miller_index_set()
    self.test_rotation_angles()
    self.test_beam_vectors()
    self.test_new()
    self.test_new_from_array()
    self.test_scan_varying()

if __name__ == '__main__':
  if have_dials_regression:
    from dials.test import cd_auto
    with cd_auto(__file__):
      test = TestRayPredictor()
      test.run()
  else:
    print "Skipping test: dials_regression not available."
