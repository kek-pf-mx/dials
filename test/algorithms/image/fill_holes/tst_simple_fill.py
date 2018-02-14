from __future__ import absolute_import, division

class Test:
  def __init__(self):
    pass

  def run(self):
    from dials.algorithms.image.fill_holes import simple_fill
    from scitbx.array_family import flex
    from math import sqrt

    mask = flex.bool(flex.grid(100, 100), True)
    data = flex.double(flex.grid(100, 100), True)

    for j in range(100):
      for i in range(100):
        data[j, i] = 10 + j * 0.01 + i * 0.01
        if sqrt((j - 50)**2 + (i - 50)**2) <= 10.5:
          mask[j, i] = False
          data[j, i] = 0

    result = simple_fill(data, mask)
    known = data.as_1d().select(mask.as_1d())
    filled = result.as_1d().select(mask.as_1d() == False)
    assert flex.max(filled) <= flex.max(known)
    assert flex.min(filled) >= flex.min(known)

    # Test passed
    print 'OK'

if __name__ == '__main__':
  from dials.test import cd_auto
  with cd_auto(__file__):
    test = Test()
    test.run()
