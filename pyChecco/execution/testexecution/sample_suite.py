import unittest


sampled_tests = None


class SampleSuite(unittest.TestSuite):
    def __init__(self, tests=()):
        super().__init__(tests)

    def run(self, result, debug=False):
        global sampled_tests

        topLevel = False
        if getattr(result, '_testRunEntered', False) is False:
            result._testRunEntered = topLevel = True

        for index, test in enumerate(self):
            if isinstance(test, SampleSuite):
                if result.shouldStop:
                    break

                if _isnotsuite(test):
                    self._tearDownPreviousClass(test, result)
                    self._handleModuleFixture(test, result)
                    self._handleClassSetUp(test, result)
                    result._previousTestClass = test.__class__

                    if (getattr(test.__class__, '_classSetupFailed', False) or
                        getattr(result, '_moduleSetUpFailed', False)):
                        continue

                if not debug:
                    test(result)
                else:
                    test.debug()

                if self._cleanup:
                    self._removeTestAtIndex(index)
            else:
                if result.shouldStop:
                    break

                if _isnotsuite(test):
                    self._tearDownPreviousClass(test, result)
                    self._handleModuleFixture(test, result)
                    self._handleClassSetUp(test, result)
                    result._previousTestClass = test.__class__

                    if (getattr(test.__class__, '_classSetupFailed', False) or
                        getattr(result, '_moduleSetUpFailed', False)):
                        continue

                if test.id() in sampled_tests:
                    if not debug:
                        test(result)
                    else:
                        test.debug()
                else:
                    print("Skipped test", test.id())

                if self._cleanup:
                    self._removeTestAtIndex(index)

        if topLevel:
            self._tearDownPreviousClass(None, result)
            self._handleModuleTearDown(result)
            result._testRunEntered = False
        return result


def set_sampled_tests(sampled):
    global sampled_tests
    sampled_tests = sampled


def _isnotsuite(test):
    "A crude way to tell apart testcases and suites with duck-typing"
    try:
        iter(test)
    except TypeError:
        return True
    return False
