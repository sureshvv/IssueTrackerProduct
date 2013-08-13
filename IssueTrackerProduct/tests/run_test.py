import os.path
import zope.testrunner

dir = os.path.dirname(__file__)

if __name__ == '__main__':
    zope.testrunner.run((['--auto-color', '--auto-progress']) + [
        '--test-path', dir,
        ])
