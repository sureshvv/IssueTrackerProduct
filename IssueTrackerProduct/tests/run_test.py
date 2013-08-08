import os.path
import zope.testing.testrunner

dir = os.path.dirname(__file__)

if __name__ == '__main__':
    zope.testing.testrunner.run((['--auto-color', '--auto-progress']) + [
        '--test-path', dir,
        ])
