#
# Created by: Pearu Peterson, September 2002
#

from __future__ import division, print_function, absolute_import

import sys
import subprocess
import time
from functools import reduce

from numpy.testing import (assert_equal, assert_array_almost_equal, assert_,
                           assert_allclose, assert_almost_equal,
                           assert_array_equal)
import pytest
from pytest import raises as assert_raises

import numpy as np
from numpy import (eye, ones, zeros, zeros_like, triu, tril, tril_indices,
                   triu_indices)

from numpy.random import rand, randint, seed

from scipy.linalg import _flapack as flapack, lapack
from scipy.linalg import inv, svd, cholesky, solve, ldl, norm
from scipy.linalg.lapack import _compute_lwork
from scipy.linalg import qr

import scipy.sparse as sps

try:
    from scipy.linalg import _clapack as clapack
except ImportError:
    clapack = None
from scipy.linalg.lapack import get_lapack_funcs
from scipy.linalg.blas import get_blas_funcs

REAL_DTYPES = [np.float32, np.float64]
COMPLEX_DTYPES = [np.complex64, np.complex128]
DTYPES = REAL_DTYPES + COMPLEX_DTYPES


def test_lapack_documented():
    """Test that all entries are in the doc."""
    if lapack.__doc__ is None:  # just in case there is a python -OO
        pytest.skip('lapack.__doc__ is None')
    names = set(lapack.__doc__.split())
    ignore_list = set([
        'absolute_import', 'clapack', 'division', 'find_best_lapack_type',
        'flapack', 'print_function',
    ])
    missing = list()
    for name in dir(lapack):
        if (not name.startswith('_') and name not in ignore_list and
                name not in names):
            missing.append(name)
    assert missing == [], 'Name(s) missing from lapack.__doc__ or ignore_list'


class TestFlapackSimple(object):

    def test_gebal(self):
        a = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        a1 = [[1, 0, 0, 3e-4],
              [4, 0, 0, 2e-3],
              [7, 1, 0, 0],
              [0, 1, 0, 0]]
        for p in 'sdzc':
            f = getattr(flapack, p+'gebal', None)
            if f is None:
                continue
            ba, lo, hi, pivscale, info = f(a)
            assert_(not info, repr(info))
            assert_array_almost_equal(ba, a)
            assert_equal((lo, hi), (0, len(a[0])-1))
            assert_array_almost_equal(pivscale, np.ones(len(a)))

            ba, lo, hi, pivscale, info = f(a1, permute=1, scale=1)
            assert_(not info, repr(info))
            # print(a1)
            # print(ba, lo, hi, pivscale)

    def test_gehrd(self):
        a = [[-149, -50, -154],
             [537, 180, 546],
             [-27, -9, -25]]
        for p in 'd':
            f = getattr(flapack, p+'gehrd', None)
            if f is None:
                continue
            ht, tau, info = f(a)
            assert_(not info, repr(info))

    def test_trsyl(self):
        a = np.array([[1, 2], [0, 4]])
        b = np.array([[5, 6], [0, 8]])
        c = np.array([[9, 10], [11, 12]])
        trans = 'T'

        # Test single and double implementations, including most
        # of the options
        for dtype in 'fdFD':
            a1, b1, c1 = a.astype(dtype), b.astype(dtype), c.astype(dtype)
            trsyl, = get_lapack_funcs(('trsyl',), (a1,))
            if dtype.isupper():  # is complex dtype
                a1[0] += 1j
                trans = 'C'

            x, scale, info = trsyl(a1, b1, c1)
            assert_array_almost_equal(np.dot(a1, x) + np.dot(x, b1),
                                      scale * c1)

            x, scale, info = trsyl(a1, b1, c1, trana=trans, tranb=trans)
            assert_array_almost_equal(
                    np.dot(a1.conjugate().T, x) + np.dot(x, b1.conjugate().T),
                    scale * c1, decimal=4)

            x, scale, info = trsyl(a1, b1, c1, isgn=-1)
            assert_array_almost_equal(np.dot(a1, x) - np.dot(x, b1),
                                      scale * c1, decimal=4)

    def test_lange(self):
        a = np.array([
            [-149, -50, -154],
            [537, 180, 546],
            [-27, -9, -25]])

        for dtype in 'fdFD':
            for norm_str in 'Mm1OoIiFfEe':
                a1 = a.astype(dtype)
                if dtype.isupper():
                    # is complex dtype
                    a1[0, 0] += 1j

                lange, = get_lapack_funcs(('lange',), (a1,))
                value = lange(norm_str, a1)

                if norm_str in 'FfEe':
                    if dtype in 'Ff':
                        decimal = 3
                    else:
                        decimal = 7
                    ref = np.sqrt(np.sum(np.square(np.abs(a1))))
                    assert_almost_equal(value, ref, decimal)
                else:
                    if norm_str in 'Mm':
                        ref = np.max(np.abs(a1))
                    elif norm_str in '1Oo':
                        ref = np.max(np.sum(np.abs(a1), axis=0))
                    elif norm_str in 'Ii':
                        ref = np.max(np.sum(np.abs(a1), axis=1))

                    assert_equal(value, ref)


class TestLapack(object):

    def test_flapack(self):
        if hasattr(flapack, 'empty_module'):
            # flapack module is empty
            pass

    def test_clapack(self):
        if hasattr(clapack, 'empty_module'):
            # clapack module is empty
            pass


class TestLeastSquaresSolvers(object):

    def test_gels(self):
        seed(1234)
        # Test fat/tall matrix argument handling - gh-issue #8329
        for ind, dtype in enumerate(DTYPES):
            m = 10
            n = 20
            nrhs = 1
            a1 = rand(m, n).astype(dtype)
            b1 = rand(n).astype(dtype)
            gls, glslw = get_lapack_funcs(('gels', 'gels_lwork'), dtype=dtype)

            # Request of sizes
            lwork = _compute_lwork(glslw, m, n, nrhs)
            _, _, info = gls(a1, b1, lwork=lwork)
            assert_(info >= 0)
            _, _, info = gls(a1, b1, trans='TTCC'[ind], lwork=lwork)
            assert_(info >= 0)

        for dtype in REAL_DTYPES:
            a1 = np.array([[1.0, 2.0],
                           [4.0, 5.0],
                           [7.0, 8.0]], dtype=dtype)
            b1 = np.array([16.0, 17.0, 20.0], dtype=dtype)
            gels, gels_lwork, geqrf = get_lapack_funcs(
                    ('gels', 'gels_lwork', 'geqrf'), (a1, b1))

            m, n = a1.shape
            if len(b1.shape) == 2:
                nrhs = b1.shape[1]
            else:
                nrhs = 1

            # Request of sizes
            lwork = _compute_lwork(gels_lwork, m, n, nrhs)

            lqr, x, info = gels(a1, b1, lwork=lwork)
            assert_allclose(x[:-1], np.array([-14.333333333333323,
                                              14.999999999999991],
                                             dtype=dtype),
                            rtol=25*np.finfo(dtype).eps)
            lqr_truth, _, _, _ = geqrf(a1)
            assert_array_equal(lqr, lqr_truth)

        for dtype in COMPLEX_DTYPES:
            a1 = np.array([[1.0+4.0j, 2.0],
                           [4.0+0.5j, 5.0-3.0j],
                           [7.0-2.0j, 8.0+0.7j]], dtype=dtype)
            b1 = np.array([16.0, 17.0+2.0j, 20.0-4.0j], dtype=dtype)
            gels, gels_lwork, geqrf = get_lapack_funcs(
                    ('gels', 'gels_lwork', 'geqrf'), (a1, b1))

            m, n = a1.shape
            if len(b1.shape) == 2:
                nrhs = b1.shape[1]
            else:
                nrhs = 1

            # Request of sizes
            lwork = _compute_lwork(gels_lwork, m, n, nrhs)

            lqr, x, info = gels(a1, b1, lwork=lwork)
            assert_allclose(x[:-1],
                            np.array([1.161753632288328-1.901075709391912j,
                                      1.735882340522193+1.521240901196909j],
                                     dtype=dtype), rtol=25*np.finfo(dtype).eps)
            lqr_truth, _, _, _ = geqrf(a1)
            assert_array_equal(lqr, lqr_truth)

    def test_gelsd(self):
        for dtype in REAL_DTYPES:
            a1 = np.array([[1.0, 2.0],
                           [4.0, 5.0],
                           [7.0, 8.0]], dtype=dtype)
            b1 = np.array([16.0, 17.0, 20.0], dtype=dtype)
            gelsd, gelsd_lwork = get_lapack_funcs(('gelsd', 'gelsd_lwork'),
                                                  (a1, b1))

            m, n = a1.shape
            if len(b1.shape) == 2:
                nrhs = b1.shape[1]
            else:
                nrhs = 1

            # Request of sizes
            work, iwork, info = gelsd_lwork(m, n, nrhs, -1)
            lwork = int(np.real(work))
            iwork_size = iwork

            x, s, rank, info = gelsd(a1, b1, lwork, iwork_size,
                                     -1, False, False)
            assert_allclose(x[:-1], np.array([-14.333333333333323,
                                              14.999999999999991],
                                             dtype=dtype),
                            rtol=25*np.finfo(dtype).eps)
            assert_allclose(s, np.array([12.596017180511966,
                                         0.583396253199685], dtype=dtype),
                            rtol=25*np.finfo(dtype).eps)

        for dtype in COMPLEX_DTYPES:
            a1 = np.array([[1.0+4.0j, 2.0],
                           [4.0+0.5j, 5.0-3.0j],
                           [7.0-2.0j, 8.0+0.7j]], dtype=dtype)
            b1 = np.array([16.0, 17.0+2.0j, 20.0-4.0j], dtype=dtype)
            gelsd, gelsd_lwork = get_lapack_funcs(('gelsd', 'gelsd_lwork'),
                                                  (a1, b1))

            m, n = a1.shape
            if len(b1.shape) == 2:
                nrhs = b1.shape[1]
            else:
                nrhs = 1

            # Request of sizes
            work, rwork, iwork, info = gelsd_lwork(m, n, nrhs, -1)
            lwork = int(np.real(work))
            rwork_size = int(rwork)
            iwork_size = iwork

            x, s, rank, info = gelsd(a1, b1, lwork, rwork_size, iwork_size,
                                     -1, False, False)
            assert_allclose(x[:-1],
                            np.array([1.161753632288328-1.901075709391912j,
                                      1.735882340522193+1.521240901196909j],
                                     dtype=dtype), rtol=25*np.finfo(dtype).eps)
            assert_allclose(s,
                            np.array([13.035514762572043, 4.337666985231382],
                                     dtype=dtype), rtol=25*np.finfo(dtype).eps)

    def test_gelss(self):

        for dtype in REAL_DTYPES:
            a1 = np.array([[1.0, 2.0],
                           [4.0, 5.0],
                           [7.0, 8.0]], dtype=dtype)
            b1 = np.array([16.0, 17.0, 20.0], dtype=dtype)
            gelss, gelss_lwork = get_lapack_funcs(('gelss', 'gelss_lwork'),
                                                  (a1, b1))

            m, n = a1.shape
            if len(b1.shape) == 2:
                nrhs = b1.shape[1]
            else:
                nrhs = 1

            # Request of sizes
            work, info = gelss_lwork(m, n, nrhs, -1)
            lwork = int(np.real(work))

            v, x, s, rank, work, info = gelss(a1, b1, -1, lwork, False, False)
            assert_allclose(x[:-1], np.array([-14.333333333333323,
                                              14.999999999999991],
                                             dtype=dtype),
                            rtol=25*np.finfo(dtype).eps)
            assert_allclose(s, np.array([12.596017180511966,
                                         0.583396253199685], dtype=dtype),
                            rtol=25*np.finfo(dtype).eps)

        for dtype in COMPLEX_DTYPES:
            a1 = np.array([[1.0+4.0j, 2.0],
                           [4.0+0.5j, 5.0-3.0j],
                           [7.0-2.0j, 8.0+0.7j]], dtype=dtype)
            b1 = np.array([16.0, 17.0+2.0j, 20.0-4.0j], dtype=dtype)
            gelss, gelss_lwork = get_lapack_funcs(('gelss', 'gelss_lwork'),
                                                  (a1, b1))

            m, n = a1.shape
            if len(b1.shape) == 2:
                nrhs = b1.shape[1]
            else:
                nrhs = 1

            # Request of sizes
            work, info = gelss_lwork(m, n, nrhs, -1)
            lwork = int(np.real(work))

            v, x, s, rank, work, info = gelss(a1, b1, -1, lwork, False, False)
            assert_allclose(x[:-1],
                            np.array([1.161753632288328-1.901075709391912j,
                                      1.735882340522193+1.521240901196909j],
                                     dtype=dtype),
                            rtol=25*np.finfo(dtype).eps)
            assert_allclose(s, np.array([13.035514762572043,
                                         4.337666985231382], dtype=dtype),
                            rtol=25*np.finfo(dtype).eps)

    def test_gelsy(self):

        for dtype in REAL_DTYPES:
            a1 = np.array([[1.0, 2.0],
                           [4.0, 5.0],
                           [7.0, 8.0]], dtype=dtype)
            b1 = np.array([16.0, 17.0, 20.0], dtype=dtype)
            gelsy, gelsy_lwork = get_lapack_funcs(('gelsy', 'gelss_lwork'),
                                                  (a1, b1))

            m, n = a1.shape
            if len(b1.shape) == 2:
                nrhs = b1.shape[1]
            else:
                nrhs = 1

            # Request of sizes
            work, info = gelsy_lwork(m, n, nrhs, 10*np.finfo(dtype).eps)
            lwork = int(np.real(work))

            jptv = np.zeros((a1.shape[1], 1), dtype=np.int32)
            v, x, j, rank, info = gelsy(a1, b1, jptv, np.finfo(dtype).eps,
                                        lwork, False, False)
            assert_allclose(x[:-1], np.array([-14.333333333333323,
                                              14.999999999999991],
                                             dtype=dtype),
                            rtol=25*np.finfo(dtype).eps)

        for dtype in COMPLEX_DTYPES:
            a1 = np.array([[1.0+4.0j, 2.0],
                           [4.0+0.5j, 5.0-3.0j],
                           [7.0-2.0j, 8.0+0.7j]], dtype=dtype)
            b1 = np.array([16.0, 17.0+2.0j, 20.0-4.0j], dtype=dtype)
            gelsy, gelsy_lwork = get_lapack_funcs(('gelsy', 'gelss_lwork'),
                                                  (a1, b1))

            m, n = a1.shape
            if len(b1.shape) == 2:
                nrhs = b1.shape[1]
            else:
                nrhs = 1

            # Request of sizes
            work, info = gelsy_lwork(m, n, nrhs, 10*np.finfo(dtype).eps)
            lwork = int(np.real(work))

            jptv = np.zeros((a1.shape[1], 1), dtype=np.int32)
            v, x, j, rank, info = gelsy(a1, b1, jptv, np.finfo(dtype).eps,
                                        lwork, False, False)
            assert_allclose(x[:-1],
                            np.array([1.161753632288328-1.901075709391912j,
                                      1.735882340522193+1.521240901196909j],
                                     dtype=dtype),
                            rtol=25*np.finfo(dtype).eps)


@pytest.mark.parametrize('dtype', DTYPES)
@pytest.mark.parametrize('shape', [(3, 4), (5, 2), (2**18, 2**18)])
def test_geqrf_lwork(dtype, shape):
    geqrf_lwork = get_lapack_funcs(('geqrf_lwork'), dtype=dtype)
    m, n = shape
    lwork, info = geqrf_lwork(m=m, n=n)
    assert_equal(info, 0)


class TestRegression(object):

    def test_ticket_1645(self):
        # Check that RQ routines have correct lwork
        for dtype in DTYPES:
            a = np.zeros((300, 2), dtype=dtype)

            gerqf, = get_lapack_funcs(['gerqf'], [a])
            assert_raises(Exception, gerqf, a, lwork=2)
            rq, tau, work, info = gerqf(a)

            if dtype in REAL_DTYPES:
                orgrq, = get_lapack_funcs(['orgrq'], [a])
                assert_raises(Exception, orgrq, rq[-2:], tau, lwork=1)
                orgrq(rq[-2:], tau, lwork=2)
            elif dtype in COMPLEX_DTYPES:
                ungrq, = get_lapack_funcs(['ungrq'], [a])
                assert_raises(Exception, ungrq, rq[-2:], tau, lwork=1)
                ungrq(rq[-2:], tau, lwork=2)


class TestDpotr(object):
    def test_gh_2691(self):
        # 'lower' argument of dportf/dpotri
        for lower in [True, False]:
            for clean in [True, False]:
                np.random.seed(42)
                x = np.random.normal(size=(3, 3))
                a = x.dot(x.T)

                dpotrf, dpotri = get_lapack_funcs(("potrf", "potri"), (a, ))

                c, info = dpotrf(a, lower, clean=clean)
                dpt = dpotri(c, lower)[0]

                if lower:
                    assert_allclose(np.tril(dpt), np.tril(inv(a)))
                else:
                    assert_allclose(np.triu(dpt), np.triu(inv(a)))


class TestDlasd4(object):
    def test_sing_val_update(self):

        sigmas = np.array([4., 3., 2., 0])
        m_vec = np.array([3.12, 5.7, -4.8, -2.2])

        M = np.hstack((np.vstack((np.diag(sigmas[0:-1]),
                                  np.zeros((1, len(m_vec) - 1)))),
                       m_vec[:, np.newaxis]))
        SM = svd(M, full_matrices=False, compute_uv=False, overwrite_a=False,
                 check_finite=False)

        it_len = len(sigmas)
        sgm = np.concatenate((sigmas[::-1], [sigmas[0] + it_len*norm(m_vec)]))
        mvc = np.concatenate((m_vec[::-1], (0,)))

        lasd4 = get_lapack_funcs('lasd4', (sigmas,))

        roots = []
        for i in range(0, it_len):
            res = lasd4(i, sgm, mvc)
            roots.append(res[1])

            assert_((res[3] <= 0), "LAPACK root finding dlasd4 failed to find \
                                    the singular value %i" % i)
        roots = np.array(roots)[::-1]

        assert_((not np.any(np.isnan(roots)), "There are NaN roots"))
        assert_allclose(SM, roots, atol=100*np.finfo(np.float64).eps,
                        rtol=100*np.finfo(np.float64).eps)


class TestTbtrs(object):

    @pytest.mark.parametrize('dtype', DTYPES)
    def test_nag_example_f07vef_f07vsf(self, dtype):
        """Test real (f07vef) and complex (f07vsf) examples from NAG

        Examples available from:
        * https://www.nag.com/numeric/fl/nagdoc_latest/html/f07/f07vef.html
        * https://www.nag.com/numeric/fl/nagdoc_latest/html/f07/f07vsf.html

        """
        if dtype in REAL_DTYPES:
            ab = np.array([[-4.16, 4.78, 6.32, 0.16],
                           [-2.25, 5.86, -4.82, 0]],
                          dtype=dtype)
            b = np.array([[-16.64, -4.16],
                          [-13.78, -16.59],
                          [13.10, -4.94],
                          [-14.14, -9.96]],
                         dtype=dtype)
            x_out = np.array([[4, 1],
                              [-1, -3],
                              [3, 2],
                              [2, -2]],
                             dtype=dtype)
        elif dtype in COMPLEX_DTYPES:
            ab = np.array([[-1.94+4.43j, 4.12-4.27j, 0.43-2.66j, 0.44+0.1j],
                           [-3.39+3.44j, -1.84+5.52j, 1.74 - 0.04j, 0],
                           [1.62+3.68j, -2.77-1.93j, 0, 0]],
                          dtype=dtype)
            b = np.array([[-8.86 - 3.88j, -24.09 - 5.27j],
                          [-15.57 - 23.41j, -57.97 + 8.14j],
                          [-7.63 + 22.78j, 19.09 - 29.51j],
                          [-14.74 - 2.40j, 19.17 + 21.33j]],
                         dtype=dtype)
            x_out = np.array([[2j, 1 + 5j],
                              [1 - 3j, -7 - 2j],
                              [-4.001887 - 4.988417j, 3.026830 + 4.003182j],
                              [1.996158 - 1.045105j, -6.103357 - 8.986653j]],
                             dtype=dtype)
        else:
            raise ValueError(f"Datatype {dtype} not understood.")

        tbtrs = get_lapack_funcs(('tbtrs'), dtype=dtype)
        x, info = tbtrs(ab=ab, b=b, uplo='L')
        assert_equal(info, 0)
        assert_allclose(x, x_out, rtol=0, atol=1e-5)

    @pytest.mark.parametrize('dtype,trans',
                             [(dtype, trans)
                              for dtype in DTYPES for trans in ['N', 'T', 'C']
                              if not (trans == 'C' and dtype in REAL_DTYPES)])
    @pytest.mark.parametrize('uplo', ['U', 'L'])
    @pytest.mark.parametrize('diag', ['N', 'U'])
    def test_random_matrices(self, dtype, trans, uplo, diag):
        seed(1724)
        # lda, ldb, nrhs, kd are used to specify A and b.
        # A is of shape lda x ldb with kd super/sub-diagonals
        # b is of shape ldb x nrhs matrix
        lda, ldb, nrhs, kd = 4, 4, 3, 2
        ldab = kd + 1

        # Construct the diagonal and kd super/sub diagonals of A with
        # the corresponding offsets.
        band_widths = range(lda, lda - kd - 1, -1)
        band_offsets = np.arange(ldab) if uplo == 'U' else np.arange(ldab) * -1
        if dtype in REAL_DTYPES:
            b = rand(ldb, nrhs).astype(dtype)
            bands = [rand(width).astype(dtype) for width in band_widths]
        elif dtype in COMPLEX_DTYPES:
            b = (rand(ldb, nrhs) + rand(ldb, nrhs) * 1j).astype(dtype)
            bands = [(rand(width) + rand(width) * 1j).astype(dtype)
                     for width in band_widths]

        if diag == 'U':  # A must be unit triangular
            bands[0] = np.ones(lda, dtype=dtype)

        # Construct the diagonal banded matrix A from the bands and offsets.
        a = sps.diags(bands, band_offsets, format='dia')
        ab = np.flipud(a.data) if uplo == 'U' else a.data

        tbtrs = get_lapack_funcs('tbtrs', dtype=dtype)
        x, info = tbtrs(ab=ab, b=b, uplo=uplo, trans=trans, diag=diag)
        assert_equal(info, 0)

        if trans == 'N':
            assert_allclose(a @ x, b, rtol=5e-5)
        elif trans == 'T':
            assert_allclose(a.T @ x, b, rtol=5e-5)
        elif trans == 'C':
            assert_allclose(a.H @ x, b, rtol=5e-5)
        else:
            raise ValueError('Invalid trans argument')

    @pytest.mark.parametrize('uplo,trans,diag',
                             [['U', 'N', 'Invalid'],
                              ['U', 'Invalid', 'N'],
                              ['Invalid', 'N', 'N']])
    def test_invalid_argument_raises_exception(self, uplo, trans, diag):
        """Test if invalid values of uplo, trans and diag raise exceptions"""
        # Argument checks occur independently of used datatype.
        # This mean we must not parameterize all available datatypes.
        tbtrs = get_lapack_funcs('tbtrs', dtype=np.float)
        ab = rand(4, 2)
        b = rand(2, 4)
        assert_raises(Exception, tbtrs, ab, b, uplo, trans, diag)

    def test_zero_element_in_diagonal(self):
        """Test if a matrix with a zero diagonal element is singular

        If the i-th diagonal of A is zero, ?tbtrs should return `i` in `info`
        indicating the provided matrix is singular.

        Note that ?tbtrs requires the matrix A to be stored in banded form.
        In this form the diagonal corresponds to the last row."""
        ab = np.ones((3, 4), dtype=float)
        b = np.ones(4, dtype=float)
        tbtrs = get_lapack_funcs('tbtrs', dtype=float)

        ab[-1, 3] = 0
        _, info = tbtrs(ab=ab, b=b, uplo='U')
        assert_equal(info, 4)

    @pytest.mark.parametrize('ldab,n,ldb,nrhs', [
                              (5, 5, 0, 5),
                              (5, 5, 3, 5)
    ])
    def test_invalid_matrix_shapes(self, ldab, n, ldb, nrhs):
        """Test ?tbtrs fails correctly if shapes are invalid."""
        ab = np.ones((ldab, n), dtype=float)
        b = np.ones((ldb, nrhs), dtype=float)
        tbtrs = get_lapack_funcs('tbtrs', dtype=float)
        assert_raises(Exception, tbtrs, ab, b)


def test_lartg():
    for dtype in 'fdFD':
        lartg = get_lapack_funcs('lartg', dtype=dtype)

        f = np.array(3, dtype)
        g = np.array(4, dtype)

        if np.iscomplexobj(g):
            g *= 1j

        cs, sn, r = lartg(f, g)

        assert_allclose(cs, 3.0/5.0)
        assert_allclose(r, 5.0)

        if np.iscomplexobj(g):
            assert_allclose(sn, -4.0j/5.0)
            assert_(type(r) == complex)
            assert_(type(cs) == float)
        else:
            assert_allclose(sn, 4.0/5.0)


def test_rot():
    # srot, drot from blas and crot and zrot from lapack.

    for dtype in 'fdFD':
        c = 0.6
        s = 0.8

        u = np.full(4, 3, dtype)
        v = np.full(4, 4, dtype)
        atol = 10**-(np.finfo(dtype).precision-1)

        if dtype in 'fd':
            rot = get_blas_funcs('rot', dtype=dtype)
            f = 4
        else:
            rot = get_lapack_funcs('rot', dtype=dtype)
            s *= -1j
            v *= 1j
            f = 4j

        assert_allclose(rot(u, v, c, s), [[5, 5, 5, 5],
                                          [0, 0, 0, 0]], atol=atol)
        assert_allclose(rot(u, v, c, s, n=2), [[5, 5, 3, 3],
                                               [0, 0, f, f]], atol=atol)
        assert_allclose(rot(u, v, c, s, offx=2, offy=2),
                        [[3, 3, 5, 5], [f, f, 0, 0]], atol=atol)
        assert_allclose(rot(u, v, c, s, incx=2, offy=2, n=2),
                        [[5, 3, 5, 3], [f, f, 0, 0]], atol=atol)
        assert_allclose(rot(u, v, c, s, offx=2, incy=2, n=2),
                        [[3, 3, 5, 5], [0, f, 0, f]], atol=atol)
        assert_allclose(rot(u, v, c, s, offx=2, incx=2, offy=2, incy=2, n=1),
                        [[3, 3, 5, 3], [f, f, 0, f]], atol=atol)
        assert_allclose(rot(u, v, c, s, incx=-2, incy=-2, n=2),
                        [[5, 3, 5, 3], [0, f, 0, f]], atol=atol)

        a, b = rot(u, v, c, s, overwrite_x=1, overwrite_y=1)
        assert_(a is u)
        assert_(b is v)
        assert_allclose(a, [5, 5, 5, 5], atol=atol)
        assert_allclose(b, [0, 0, 0, 0], atol=atol)


def test_larfg_larf():
    np.random.seed(1234)
    a0 = np.random.random((4, 4))
    a0 = a0.T.dot(a0)

    a0j = np.random.random((4, 4)) + 1j*np.random.random((4, 4))
    a0j = a0j.T.conj().dot(a0j)

    # our test here will be to do one step of reducing a hermetian matrix to
    # tridiagonal form using householder transforms.

    for dtype in 'fdFD':
        larfg, larf = get_lapack_funcs(['larfg', 'larf'], dtype=dtype)

        if dtype in 'FD':
            a = a0j.copy()
        else:
            a = a0.copy()

        # generate a householder transform to clear a[2:,0]
        alpha, x, tau = larfg(a.shape[0]-1, a[1, 0], a[2:, 0])

        # create expected output
        expected = np.zeros_like(a[:, 0])
        expected[0] = a[0, 0]
        expected[1] = alpha

        # assemble householder vector
        v = np.zeros_like(a[1:, 0])
        v[0] = 1.0
        v[1:] = x

        # apply transform from the left
        a[1:, :] = larf(v, tau.conjugate(), a[1:, :], np.zeros(a.shape[1]))

        # apply transform from the right
        a[:, 1:] = larf(v, tau, a[:, 1:], np.zeros(a.shape[0]), side='R')

        assert_allclose(a[:, 0], expected, atol=1e-5)
        assert_allclose(a[0, :], expected, atol=1e-5)


@pytest.mark.xslow
def test_sgesdd_lwork_bug_workaround():
    # Test that SGESDD lwork is sufficiently large for LAPACK.
    #
    # This checks that workaround around an apparent LAPACK bug
    # actually works. cf. gh-5401
    #
    # xslow: requires 1GB+ of memory

    p = subprocess.Popen([sys.executable, '-c',
                          'import numpy as np; '
                          'from scipy.linalg import svd; '
                          'a = np.zeros([9537, 9537], dtype=np.float32); '
                          'svd(a)'],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)

    # Check if it an error occurred within 5 sec; the computation can
    # take substantially longer, and we will not wait for it to finish
    for j in range(50):
        time.sleep(0.1)
        if p.poll() is not None:
            returncode = p.returncode
            break
    else:
        # Didn't exit in time -- probably entered computation.  The
        # error is raised before entering computation, so things are
        # probably OK.
        returncode = 0
        p.terminate()

    assert_equal(returncode, 0,
                 "Code apparently failed: " + p.stdout.read())


class TestSytrd(object):
    def test_sytrd(self):
        for dtype in REAL_DTYPES:
            # Assert that a 0x0 matrix raises an error
            A = np.zeros((0, 0), dtype=dtype)
            sytrd, sytrd_lwork = \
                get_lapack_funcs(('sytrd', 'sytrd_lwork'), (A,))
            assert_raises(ValueError, sytrd, A)

            # Tests for n = 1 currently fail with
            # ```
            # ValueError: failed to create intent(cache|hide)|optional array--
            # must have defined dimensions but got (0,)
            # ```
            # This is a NumPy issue
            # <https://github.com/numpy/numpy/issues/9617>.
            # TODO Once the minimum NumPy version is past 1.14, test for n=1

            # some upper triangular array
            n = 3
            A = np.zeros((n, n), dtype=dtype)
            A[np.triu_indices_from(A)] = \
                np.arange(1, n*(n+1)//2+1, dtype=dtype)

            # query lwork
            lwork, info = sytrd_lwork(n)
            assert_equal(info, 0)

            # check lower=1 behavior (shouldn't do much since the matrix is
            # upper triangular)
            data, d, e, tau, info = sytrd(A, lower=1, lwork=lwork)
            assert_equal(info, 0)

            assert_allclose(data, A, atol=5*np.finfo(dtype).eps, rtol=1.0)
            assert_allclose(d, np.diag(A))
            assert_allclose(e, 0.0)
            assert_allclose(tau, 0.0)

            # and now for the proper test (lower=0 is the default)
            data, d, e, tau, info = sytrd(A, lwork=lwork)
            assert_equal(info, 0)

            # assert Q^T*A*Q = tridiag(e, d, e)

            # build tridiagonal matrix
            T = np.zeros_like(A, dtype=dtype)
            k = np.arange(A.shape[0])
            T[k, k] = d
            k2 = np.arange(A.shape[0]-1)
            T[k2+1, k2] = e
            T[k2, k2+1] = e

            # build Q
            Q = np.eye(n, n, dtype=dtype)
            for i in range(n-1):
                v = np.zeros(n, dtype=dtype)
                v[:i] = data[:i, i+1]
                v[i] = 1.0
                H = np.eye(n, n, dtype=dtype) - tau[i] * np.outer(v, v)
                Q = np.dot(H, Q)

            # Make matrix fully symmetric
            i_lower = np.tril_indices(n, -1)
            A[i_lower] = A.T[i_lower]

            QTAQ = np.dot(Q.T, np.dot(A, Q))

            # disable rtol here since some values in QTAQ and T are very close
            # to 0.
            assert_allclose(QTAQ, T, atol=5*np.finfo(dtype).eps, rtol=1.0)


class TestHetrd(object):
    def test_hetrd(self):
        for real_dtype, complex_dtype in zip(REAL_DTYPES, COMPLEX_DTYPES):
            # Assert that a 0x0 matrix raises an error
            A = np.zeros((0, 0), dtype=complex_dtype)
            hetrd, hetrd_lwork = \
                get_lapack_funcs(('hetrd', 'hetrd_lwork'), (A,))
            assert_raises(ValueError, hetrd, A)

            # Tests for n = 1 currently fail with
            # ```
            # ValueError: failed to create intent(cache|hide)|optional array--
            # must have defined dimensions but got (0,)
            # ```
            # This is a NumPy issue
            # <https://github.com/numpy/numpy/issues/9617>.
            # TODO Once the minimum NumPy version is past 1.14, test for n=1

            # some upper triangular array
            n = 3
            A = np.zeros((n, n), dtype=complex_dtype)
            A[np.triu_indices_from(A)] = (
                np.arange(1, n*(n+1)//2+1, dtype=real_dtype)
                + 1j * np.arange(1, n*(n+1)//2+1, dtype=real_dtype)
                )
            np.fill_diagonal(A, np.real(np.diag(A)))

            # test query lwork
            for x in [0, 1]:
                _, info = hetrd_lwork(n, lower=x)
                assert_equal(info, 0)
            # lwork returns complex which segfaults hetrd call (gh-10388)
            # use the safe and recommended option
            lwork = _compute_lwork(hetrd_lwork, n)

            # check lower=1 behavior (shouldn't do much since the matrix is
            # upper triangular)
            data, d, e, tau, info = hetrd(A, lower=1, lwork=lwork)
            assert_equal(info, 0)

            assert_allclose(data, A, atol=5*np.finfo(real_dtype).eps, rtol=1.0)

            assert_allclose(d, np.real(np.diag(A)))
            assert_allclose(e, 0.0)
            assert_allclose(tau, 0.0)

            # and now for the proper test (lower=0 is the default)
            data, d, e, tau, info = hetrd(A, lwork=lwork)
            assert_equal(info, 0)

            # assert Q^T*A*Q = tridiag(e, d, e)

            # build tridiagonal matrix
            T = np.zeros_like(A, dtype=real_dtype)
            k = np.arange(A.shape[0], dtype=int)
            T[k, k] = d
            k2 = np.arange(A.shape[0]-1, dtype=int)
            T[k2+1, k2] = e
            T[k2, k2+1] = e

            # build Q
            Q = np.eye(n, n, dtype=complex_dtype)
            for i in range(n-1):
                v = np.zeros(n, dtype=complex_dtype)
                v[:i] = data[:i, i+1]
                v[i] = 1.0
                H = np.eye(n, n, dtype=complex_dtype) \
                    - tau[i] * np.outer(v, np.conj(v))
                Q = np.dot(H, Q)

            # Make matrix fully Hermetian
            i_lower = np.tril_indices(n, -1)
            A[i_lower] = np.conj(A.T[i_lower])

            QHAQ = np.dot(np.conj(Q.T), np.dot(A, Q))

            # disable rtol here since some values in QTAQ and T are very close
            # to 0.
            assert_allclose(
                QHAQ, T, atol=10*np.finfo(real_dtype).eps, rtol=1.0
                )


def test_gglse():
    # Example data taken from NAG manual
    for ind, dtype in enumerate(DTYPES):
        # DTYPES = <s,d,c,z> gglse
        func, func_lwork = get_lapack_funcs(('gglse', 'gglse_lwork'),
                                            dtype=dtype)
        lwork = _compute_lwork(func_lwork, m=6, n=4, p=2)
        # For <s,d>gglse
        if ind < 2:
            a = np.array([[-0.57, -1.28, -0.39, 0.25],
                          [-1.93, 1.08, -0.31, -2.14],
                          [2.30, 0.24, 0.40, -0.35],
                          [-1.93, 0.64, -0.66, 0.08],
                          [0.15, 0.30, 0.15, -2.13],
                          [-0.02, 1.03, -1.43, 0.50]], dtype=dtype)
            c = np.array([-1.50, -2.14, 1.23, -0.54, -1.68, 0.82], dtype=dtype)
            d = np.array([0., 0.], dtype=dtype)
        # For <s,d>gglse
        else:
            a = np.array([[0.96-0.81j, -0.03+0.96j, -0.91+2.06j, -0.05+0.41j],
                          [-0.98+1.98j, -1.20+0.19j, -0.66+0.42j, -0.81+0.56j],
                          [0.62-0.46j, 1.01+0.02j, 0.63-0.17j, -1.11+0.60j],
                          [0.37+0.38j, 0.19-0.54j, -0.98-0.36j, 0.22-0.20j],
                          [0.83+0.51j, 0.20+0.01j, -0.17-0.46j, 1.47+1.59j],
                          [1.08-0.28j, 0.20-0.12j, -0.07+1.23j, 0.26+0.26j]])
            c = np.array([[-2.54+0.09j],
                          [1.65-2.26j],
                          [-2.11-3.96j],
                          [1.82+3.30j],
                          [-6.41+3.77j],
                          [2.07+0.66j]])
            d = np.zeros(2, dtype=dtype)

        b = np.array([[1., 0., -1., 0.], [0., 1., 0., -1.]], dtype=dtype)

        _, _, _, result, _ = func(a, b, c, d, lwork=lwork)
        if ind < 2:
            expected = np.array([0.48904455,
                                 0.99754786,
                                 0.48904455,
                                 0.99754786])
        else:
            expected = np.array([1.08742917-1.96205783j,
                                 -0.74093902+3.72973919j,
                                 1.08742917-1.96205759j,
                                 -0.74093896+3.72973895j])
        assert_array_almost_equal(result, expected, decimal=4)


def test_sycon_hecon():
    seed(1234)
    for ind, dtype in enumerate(DTYPES+COMPLEX_DTYPES):
        # DTYPES + COMPLEX DTYPES = <s,d,c,z> sycon + <c,z>hecon
        n = 10
        # For <s,d,c,z>sycon
        if ind < 4:
            func_lwork = get_lapack_funcs('sytrf_lwork', dtype=dtype)
            funcon, functrf = get_lapack_funcs(('sycon', 'sytrf'), dtype=dtype)
            A = (rand(n, n)).astype(dtype)
        # For <c,z>hecon
        else:
            func_lwork = get_lapack_funcs('hetrf_lwork', dtype=dtype)
            funcon, functrf = get_lapack_funcs(('hecon', 'hetrf'), dtype=dtype)
            A = (rand(n, n) + rand(n, n)*1j).astype(dtype)

        # Since sycon only refers to upper/lower part, conj() is safe here.
        A = (A + A.conj().T)/2 + 2*np.eye(n, dtype=dtype)

        anorm = norm(A, 1)
        lwork = _compute_lwork(func_lwork, n)
        ldu, ipiv, _ = functrf(A, lwork=lwork, lower=1)
        rcond, _ = funcon(a=ldu, ipiv=ipiv, anorm=anorm, lower=1)
        # The error is at most 1-fold
        assert_(abs(1/rcond - np.linalg.cond(A, p=1))*rcond < 1)


def test_sygst():
    seed(1234)
    for ind, dtype in enumerate(REAL_DTYPES):
        # DTYPES = <s,d> sygst
        n = 10

        potrf, sygst, syevd, sygvd = get_lapack_funcs(('potrf', 'sygst',
                                                       'syevd', 'sygvd'),
                                                      dtype=dtype)

        A = rand(n, n).astype(dtype)
        A = (A + A.T)/2
        # B must be positive definite
        B = rand(n, n).astype(dtype)
        B = (B + B.T)/2 + 2 * np.eye(n, dtype=dtype)

        # Perform eig (sygvd)
        _, eig_gvd, info = sygvd(A, B)
        assert_(info == 0)

        # Convert to std problem potrf
        b, info = potrf(B)
        assert_(info == 0)
        a, info = sygst(A, b)
        assert_(info == 0)

        eig, _, info = syevd(a)
        assert_(info == 0)
        assert_allclose(eig, eig_gvd, rtol=1e-4)


def test_hegst():
    seed(1234)
    for ind, dtype in enumerate(COMPLEX_DTYPES):
        # DTYPES = <c,z> hegst
        n = 10

        potrf, hegst, heevd, hegvd = get_lapack_funcs(('potrf', 'hegst',
                                                       'heevd', 'hegvd'),
                                                      dtype=dtype)

        A = rand(n, n).astype(dtype) + 1j * rand(n, n).astype(dtype)
        A = (A + A.conj().T)/2
        # B must be positive definite
        B = rand(n, n).astype(dtype) + 1j * rand(n, n).astype(dtype)
        B = (B + B.conj().T)/2 + 2 * np.eye(n, dtype=dtype)

        # Perform eig (hegvd)
        _, eig_gvd, info = hegvd(A, B)
        assert_(info == 0)

        # Convert to std problem potrf
        b, info = potrf(B)
        assert_(info == 0)
        a, info = hegst(A, b)
        assert_(info == 0)

        eig, _, info = heevd(a)
        assert_(info == 0)
        assert_allclose(eig, eig_gvd, rtol=1e-4)


def test_tzrzf():
    """
    This test performs an RZ decomposition in which an m x n upper trapezoidal
    array M (m <= n) is factorized as M = [R 0] * Z where R is upper triangular
    and Z is unitary.
    """
    seed(1234)
    m, n = 10, 15
    for ind, dtype in enumerate(DTYPES):
        tzrzf, tzrzf_lw = get_lapack_funcs(('tzrzf', 'tzrzf_lwork'),
                                           dtype=dtype)
        lwork = _compute_lwork(tzrzf_lw, m, n)

        if ind < 2:
            A = triu(rand(m, n).astype(dtype))
        else:
            A = triu((rand(m, n) + rand(m, n)*1j).astype(dtype))

        # assert wrong shape arg, f2py returns generic error
        assert_raises(Exception, tzrzf, A.T)
        rz, tau, info = tzrzf(A, lwork=lwork)
        # Check success
        assert_(info == 0)

        # Get Z manually for comparison
        R = np.hstack((rz[:, :m], np.zeros((m, n-m), dtype=dtype)))
        V = np.hstack((np.eye(m, dtype=dtype), rz[:, m:]))
        Id = np.eye(n, dtype=dtype)
        ref = [Id-tau[x]*V[[x], :].T.dot(V[[x], :].conj()) for x in range(m)]
        Z = reduce(np.dot, ref)
        assert_allclose(R.dot(Z) - A, zeros_like(A, dtype=dtype),
                        atol=10*np.spacing(dtype(1.0).real), rtol=0.)


def test_tfsm():
    """
    Test for solving a linear system with the coefficient matrix is a
    triangular array stored in Full Packed (RFP) format.
    """
    seed(1234)
    for ind, dtype in enumerate(DTYPES):
        n = 20
        if ind > 1:
            A = triu(rand(n, n) + rand(n, n)*1j + eye(n)).astype(dtype)
            trans = 'C'
        else:
            A = triu(rand(n, n) + eye(n)).astype(dtype)
            trans = 'T'

        trttf, tfttr, tfsm = get_lapack_funcs(('trttf', 'tfttr', 'tfsm'),
                                              dtype=dtype)

        Afp, _ = trttf(A)
        B = rand(n, 2).astype(dtype)
        soln = tfsm(-1, Afp, B)
        assert_array_almost_equal(soln, solve(-A, B),
                                  decimal=4 if ind % 2 == 0 else 6)

        soln = tfsm(-1, Afp, B, trans=trans)
        assert_array_almost_equal(soln, solve(-A.conj().T, B),
                                  decimal=4 if ind % 2 == 0 else 6)

        # Make A, unit diagonal
        A[np.arange(n), np.arange(n)] = dtype(1.)
        soln = tfsm(-1, Afp, B, trans=trans, diag='U')
        assert_array_almost_equal(soln, solve(-A.conj().T, B),
                                  decimal=4 if ind % 2 == 0 else 6)

        # Change side
        B2 = rand(3, n).astype(dtype)
        soln = tfsm(-1, Afp, B2, trans=trans, diag='U', side='R')
        assert_array_almost_equal(soln, solve(-A, B2.T).conj().T,
                                  decimal=4 if ind % 2 == 0 else 6)


def test_ormrz_unmrz():
    """
    This test performs a matrix multiplication with an arbitrary m x n matric C
    and a unitary matrix Q without explicitly forming the array. The array data
    is encoded in the rectangular part of A which is obtained from ?TZRZF. Q
    size is inferred by m, n, side keywords.
    """
    seed(1234)
    qm, qn, cn = 10, 15, 15
    for ind, dtype in enumerate(DTYPES):
        tzrzf, tzrzf_lw = get_lapack_funcs(('tzrzf', 'tzrzf_lwork'),
                                           dtype=dtype)
        lwork_rz = _compute_lwork(tzrzf_lw, qm, qn)

        if ind < 2:
            A = triu(rand(qm, qn).astype(dtype))
            C = rand(cn, cn).astype(dtype)
            orun_mrz, orun_mrz_lw = get_lapack_funcs(('ormrz', 'ormrz_lwork'),
                                                     dtype=dtype)
        else:
            A = triu((rand(qm, qn) + rand(qm, qn)*1j).astype(dtype))
            C = (rand(cn, cn) + rand(cn, cn)*1j).astype(dtype)
            orun_mrz, orun_mrz_lw = get_lapack_funcs(('unmrz', 'unmrz_lwork'),
                                                     dtype=dtype)

        lwork_mrz = _compute_lwork(orun_mrz_lw, cn, cn)
        rz, tau, info = tzrzf(A, lwork=lwork_rz)

        # Get Q manually for comparison
        V = np.hstack((np.eye(qm, dtype=dtype), rz[:, qm:]))
        Id = np.eye(qn, dtype=dtype)
        ref = [Id-tau[x]*V[[x], :].T.dot(V[[x], :].conj()) for x in range(qm)]
        Q = reduce(np.dot, ref)

        # Now that we have Q, we can test whether lapack results agree with
        # each case of CQ, CQ^H, QC, and QC^H
        trans = 'T' if ind < 2 else 'C'
        tol = 10*np.spacing(dtype(1.0).real)

        cq, info = orun_mrz(rz, tau, C, lwork=lwork_mrz)
        assert_(info == 0)
        assert_allclose(cq - Q.dot(C), zeros_like(C), atol=tol, rtol=0.)

        cq, info = orun_mrz(rz, tau, C, trans=trans, lwork=lwork_mrz)
        assert_(info == 0)
        assert_allclose(cq - Q.conj().T.dot(C), zeros_like(C), atol=tol,
                        rtol=0.)

        cq, info = orun_mrz(rz, tau, C, side='R', lwork=lwork_mrz)
        assert_(info == 0)
        assert_allclose(cq - C.dot(Q), zeros_like(C), atol=tol, rtol=0.)

        cq, info = orun_mrz(rz, tau, C, side='R', trans=trans, lwork=lwork_mrz)
        assert_(info == 0)
        assert_allclose(cq - C.dot(Q.conj().T), zeros_like(C), atol=tol,
                        rtol=0.)


def test_tfttr_trttf():
    """
    Test conversion routines between the Rectengular Full Packed (RFP) format
    and Standard Triangular Array (TR)
    """
    seed(1234)
    for ind, dtype in enumerate(DTYPES):
        n = 20
        if ind > 1:
            A_full = (rand(n, n) + rand(n, n)*1j).astype(dtype)
            transr = 'C'
        else:
            A_full = (rand(n, n)).astype(dtype)
            transr = 'T'

        trttf, tfttr = get_lapack_funcs(('trttf', 'tfttr'), dtype=dtype)
        A_tf_U, info = trttf(A_full)
        assert_(info == 0)
        A_tf_L, info = trttf(A_full, uplo='L')
        assert_(info == 0)
        A_tf_U_T, info = trttf(A_full, transr=transr, uplo='U')
        assert_(info == 0)
        A_tf_L_T, info = trttf(A_full, transr=transr, uplo='L')
        assert_(info == 0)

        # Create the RFP array manually (n is even!)
        A_tf_U_m = zeros((n+1, n//2), dtype=dtype)
        A_tf_U_m[:-1, :] = triu(A_full)[:, n//2:]
        A_tf_U_m[n//2+1:, :] += triu(A_full)[:n//2, :n//2].conj().T

        A_tf_L_m = zeros((n+1, n//2), dtype=dtype)
        A_tf_L_m[1:, :] = tril(A_full)[:, :n//2]
        A_tf_L_m[:n//2, :] += tril(A_full)[n//2:, n//2:].conj().T

        assert_array_almost_equal(A_tf_U, A_tf_U_m.reshape(-1, order='F'))
        assert_array_almost_equal(A_tf_U_T,
                                  A_tf_U_m.conj().T.reshape(-1, order='F'))

        assert_array_almost_equal(A_tf_L, A_tf_L_m.reshape(-1, order='F'))
        assert_array_almost_equal(A_tf_L_T,
                                  A_tf_L_m.conj().T.reshape(-1, order='F'))

        # Get the original array from RFP
        A_tr_U, info = tfttr(n, A_tf_U)
        assert_(info == 0)
        A_tr_L, info = tfttr(n, A_tf_L, uplo='L')
        assert_(info == 0)
        A_tr_U_T, info = tfttr(n, A_tf_U_T, transr=transr, uplo='U')
        assert_(info == 0)
        A_tr_L_T, info = tfttr(n, A_tf_L_T, transr=transr, uplo='L')
        assert_(info == 0)

        assert_array_almost_equal(A_tr_U, triu(A_full))
        assert_array_almost_equal(A_tr_U_T, triu(A_full))
        assert_array_almost_equal(A_tr_L, tril(A_full))
        assert_array_almost_equal(A_tr_L_T, tril(A_full))


def test_tpttr_trttp():
    """
    Test conversion routines between the Rectengular Full Packed (RFP) format
    and Standard Triangular Array (TR)
    """
    seed(1234)
    for ind, dtype in enumerate(DTYPES):
        n = 20
        if ind > 1:
            A_full = (rand(n, n) + rand(n, n)*1j).astype(dtype)
        else:
            A_full = (rand(n, n)).astype(dtype)

        trttp, tpttr = get_lapack_funcs(('trttp', 'tpttr'), dtype=dtype)
        A_tp_U, info = trttp(A_full)
        assert_(info == 0)
        A_tp_L, info = trttp(A_full, uplo='L')
        assert_(info == 0)

        # Create the TP array manually
        inds = tril_indices(n)
        A_tp_U_m = zeros(n*(n+1)//2, dtype=dtype)
        A_tp_U_m[:] = (triu(A_full).T)[inds]

        inds = triu_indices(n)
        A_tp_L_m = zeros(n*(n+1)//2, dtype=dtype)
        A_tp_L_m[:] = (tril(A_full).T)[inds]

        assert_array_almost_equal(A_tp_U, A_tp_U_m)
        assert_array_almost_equal(A_tp_L, A_tp_L_m)

        # Get the original array from TP
        A_tr_U, info = tpttr(n, A_tp_U)
        assert_(info == 0)
        A_tr_L, info = tpttr(n, A_tp_L, uplo='L')
        assert_(info == 0)

        assert_array_almost_equal(A_tr_U, triu(A_full))
        assert_array_almost_equal(A_tr_L, tril(A_full))


def test_pftrf():
    """
    Test Cholesky factorization of a positive definite Rectengular Full
    Packed (RFP) format array
    """
    seed(1234)
    for ind, dtype in enumerate(DTYPES):
        n = 20
        if ind > 1:
            A = (rand(n, n) + rand(n, n)*1j).astype(dtype)
            A = A + A.conj().T + n*eye(n)
        else:
            A = (rand(n, n)).astype(dtype)
            A = A + A.T + n*eye(n)

        pftrf, trttf, tfttr = get_lapack_funcs(('pftrf', 'trttf', 'tfttr'),
                                               dtype=dtype)

        # Get the original array from TP
        Afp, info = trttf(A)
        Achol_rfp, info = pftrf(n, Afp)
        assert_(info == 0)
        A_chol_r, _ = tfttr(n, Achol_rfp)
        Achol = cholesky(A)
        assert_array_almost_equal(A_chol_r, Achol)


def test_pftri():
    """
    Test Cholesky factorization of a positive definite Rectengular Full
    Packed (RFP) format array to find its inverse
    """
    seed(1234)
    for ind, dtype in enumerate(DTYPES):
        n = 20
        if ind > 1:
            A = (rand(n, n) + rand(n, n)*1j).astype(dtype)
            A = A + A.conj().T + n*eye(n)
        else:
            A = (rand(n, n)).astype(dtype)
            A = A + A.T + n*eye(n)

        pftri, pftrf, trttf, tfttr = get_lapack_funcs(('pftri',
                                                       'pftrf',
                                                       'trttf',
                                                       'tfttr'),
                                                      dtype=dtype)

        # Get the original array from TP
        Afp, info = trttf(A)
        A_chol_rfp, info = pftrf(n, Afp)
        A_inv_rfp, info = pftri(n, A_chol_rfp)
        assert_(info == 0)
        A_inv_r, _ = tfttr(n, A_inv_rfp)
        Ainv = inv(A)
        assert_array_almost_equal(A_inv_r, triu(Ainv),
                                  decimal=4 if ind % 2 == 0 else 6)


def test_pftrs():
    """
    Test Cholesky factorization of a positive definite Rectengular Full
    Packed (RFP) format array and solve a linear system
    """
    seed(1234)
    for ind, dtype in enumerate(DTYPES):
        n = 20
        if ind > 1:
            A = (rand(n, n) + rand(n, n)*1j).astype(dtype)
            A = A + A.conj().T + n*eye(n)
        else:
            A = (rand(n, n)).astype(dtype)
            A = A + A.T + n*eye(n)

        B = ones((n, 3), dtype=dtype)
        Bf1 = ones((n+2, 3), dtype=dtype)
        Bf2 = ones((n-2, 3), dtype=dtype)
        pftrs, pftrf, trttf, tfttr = get_lapack_funcs(('pftrs',
                                                       'pftrf',
                                                       'trttf',
                                                       'tfttr'),
                                                      dtype=dtype)

        # Get the original array from TP
        Afp, info = trttf(A)
        A_chol_rfp, info = pftrf(n, Afp)
        # larger B arrays shouldn't segfault
        soln, info = pftrs(n, A_chol_rfp, Bf1)
        assert_(info == 0)
        assert_raises(Exception, pftrs, n, A_chol_rfp, Bf2)
        soln, info = pftrs(n, A_chol_rfp, B)
        assert_(info == 0)
        assert_array_almost_equal(solve(A, B), soln,
                                  decimal=4 if ind % 2 == 0 else 6)


def test_sfrk_hfrk():
    """
    Test for performing a symmetric rank-k operation for matrix in RFP format.
    """
    seed(1234)
    for ind, dtype in enumerate(DTYPES):
        n = 20
        if ind > 1:
            A = (rand(n, n) + rand(n, n)*1j).astype(dtype)
            A = A + A.conj().T + n*eye(n)
        else:
            A = (rand(n, n)).astype(dtype)
            A = A + A.T + n*eye(n)

        prefix = 's'if ind < 2 else 'h'
        trttf, tfttr, shfrk = get_lapack_funcs(('trttf', 'tfttr', '{}frk'
                                                ''.format(prefix)),
                                               dtype=dtype)

        Afp, _ = trttf(A)
        C = np.random.rand(n, 2).astype(dtype)
        Afp_out = shfrk(n, 2, -1, C, 2, Afp)
        A_out, _ = tfttr(n, Afp_out)
        assert_array_almost_equal(A_out, triu(-C.dot(C.conj().T) + 2*A),
                                  decimal=4 if ind % 2 == 0 else 6)


def test_syconv():
    """
    Test for going back and forth between the returned format of he/sytrf to
    L and D factors/permutations.
    """
    seed(1234)
    for ind, dtype in enumerate(DTYPES):
        n = 10

        if ind > 1:
            A = (randint(-30, 30, (n, n)) +
                 randint(-30, 30, (n, n))*1j).astype(dtype)

            A = A + A.conj().T
        else:
            A = randint(-30, 30, (n, n)).astype(dtype)
            A = A + A.T + n*eye(n)

        tol = 100*np.spacing(dtype(1.0).real)
        syconv, trf, trf_lwork = get_lapack_funcs(('syconv', 'sytrf',
                                                   'sytrf_lwork'), dtype=dtype)
        lw = _compute_lwork(trf_lwork, n, lower=1)
        L, D, perm = ldl(A, lower=1, hermitian=False)
        lw = _compute_lwork(trf_lwork, n, lower=1)
        ldu, ipiv, info = trf(A, lower=1, lwork=lw)
        a, e, info = syconv(ldu, ipiv, lower=1)
        assert_allclose(tril(a, -1,), tril(L[perm, :], -1), atol=tol, rtol=0.)

        # Test also upper
        U, D, perm = ldl(A, lower=0, hermitian=False)
        ldu, ipiv, info = trf(A, lower=0)
        a, e, info = syconv(ldu, ipiv, lower=0)
        assert_allclose(triu(a, 1), triu(U[perm, :], 1), atol=tol, rtol=0.)


class TestBlockedQR(object):
    """
    Tests for the blocked QR factorization, namely through geqrt, gemqrt, tpqrt
    and tpmqr.
    """

    def test_geqrt_gemqrt(self):
        seed(1234)
        for ind, dtype in enumerate(DTYPES):
            n = 20

            if ind > 1:
                A = (rand(n, n) + rand(n, n)*1j).astype(dtype)
            else:
                A = (rand(n, n)).astype(dtype)

            tol = 100*np.spacing(dtype(1.0).real)
            geqrt, gemqrt = get_lapack_funcs(('geqrt', 'gemqrt'), dtype=dtype)

            a, t, info = geqrt(n, A)
            assert(info == 0)

            # Extract elementary reflectors from lower triangle, adding the
            # main diagonal of ones.
            v = np.tril(a, -1) + np.eye(n, dtype=dtype)
            # Generate the block Householder transform I - VTV^H
            Q = np.eye(n, dtype=dtype) - v @ t @ v.T.conj()
            R = np.triu(a)

            # Test columns of Q are orthogonal
            assert_allclose(Q.T.conj() @ Q, np.eye(n, dtype=dtype), atol=tol,
                            rtol=0.)
            assert_allclose(Q @ R, A, atol=tol, rtol=0.)

            if ind > 1:
                C = (rand(n, n) + rand(n, n)*1j).astype(dtype)
                transpose = 'C'
            else:
                C = (rand(n, n)).astype(dtype)
                transpose = 'T'

            for side in ('L', 'R'):
                for trans in ('N', transpose):
                    c, info = gemqrt(a, t, C, side=side, trans=trans)
                    assert(info == 0)

                    if trans == transpose:
                        q = Q.T.conj()
                    else:
                        q = Q

                    if side == 'L':
                        qC = q @ C
                    else:
                        qC = C @ q

                    assert_allclose(c, qC, atol=tol, rtol=0.)

                    # Test default arguments
                    if (side, trans) == ('L', 'N'):
                        c_default, info = gemqrt(a, t, C)
                        assert(info == 0)
                        assert_equal(c_default, c)

            # Test invalid side/trans
            assert_raises(Exception, gemqrt, a, t, C, side='A')
            assert_raises(Exception, gemqrt, a, t, C, trans='A')

    def test_tpqrt_tpmqrt(self):
        seed(1234)
        for ind, dtype in enumerate(DTYPES):
            n = 20

            if ind > 1:
                A = (rand(n, n) + rand(n, n)*1j).astype(dtype)
                B = (rand(n, n) + rand(n, n)*1j).astype(dtype)
            else:
                A = (rand(n, n)).astype(dtype)
                B = (rand(n, n)).astype(dtype)

            tol = 100*np.spacing(dtype(1.0).real)
            tpqrt, tpmqrt = get_lapack_funcs(('tpqrt', 'tpmqrt'), dtype=dtype)

            # Test for the range of pentagonal B, from square to upper
            # triangular
            for l in (0, n // 2, n):
                a, b, t, info = tpqrt(l, n, A, B)
                assert(info == 0)

                # Check that lower triangular part of A has not been modified
                assert_equal(np.tril(a, -1), np.tril(A, -1))
                # Check that elements not part of the pentagonal portion of B
                # have not been modified.
                assert_equal(np.tril(b, l - n - 1), np.tril(B, l - n - 1))

                # Extract pentagonal portion of B
                B_pent, b_pent = np.triu(B, l - n), np.triu(b, l - n)

                # Generate elementary reflectors
                v = np.concatenate((np.eye(n, dtype=dtype), b_pent))
                # Generate the block Householder transform I - VTV^H
                Q = np.eye(2 * n, dtype=dtype) - v @ t @ v.T.conj()
                R = np.concatenate((np.triu(a), np.zeros_like(a)))

                # Test columns of Q are orthogonal
                assert_allclose(Q.T.conj() @ Q, np.eye(2 * n, dtype=dtype),
                                atol=tol, rtol=0.)
                assert_allclose(Q @ R, np.concatenate((np.triu(A), B_pent)),
                                atol=tol, rtol=0.)

                if ind > 1:
                    C = (rand(n, n) + rand(n, n)*1j).astype(dtype)
                    D = (rand(n, n) + rand(n, n)*1j).astype(dtype)
                    transpose = 'C'
                else:
                    C = (rand(n, n)).astype(dtype)
                    D = (rand(n, n)).astype(dtype)
                    transpose = 'T'

                for side in ('L', 'R'):
                    for trans in ('N', transpose):
                        c, d, info = tpmqrt(l, b, t, C, D, side=side,
                                            trans=trans)
                        assert(info == 0)

                        if trans == transpose:
                            q = Q.T.conj()
                        else:
                            q = Q

                        if side == 'L':
                            cd = np.concatenate((c, d), axis=0)
                            CD = np.concatenate((C, D), axis=0)
                            qCD = q @ CD
                        else:
                            cd = np.concatenate((c, d), axis=1)
                            CD = np.concatenate((C, D), axis=1)
                            qCD = CD @ q

                        assert_allclose(cd, qCD, atol=tol, rtol=0.)

                        if (side, trans) == ('L', 'N'):
                            c_default, d_default, info = tpmqrt(l, b, t, C, D)
                            assert(info == 0)
                            assert_equal(c_default, c)
                            assert_equal(d_default, d)

                # Test invalid side/trans
                assert_raises(Exception, tpmqrt, l, b, t, C, D, side='A')
                assert_raises(Exception, tpmqrt, l, b, t, C, D, trans='A')


def test_pstrf():
    seed(1234)
    for ind, dtype in enumerate(DTYPES):
        # DTYPES = <s, d, c, z> pstrf
        n = 10
        r = 2
        pstrf = get_lapack_funcs('pstrf', dtype=dtype)

        # Create positive semidefinite A
        if ind > 1:
            A = rand(n, n-r).astype(dtype) + 1j * rand(n, n-r).astype(dtype)
            A = A @ A.conj().T
        else:
            A = rand(n, n-r).astype(dtype)
            A = A @ A.T

        c, piv, r_c, info = pstrf(A)
        U = triu(c)
        U[r_c - n:, r_c - n:] = 0.

        assert_equal(info, 1)
        # python-dbg 3.5.2 runs cause trouble with the following assertion.
        # assert_equal(r_c, n - r)
        single_atol = 1000 * np.finfo(np.float32).eps
        double_atol = 1000 * np.finfo(np.float64).eps
        atol = single_atol if ind in [0, 2] else double_atol
        assert_allclose(A[piv-1][:, piv-1], U.conj().T @ U, rtol=0., atol=atol)

        c, piv, r_c, info = pstrf(A, lower=1)
        L = tril(c)
        L[r_c - n:, r_c - n:] = 0.

        assert_equal(info, 1)
        # assert_equal(r_c, n - r)
        single_atol = 1000 * np.finfo(np.float32).eps
        double_atol = 1000 * np.finfo(np.float64).eps
        atol = single_atol if ind in [0, 2] else double_atol
        assert_allclose(A[piv-1][:, piv-1], L @ L.conj().T, rtol=0., atol=atol)


def test_pstf2():
    seed(1234)
    for ind, dtype in enumerate(DTYPES):
        # DTYPES = <s, d, c, z> pstf2
        n = 10
        r = 2
        pstf2 = get_lapack_funcs('pstf2', dtype=dtype)

        # Create positive semidefinite A
        if ind > 1:
            A = rand(n, n-r).astype(dtype) + 1j * rand(n, n-r).astype(dtype)
            A = A @ A.conj().T
        else:
            A = rand(n, n-r).astype(dtype)
            A = A @ A.T

        c, piv, r_c, info = pstf2(A)
        U = triu(c)
        U[r_c - n:, r_c - n:] = 0.

        assert_equal(info, 1)
        # python-dbg 3.5.2 runs cause trouble with the commented assertions.
        # assert_equal(r_c, n - r)
        single_atol = 1000 * np.finfo(np.float32).eps
        double_atol = 1000 * np.finfo(np.float64).eps
        atol = single_atol if ind in [0, 2] else double_atol
        assert_allclose(A[piv-1][:, piv-1], U.conj().T @ U, rtol=0., atol=atol)

        c, piv, r_c, info = pstf2(A, lower=1)
        L = tril(c)
        L[r_c - n:, r_c - n:] = 0.

        assert_equal(info, 1)
        # assert_equal(r_c, n - r)
        single_atol = 1000 * np.finfo(np.float32).eps
        double_atol = 1000 * np.finfo(np.float64).eps
        atol = single_atol if ind in [0, 2] else double_atol
        assert_allclose(A[piv-1][:, piv-1], L @ L.conj().T, rtol=0., atol=atol)


def test_geequ():
    desired_real = np.array([[0.6250, 1.0000, 0.0393, -0.4269],
                             [1.0000, -0.5619, -1.0000, -1.0000],
                             [0.5874, -1.0000, -0.0596, -0.5341],
                             [-1.0000, -0.5946, -0.0294, 0.9957]])

    desired_cplx = np.array([[-0.2816+0.5359*1j,
                              0.0812+0.9188*1j,
                              -0.7439-0.2561*1j],
                             [-0.3562-0.2954*1j,
                              0.9566-0.0434*1j,
                              -0.0174+0.1555*1j],
                             [0.8607+0.1393*1j,
                              -0.2759+0.7241*1j,
                              -0.1642-0.1365*1j]])

    for ind, dtype in enumerate(DTYPES):
        if ind < 2:
            # Use examples from the NAG documentation
            A = np.array([[1.80e+10, 2.88e+10, 2.05e+00, -8.90e+09],
                          [5.25e+00, -2.95e+00, -9.50e-09, -3.80e+00],
                          [1.58e+00, -2.69e+00, -2.90e-10, -1.04e+00],
                          [-1.11e+00, -6.60e-01, -5.90e-11, 8.00e-01]])
            A = A.astype(dtype)
        else:
            A = np.array([[-1.34e+00, 0.28e+10, -6.39e+00],
                          [-1.70e+00, 3.31e+10, -0.15e+00],
                          [2.41e-10, -0.56e+00, -0.83e-10]], dtype=dtype)
            A += np.array([[2.55e+00, 3.17e+10, -2.20e+00],
                           [-1.41e+00, -0.15e+10, 1.34e+00],
                           [0.39e-10, 1.47e+00, -0.69e-10]])*1j

            A = A.astype(dtype)

        geequ = get_lapack_funcs('geequ', dtype=dtype)
        r, c, rowcnd, colcnd, amax, info = geequ(A)

        if ind < 2:
            assert_allclose(desired_real.astype(dtype), r[:, None]*A*c,
                            rtol=0, atol=1e-4)
        else:
            assert_allclose(desired_cplx.astype(dtype), r[:, None]*A*c,
                            rtol=0, atol=1e-4)


def test_syequb():
    desired_log2s = np.array([0, 0, 0, 0, 0, 0, -1, -1, -2, -3])

    for ind, dtype in enumerate(DTYPES):
        A = np.eye(10, dtype=dtype)
        alpha = dtype(1. if ind < 2 else 1.j)
        d = np.array([alpha * 2.**x for x in range(-5, 5)], dtype=dtype)
        A += np.rot90(np.diag(d))

        syequb = get_lapack_funcs('syequb', dtype=dtype)
        s, scond, amax, info = syequb(A)

        assert_equal(np.log2(s).astype(int), desired_log2s)


def test_heequb():
    desired_log2s = np.array([[-2, -7, -2, -4, -2, -3, -2, -2, -1, -2],
                              [1, -10, 0, -6, -1, -4, -1, -2, -1, -2]])
    for ind, dtype in enumerate(COMPLEX_DTYPES):
        heequb = get_lapack_funcs('heequb', dtype=dtype)

        d = np.array([dtype(1j) * 2**x for x in range(-5, 5)], dtype=dtype)
        A = np.diag(d)
        subdiags = np.array([dtype(1j) * 2**(9-x) for x in range(9)],
                            dtype=dtype)
        A[range(1, 10), range(0, 9)] = subdiags
        s, scond, amax, info = heequb(A, lower=1)

        # See gh-10741
        pre3_7_lapack_result = np.log2(s).astype(int) == desired_log2s[0, :]
        post3_7_lapack_result = np.log2(s).astype(int) == desired_log2s[1, :]

        assert pre3_7_lapack_result.all() or post3_7_lapack_result.all()


def test_getc2_gesc2():
    np.random.seed(42)
    n = 10
    desired_real = np.random.rand(n)
    desired_cplx = np.random.rand(n) + np.random.rand(n)*1j

    for ind, dtype in enumerate(DTYPES):
        if ind < 2:
            A = np.random.rand(n, n)
            A = A.astype(dtype)
            b = A @ desired_real
            b = b.astype(dtype)
        else:
            A = np.random.rand(n, n) + np.random.rand(n, n)*1j
            A = A.astype(dtype)
            b = A @ desired_cplx
            b = b.astype(dtype)

        getc2 = get_lapack_funcs('getc2', dtype=dtype)
        gesc2 = get_lapack_funcs('gesc2', dtype=dtype)
        lu, ipiv, jpiv, info = getc2(A, overwrite_a=0)
        x, scale = gesc2(lu, b, ipiv, jpiv, overwrite_rhs=0)

        if ind < 2:
            assert_array_almost_equal(desired_real.astype(dtype),
                                      x/scale, decimal=4)
        else:
            assert_array_almost_equal(desired_cplx.astype(dtype),
                                      x/scale, decimal=4)


@pytest.mark.parametrize("dtype", DTYPES)
def test_gttrf_gttrs(dtype):
    # The test uses ?gttrf and ?gttrs to solve a random system for each dtype,
    # tests that the output of ?gttrf define LU matricies, that input
    # parameters are unmodified, transposal options function correctly, that
    # incompatible matrix shapes raise an error, and singular matrices return
    # non zero info.

    np.random.seed(42)
    n = 10
    rtol = 250 * np.finfo(dtype).eps  # set test tolerance appropriate for dtype
    atol = 100 * np.finfo(dtype).eps


def generate_random_dtype_array(shape, dtype):
    # generates a random matrix of desired data type of shape
    if dtype in COMPLEX_DTYPES:
        return (np.random.rand(*shape)
                + np.random.rand(*shape)*1.0j).astype(dtype)
    return np.random.rand(*shape).astype(dtype)


@pytest.mark.parametrize('dtype', DTYPES)
@pytest.mark.parametrize('matrix_size', [(3, 4), (7, 6), (6, 6)])
def test_geqrfp(dtype, matrix_size):
    # This test tests for all dytpes, tall, wide, and square matricies.
    # Using the routine with random Matrix A, Q and R are obtained and then
    # tested such that R is upper triangualr and non-negative on the diagonal,
    # and Q is tested as an orthagonal matrix. Verifies that A=Q@R. It also
    # tests against a matrix that the linalg.qr method returns negative
    # diagonals, and for info and error messaging.

    # Additional note: this test stands alone without a NAG manual additional
    #   example as the NAG problem was overly complex in for the small role
    #   this routine played in it.
    # set test tolerance appropriate for dtype
    np.random.seed(42)
    rtol = 250*np.finfo(dtype).eps
    atol = 100*np.finfo(dtype).eps
    # get appropriate ?geqrfp for dtype
    geqrfp = get_lapack_funcs(('geqrfp'), dtype=dtype)
    gqr = get_lapack_funcs(("orgqr"), dtype=dtype)

    m, n = matrix_size

    # create random matrix of dimentions m x n
    A = generate_random_dtype_array((m, n), dtype=dtype)
    # create rq matrix using geqrfp
    qr_A, tau, work, info = geqrfp(A)

    # obtain r from the upper triangular area
    r = np.triu(qr_A)

    # obtain q from the orgqr lapack routine
    # based on linalg.qr's extraction strategy of q with orgqr

    if m > n:
        # this adds an extra column to the end of qr_A
        # let qqr be an empty m x m matrix
        qqr = np.zeros((m, m), dtype=dtype)
        # set first n columns of qqr to qr_A
        qqr[:, :n] = qr_A
        # determine q from this qqr
        # note that m is a sufficient for lwork based on LAPACK documentation
        q = gqr(qqr, tau=tau, lwork=m)[0]
    else:
        q = gqr(qr_A[:, :m], tau=tau, lwork=m)[0]

    # test that q and r still make A
    assert_allclose(q@r, A, rtol=rtol)
    # ensure that q is orthogonal (that q @ transposed q is the identity)
    assert_allclose(np.eye(q.shape[0]), q@(q.conj().T), rtol=rtol,
                    atol=atol)
    # ensure r is upper tri by comparing original r to r as upper triangular
    assert_allclose(r, np.triu(r), rtol=rtol)
    # make sure diagonals of r are positive for this random solution
    assert_(np.all(np.diag(r) > np.zeros(len(np.diag(r)))))
    # ensure that info is zero for this success
    assert_(info == 0)

    # test that this routine gives r diagonals that are positive for a
    # matrix that returns negatives in the diagonal with scipy.linalg.rq
    A_negative = generate_random_dtype_array((n, m), dtype=dtype) * -1
    r_rq_neg, q_rq_neg = qr(A_negative)
    rq_A_neg, tau_neg, work_neg, info_neg = geqrfp(A_negative)
    # assert that any of the entries on the diagonal from linalg.qr
    #   are negative and that all of geqrfp are positive.
    assert_(np.any(r_rq_neg[np.arange(r_rq_neg.shape[0]-1),
                            np.arange(r_rq_neg.shape[0]-1)] < 0) and
            np.all(r[np.arange(r.shape[0]-1),
                     np.arange(r.shape[0]-1)] > np.zeros(r.shape[0]-1)))
    # assert that the first value (1 indexed 1) returned as the illegal value
    A[0][0] = None
    _qr_A, _tau, _work, _info = geqrfp(A)
    assert_(_info == -1)
    # check that empty array raises good error message
    A_empty = np.array([])
    with assert_raises(Exception):
        geqrfp(A_empty)
